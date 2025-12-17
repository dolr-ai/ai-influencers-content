"""AI Content Pipeline - Gradio App
Generate short-form AI video content from ideas using Google Gemini, Veo and ElevenLabs.
"""

import gradio as gr
import json
import os
import tempfile
from typing import List, Dict, Optional
from dotenv import load_dotenv

from services.script_generator import generate_script, format_script_for_display
from services.video_generator import generate_all_clips
from services.video_stitcher import stitch_videos
from services.audio_generator import add_voiceover_to_video

load_dotenv()

# Strip whitespace/newlines from API keys to prevent header errors
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "").strip()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()

# Global state
current_script_segments: List[Dict] = []
generated_clips: List[Dict] = []  # Store {segment_idx, video_path, prompt}


def parse_transition_overrides(overrides_json: str) -> Optional[Dict[str, str]]:
    """
    Parse JSON mapping of 1-based segment index -> transition style.
    
    Allowed styles: "none", "fade", "crossfade".
    """
    if not overrides_json:
        return None
    
    overrides_json = overrides_json.strip()
    if not overrides_json:
        return None
    
    try:
        raw = json.loads(overrides_json)
    except Exception as e:
        raise ValueError(f"Invalid JSON for transition overrides: {e}")
    
    if not isinstance(raw, dict):
        raise ValueError("Transition overrides must be a JSON object like {\"1\": \"none\", \"2\": \"fade\"}")
    
    normalized: Dict[str, str] = {}
    for key, value in raw.items():
        str_key = str(key).strip()
        if not str_key.isdigit():
            # Skip non-numeric keys
            continue
        if not isinstance(value, str):
            continue
        style = value.lower().strip()
        if style not in {"none", "fade", "crossfade"}:
            continue
        normalized[str_key] = style
    
    return normalized or None


def generate_script_handler(idea: str, total_duration: int, segment_duration: int):
    """Generate script from idea"""
    global current_script_segments
    
    if not idea.strip():
        return "❌ Please enter an idea", "", gr.update(visible=False)
    
    if not GEMINI_API_KEY:
        return "❌ No Gemini API key provided in .env file", "", gr.update(visible=False)
    
    try:
        segments = generate_script(idea, total_duration, segment_duration, GEMINI_API_KEY)
        current_script_segments = segments
        formatted = format_script_for_display(segments)
        return "✅ Script generated successfully!", formatted, gr.update(visible=True)
    except Exception as e:
        return f"❌ Error: {str(e)}", "", gr.update(visible=False)


def update_script_handler(edited_script: str, segment_duration: int):
    """Update script segments from edited text using LLM to auto-format"""
    global current_script_segments
    
    if not edited_script.strip():
        return "❌ Script cannot be empty"
    
    if not GEMINI_API_KEY:
        return "❌ No Gemini API key provided in .env file"
    
    try:
        # First try to parse as-is if already formatted
        lines = edited_script.strip().split('\n')
        new_segments = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('Segment ') and ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    prompt = parts[1].strip()
                    if prompt:
                        # Keep original structure if it exists, just update the prompt field
                        new_segments.append({"prompt": prompt})
        
        # If already formatted correctly, use it
        if new_segments:
            # Preserve original segment structure but update prompts
            for i, new_seg in enumerate(new_segments):
                if i < len(current_script_segments):
                    # Keep original fields but add/update prompt
                    current_script_segments[i]["prompt"] = new_seg["prompt"]
                else:
                    # New segment
                    current_script_segments.append(new_seg)
            
            # If we have fewer new segments than before, trim the list
            if len(new_segments) < len(current_script_segments):
                current_script_segments = current_script_segments[:len(new_segments)]
            
            return f"✅ Script updated! {len(current_script_segments)} segments ready"
        
        # Otherwise, use LLM to format the free-form text
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        formatting_prompt = f"""You are a video script formatter. The user has provided edited script content in free-form text.
Your job is to parse this and structure it into individual video prompts for AI video generation.

CRITICAL FORMATTING REQUIREMENTS:
- The character's appearance and background are provided via a reference image
- You must use EXACTLY this format: "The person says: 'dialogue text'. with expression"
- Keep prompts simple and focused on dialogue + basic expression
- Avoid descriptive language that could trigger content filters
- Use neutral, professional expressions

Each segment should be approximately {segment_duration} seconds of spoken content.

User's edited script:
{edited_script}

Return ONLY valid JSON (no markdown). Use EXACTLY this format:
[
  {{"prompt": "The person says: 'dialogue here'. with calm expression"}},
  {{"prompt": "The person says: 'more dialogue'. with friendly expression"}},
  ...
]

ALLOWED EXPRESSIONS ONLY: calm, friendly, confident, thoughtful, excited, serious, natural, speaking naturally"""

        response = model.generate_content(formatting_prompt)
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        # Parse JSON
        segments_data = json.loads(response_text)
        
        if not segments_data or not isinstance(segments_data, list):
            return "❌ LLM returned invalid format"
        
        # Post-process to ensure consistent formatting and avoid sensitive content
        sanitized_segments = []
        for segment in segments_data:
            if "prompt" in segment:
                prompt = segment["prompt"]
                
                # Ensure the prompt follows the exact format: "The person says: 'text'. with expression"
                if not prompt.startswith("The person says:"):
                    # Try to extract dialogue and reformat
                    if "says:" in prompt:
                        parts = prompt.split("says:", 1)
                        if len(parts) == 2:
                            dialogue_part = parts[1].strip()
                            # Clean and reformat
                            if "with" in dialogue_part:
                                dialogue, expression = dialogue_part.split("with", 1)
                                dialogue = dialogue.strip().strip("'\".,")
                                expression = expression.strip().strip(".,")
                                prompt = f"The person says: '{dialogue}'. with {expression}"
                            else:
                                dialogue = dialogue_part.strip().strip("'\".,")
                                prompt = f"The person says: '{dialogue}'. speaking naturally"
                    else:
                        # Fallback: treat entire prompt as dialogue
                        clean_dialogue = prompt.strip().strip("'\".,")
                        prompt = f"The person says: '{clean_dialogue}'. speaking naturally"
                
                # Sanitize expressions to safe ones
                safe_expressions = ["calm", "friendly", "confident", "thoughtful", "excited", "serious", "natural", "speaking naturally"]
                for safe_expr in safe_expressions:
                    if safe_expr in prompt.lower():
                        break
                else:
                    # If no safe expression found, default to natural
                    if "with" in prompt:
                        prompt = prompt.split("with")[0].strip() + ". speaking naturally"
                    else:
                        prompt = prompt + " speaking naturally"
                
                sanitized_segments.append({"prompt": prompt})
        
        current_script_segments = sanitized_segments
        return f"✅ Script auto-formatted and sanitized! {len(sanitized_segments)} segments ready"
        
    except json.JSONDecodeError as e:
        return f"❌ Error parsing LLM response: {str(e)}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def generate_video_handler(
    image,
    seg1_image,
    seg2_image,
    seg3_image,
    seg4_image,
    seg5_image,
    segment_duration: int,
    aspect_ratio: str,
    add_transitions: bool,
    transition_style: str,
    transition_duration: float,
    transition_overrides_json: str,
    add_subtitles: bool,
):
    """Generate video from script"""
    global current_script_segments, generated_clips
    
    if not current_script_segments:
        return (
            "❌ Generate script first",
            None,
            gr.update(visible=False),
            gr.update(visible=False),
        )
    
    if not REPLICATE_API_TOKEN:
        return (
            "❌ No Replicate API token provided in .env file",
            None,
            gr.update(visible=False),
            gr.update(visible=False),
        )
    
    try:
        temp_dir = tempfile.gettempdir()
        
        seg_images = [seg1_image, seg2_image, seg3_image, seg4_image, seg5_image]
        if image is None and not any(seg_images):
            return (
                "❌ Upload at least one reference image (base or per-segment)",
                None,
                gr.update(visible=False),
                gr.update(visible=False),
            )
        
        image_path = None
        if image is not None:
            image_path = os.path.join(temp_dir, "reference_image.png")
            image.save(image_path)
        
        num_segments = len(current_script_segments)
        segment_image_paths: List[Optional[str]] = [None] * max(num_segments, 5)
        for idx, img in enumerate(seg_images):
            if img is not None:
                seg_path = os.path.join(temp_dir, f"reference_image_segment_{idx + 1}.png")
                img.save(seg_path)
                segment_image_paths[idx] = seg_path
        
        if image_path is None:
            first_seg_path = next((p for p in segment_image_paths if p), None)
            if first_seg_path:
                image_path = first_seg_path
        
        if image_path is None:
            return "❌ Could not read any of the uploaded images", None, gr.update(visible=False), gr.update(visible=False)
        
        # Generate clips
        video_paths = generate_all_clips(
            script_segments=current_script_segments,
            reference_image_path=image_path,
            segment_duration=segment_duration,
            replicate_api_token=REPLICATE_API_TOKEN,
            aspect_ratio=aspect_ratio,
            reference_image_paths=segment_image_paths,
        )
        
        # Store generated clips for review with the actual prompts sent to Veo
        generated_clips = []
        for idx, video_path in enumerate(video_paths):
            segment = current_script_segments[idx]
            
            # Determine which reference image was used for this segment
            if segment_image_paths and idx < len(segment_image_paths) and segment_image_paths[idx]:
                segment_ref_image = segment_image_paths[idx]
            else:
                segment_ref_image = image_path
            
            # Reconstruct what was actually sent to Veo
            if "prompt" in segment and segment["prompt"].strip():
                actual_prompt = segment["prompt"]
            else:
                # Rebuild from structured fields
                narration = segment.get("narration", "")
                expression = segment.get("expression", segment.get("mood", ""))
                
                prompt_parts = []
                if narration:
                    prompt_parts.append(f"The person says: '{narration}'")
                if expression:
                    prompt_parts.append(f"with {expression}")
                else:
                    prompt_parts.append("speaking naturally")
                
                actual_prompt = ". ".join(prompt_parts) + "."
            
            generated_clips.append(
                {
                    "segment_idx": idx,
                    "video_path": video_path,
                    "prompt": segment.get("prompt", ""),
                    "actual_prompt": actual_prompt,
                    "reference_image_path": segment_ref_image,
                }
            )
        
        output_path = os.path.join(temp_dir, "segments_preview.mp4")
        final_video = stitch_videos(
            video_paths,
            output_path,
            add_transitions=False,
        )
        
        return (
            f"✅ Video created! Segments: {len(video_paths)}",
            final_video,
            gr.update(visible=True),
            gr.update(visible=True),
        )
    except Exception as e:
        return f"❌ Error: {str(e)}", None, gr.update(visible=False), gr.update(visible=False)


def get_clip_for_review(clip_index: int):
    """Get a specific clip for review"""
    global generated_clips, current_script_segments
    
    array_index = clip_index - 1
    
    if not generated_clips or array_index < 0 or array_index >= len(generated_clips):
        return None, "No clip available", "", ""
    
    clip = generated_clips[array_index]
    
    # Show what was actually sent to Veo
    actual_veo_prompt = clip.get('actual_prompt', clip['prompt'])
    
    # Show the source segment info if available
    segment = current_script_segments[array_index] if array_index < len(current_script_segments) else {}
    
    # Build display text
    display_lines = [f"**Segment {clip_index} of {len(generated_clips)}**\n"]
    
    if segment.get('narration'):
        display_lines.append(f"🎤 **Dialogue:** {segment['narration']}")
    
    if segment.get('expression') or segment.get('mood'):
        expression_text = segment.get('expression', segment.get('mood', ''))
        display_lines.append(f"😊 **Expression:** {expression_text}")
    
    # Show the exact prompt sent to Replicate
    display_lines.append(f"\n**📝 Exact Prompt to Replicate:**\n`{actual_veo_prompt}`")
    
    segment_info = "\n".join(display_lines)
    
    return (
        clip['video_path'], 
        f"Reviewing Segment {clip_index}/{len(generated_clips)}", 
        segment_info,
        actual_veo_prompt
    )


def regenerate_clip_handler(
    clip_index: int,
    segment_duration: int,
    aspect_ratio: str,
    edited_prompt: str,
    regen_image_override,
):
    """Regenerate a specific clip"""
    global generated_clips, current_script_segments
    
    # Convert from 1-based to 0-based indexing
    array_index = clip_index - 1
    
    if not generated_clips or array_index < 0 or array_index >= len(generated_clips):
        return "❌ Invalid clip index", None
    
    if not REPLICATE_API_TOKEN:
        return "❌ No Replicate API token provided in .env file", None
    
    try:
        clip = generated_clips[array_index]
        
        prompt = edited_prompt.strip()
        if not prompt:
            segment = current_script_segments[array_index]
            if "prompt" in segment and segment["prompt"].strip():
                prompt = segment["prompt"]
            else:
                narration = segment.get("narration", "")
                expression = segment.get("expression", segment.get("mood", ""))
                
                prompt_parts = []
                if narration:
                    prompt_parts.append(f"The person says: '{narration}'")
                if expression:
                    prompt_parts.append(f"with {expression}")
                else:
                    prompt_parts.append("speaking naturally")
                
                prompt = ". ".join(prompt_parts) + "."
        else:
            current_script_segments[array_index]["prompt"] = prompt
        
        temp_dir = tempfile.gettempdir()
        reference_image_path = None
        if regen_image_override is not None:
            reference_image_path = os.path.join(
                temp_dir, f"reference_image_regen_{clip_index}.png"
            )
            regen_image_override.save(reference_image_path)
            # Persist this override so future regenerations use it
            generated_clips[array_index]["reference_image_path"] = reference_image_path
        else:
            reference_image_path = clip.get("reference_image_path")
            if not reference_image_path:
                # Fallback to first clip's reference image if present
                if generated_clips and generated_clips[0].get("reference_image_path"):
                    reference_image_path = generated_clips[0]["reference_image_path"]
                else:
                    return "❌ No reference image found for this clip", None
        
        from services.video_generator import generate_single_clip
        video_path = generate_single_clip(
            prompt=prompt,
            reference_image_path=reference_image_path,
            duration=segment_duration,
            replicate_api_token=REPLICATE_API_TOKEN,
            aspect_ratio=aspect_ratio,
            segment_num=clip_index  # Use the actual clip number for unique filename
        )
        
        original_segment_idx = generated_clips[array_index]["segment_idx"]
        generated_clips[array_index]["video_path"] = video_path
        generated_clips[array_index]["prompt"] = prompt
        generated_clips[array_index]["segment_idx"] = original_segment_idx
        
        return f"✅ Segment {clip_index} regenerated!", video_path
    except Exception as e:
        return f"❌ Error: {str(e)}", None


def finalize_video_handler(
    add_transitions: bool,
    transition_style: str,
    transition_duration: float,
    transition_overrides_json: str,
    add_subtitles: bool,
):
    """Stitch all clips together after review"""
    global generated_clips, current_script_segments
    
    if not generated_clips:
        return "❌ No clips to stitch", None, gr.update(visible=False)
    
    try:
        temp_dir = tempfile.gettempdir()
        
        transition_style = (transition_style or "fade").lower()
        if transition_style not in {"none", "fade", "crossfade"}:
            transition_style = "fade"
        
        try:
            transition_overrides = parse_transition_overrides(transition_overrides_json)
        except ValueError as e:
            return f"❌ {str(e)}", None, gr.update(visible=False)
        
        try:
            transition_duration_value = float(transition_duration)
            if transition_duration_value <= 0:
                transition_duration_value = 0.3
        except (TypeError, ValueError):
            transition_duration_value = 0.3
        
        sorted_clips = sorted(generated_clips, key=lambda x: x["segment_idx"])
        video_paths = [clip["video_path"] for clip in sorted_clips]
        
        # Stitch videos
        output_path = os.path.join(temp_dir, "final_output_reviewed.mp4")
        final_video = stitch_videos(
            video_paths,
            output_path,
            add_transitions=add_transitions,
            transition_duration=transition_duration_value,
            transition_style=transition_style,
            transition_overrides=transition_overrides,
            add_subtitles=add_subtitles,
            script_segments=current_script_segments,
        )
        
        status = f"✅ Final video stitched with {len(video_paths)} segments! Proceed to Step 5 to add voice-over."
        
        # Always show voice-over section as next step
        return status, final_video, gr.update(visible=True)
    except Exception as e:
        return f"❌ Error: {str(e)}", None, gr.update(visible=False)


def add_voiceover_handler(video_path: str):
    """Add ElevenLabs voice-over to the final video"""
    if not video_path:
        return "❌ No video to add voice-over to", None
    
    if not ELEVENLABS_API_KEY:
        return "❌ No ElevenLabs API key provided in .env file", None
    
    try:
        # Add voice-over using ElevenLabs
        voiceover_video = add_voiceover_to_video(
            video_path=video_path,
            elevenlabs_api_key=ELEVENLABS_API_KEY,
            voice_name="Leo - Energetic Hindi Voice"
        )
        
        return "✅ Voice-over added successfully!", voiceover_video
    except Exception as e:
        return f"❌ Error adding voice-over: {str(e)}", None


# Create Gradio interface
with gr.Blocks(title="AI Content Pipeline") as app:
    # Header
    gr.Markdown("# 🎬 AI Content Pipeline")
    gr.Markdown("*Transform your ideas into engaging AI-generated short-form videos using Google Gemini & Veo*")
    
    gr.Markdown("---")
    
    # Tabbed layout for each step
    with gr.Tabs() as tabs:
        # Step 1: Script
        with gr.TabItem("1️⃣ Script"):
            with gr.Group():
                gr.Markdown("## 📝 Step 1: Generate Script")
                
                with gr.Row(equal_height=True):
                    with gr.Column(scale=2):
                        idea = gr.Textbox(
                            label="💡 Your Video Idea",
                            lines=4,
                            placeholder="E.g., '5 productivity hacks that changed my life'\n'The science behind morning routines'\n'Why minimalism is trending'"
                        )
                    with gr.Column(scale=1):
                        with gr.Group():
                            total_duration = gr.Radio(
                                [30, 40], 
                                value=40, 
                                label="⏱️ Total Duration (seconds)"
                            )
                            segment_duration = gr.Radio(
                                [4, 6, 8], 
                                value=8, 
                                label="🎞️ Segment Length (seconds)"
                            )
                
                with gr.Row():
                    gen_script_btn = gr.Button(
                        "🎬 Generate Script", 
                        variant="primary", 
                        size="lg",
                        scale=1
                    )
                    with gr.Column(scale=2):
                        script_status = gr.Textbox(
                            label="Status", 
                            interactive=False
                        )
                
                script_display = gr.Textbox(
                    label="📋 Generated Script", 
                    lines=12, 
                    interactive=False
                )
            
            # Script editing section (hidden by default)
            with gr.Group(visible=False) as edit_script_section:
                with gr.Accordion("✏️ Edit Script (Optional)", open=True):
                    gr.Markdown("✨ **Write freely!** The AI will automatically format your text into video segments.")
                    gr.Markdown("💡 **Focus on:** dialogue, expressions, and emotions - the character's appearance comes from your reference image!")
                    
                    edited_script = gr.Textbox(
                        label="📝 Script Editor", 
                        lines=8, 
                        placeholder="Write what the character should say...\n\nExamples:\n• Hello everyone! I'm excited to share...\n• Today I'll explain the science behind...\n• Let me show you the most important tip..."
                    )
                    
                    with gr.Row():
                        update_script_btn = gr.Button(
                            "💾 Update & Format Script", 
                            variant="secondary",
                            size="sm"
                        )
                        update_status = gr.Textbox(
                            label="Update Status", 
                            interactive=False, 
                            scale=2
                        )
        
        # Step 2: Video generation
        with gr.TabItem("2️⃣ Video"):
            with gr.Group():
                gr.Markdown("## 🎥 Step 2: Generate Video")
                
                with gr.Row(equal_height=True):
                    with gr.Column(scale=2):
                        image = gr.Image(
                            label="🎭 Base Reference Image (used if no per-segment image)", 
                            type="pil",
                            height=260
                        )
                        gr.Markdown("**Optional per-segment images (up to 5 segments):**")
                        with gr.Row():
                            with gr.Column():
                                seg1_image = gr.Image(
                                    label="Segment 1 image (optional)",
                                    type="pil",
                                    height=120,
                                )
                                seg2_image = gr.Image(
                                    label="Segment 2 image (optional)",
                                    type="pil",
                                    height=120,
                                )
                            with gr.Column():
                                seg3_image = gr.Image(
                                    label="Segment 3 image (optional)",
                                    type="pil",
                                    height=120,
                                )
                                seg4_image = gr.Image(
                                    label="Segment 4 image (optional)",
                                    type="pil",
                                    height=120,
                                )
                        seg5_image = gr.Image(
                            label="Segment 5 image (optional)",
                            type="pil",
                            height=120,
                        )
                    with gr.Column(scale=1):
                        with gr.Group():
                            aspect_ratio = gr.Radio(
                                ["9:16", "16:9", "1:1"], 
                                value="9:16", 
                                label="📐 Aspect Ratio (9:16 for TikTok/Reels, 16:9 for YouTube)"
                            )
                            add_transitions = gr.Checkbox(
                                label="✨ Add Smooth Transitions (fade effects)", 
                                value=True
                            )
                            transition_style = gr.Dropdown(
                                ["fade", "crossfade", "none"],
                                value="fade",
                                label="✨ Global Transition Style",
                            )
                            transition_duration = gr.Slider(
                                minimum=0.1,
                                maximum=1.0,
                                value=0.3,
                                step=0.1,
                                label="⏱️ Transition Duration (seconds)",
                            )
                            add_subtitles = gr.Checkbox(
                                label="📝 Add subtitles at top (from script)",
                                value=True,
                            )
                    
                    with gr.Column(scale=1):
                        with gr.Group():
                            transition_overrides_json = gr.Textbox(
                                label="Per-segment transitions (optional JSON)",
                                placeholder='{"1": "none", "2": "fade", "3": "crossfade"}',
                                lines=2,
                            )
                
                with gr.Row():
                    gen_video_btn = gr.Button(
                        "🚀 Generate Video", 
                        variant="primary", 
                        size="lg",
                        scale=1
                    )
                    with gr.Column(scale=2):
                        video_status = gr.Textbox(
                            label="Status", 
                            interactive=False
                        )
                
                final_video = gr.Video(
                    label="🎬 Generated Video", 
                    height=400
                )
        
        # Step 3: Review & regenerate clips
        with gr.TabItem("3️⃣ Review Clips"):
            with gr.Group(visible=False) as review_section:
                gr.Markdown("## 🔍 Step 3: Review & Perfect Your Clips")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        clip_selector = gr.Number(
                            minimum=1, 
                            maximum=10,
                            value=1, 
                            label="🎞️ Select Clip to Review",
                            interactive=True,
                            precision=0
                        )
                    with gr.Column(scale=2):
                        review_status = gr.Textbox(
                            label="Review Status", 
                            interactive=False
                        )
                
                with gr.Row():
                    with gr.Column(scale=2):
                        review_video = gr.Video(
                            label="📹 Current Clip Preview", 
                            height=300
                        )
                    with gr.Column(scale=1):
                        segment_info = gr.Markdown("### 📋 Clip Details")
                
                with gr.Accordion("🎯 Technical Details", open=False):
                    actual_veo_prompt = gr.Textbox(
                        label="Prompt sent to video generator (exactly what was sent to create this clip)", 
                        lines=3, 
                        interactive=False
                    )
                
                with gr.Group():
                    gr.Markdown("### 🔧 Regenerate Clip")
                    with gr.Row():
                        with gr.Column(scale=2):
                            edited_prompt = gr.Textbox(
                                label="✏️ New Prompt (Optional - leave empty to use original)", 
                                lines=3, 
                                placeholder="E.g., The person says: 'Hello everyone!' with an excited, energetic expression"
                            )
                        with gr.Column(scale=1):
                            regenerate_segment_duration = gr.Radio(
                                [4, 6, 8], 
                                value=6, 
                                label="⏱️ Segment Length (seconds)"
                            )
                            regen_image_override = gr.Image(
                                label="Override image for this clip (optional)",
                                type="pil",
                                height=180,
                            )
                            regenerate_btn = gr.Button(
                                "🔄 Regenerate Clip", 
                                variant="secondary", 
                                size="lg"
                            )
                    
                    regen_status = gr.Textbox(
                        label="Regeneration Status", 
                        interactive=False
                    )
        
        # Step 4: Finalize video
        with gr.TabItem("4️⃣ Final Video"):
            with gr.Group(visible=False) as finalize_section:
                gr.Markdown("## ✨ Step 4: Stitch Finalized Clips for Final Video")
                
                with gr.Row():
                    with gr.Column():
                        final_transitions = gr.Checkbox(
                            label="✨ Smooth Transitions (use settings from Step 2)", 
                            value=True
                        )
                    with gr.Column():
                        finalize_btn = gr.Button(
                            "✅ Stitch Final Video", 
                            variant="primary", 
                            size="lg"
                        )
                
                finalize_status = gr.Textbox(
                    label="Status", 
                    interactive=False
                )
                
                final_reviewed_video = gr.Video(
                    label="🎬 Final Video", 
                    height=400
                )
        
        # Step 5: Voice-over
        with gr.TabItem("5️⃣ Voice-over"):
            with gr.Group(visible=False) as voiceover_section:
                gr.Markdown("## 🎙️ Step 5: Add Professional Voice-Over")
                gr.Markdown("*Using **ElevenLabs Leo** - Energetic multilingual voice*")
                
                with gr.Row():
                    voiceover_btn = gr.Button(
                        "🎙️ Generate Voice-Over", 
                        variant="primary", 
                        size="lg",
                        scale=1
                    )
                    with gr.Column(scale=2):
                        voiceover_status = gr.Textbox(
                            label="Voice-Over Status", 
                            interactive=False
                        )
                
                final_with_voiceover = gr.Video(
                    label="🎬 Final Video with Voice-Over", 
                    height=400
                )
    
    # Footer
    gr.Markdown("---")
    with gr.Row():
        gr.Markdown("*Made with ❤️ using Gradio, Google Gemini & Veo, and ElevenLabs*")
    
    # Connect buttons - Step 1: Generate Script
    gen_script_btn.click(
        fn=generate_script_handler,
        inputs=[idea, total_duration, segment_duration],
        outputs=[script_status, script_display, edit_script_section]
    )
    
    # Auto-populate edit box when script is generated
    script_display.change(
        fn=lambda x: x,
        inputs=[script_display],
        outputs=[edited_script]
    )
    
    # Update script from edits
    update_script_btn.click(
        fn=update_script_handler,
        inputs=[edited_script, segment_duration],
        outputs=[update_status]
    )
    
    # Step 2: Generate Video
    gen_video_btn.click(
        fn=generate_video_handler,
        inputs=[
            image,
            seg1_image,
            seg2_image,
            seg3_image,
            seg4_image,
            seg5_image,
            segment_duration,
            aspect_ratio,
            add_transitions,
            transition_style,
            transition_duration,
            transition_overrides_json,
            add_subtitles,
        ],
        outputs=[video_status, final_video, review_section, finalize_section]
    )
    
    # Step 3: Review clips
    clip_selector.change(
        fn=get_clip_for_review,
        inputs=[clip_selector],
        outputs=[review_video, review_status, segment_info, actual_veo_prompt]
    )
    
    # Regenerate individual clip
    regenerate_btn.click(
        fn=regenerate_clip_handler,
        inputs=[clip_selector, regenerate_segment_duration, aspect_ratio, edited_prompt, regen_image_override],
        outputs=[regen_status, review_video]
    )
    
    # Finalize video
    finalize_btn.click(
        fn=finalize_video_handler,
        inputs=[final_transitions, transition_style, transition_duration, transition_overrides_json, add_subtitles],
        outputs=[finalize_status, final_reviewed_video, voiceover_section]
    )
    
    # Add voice-over
    voiceover_btn.click(
        fn=add_voiceover_handler,
        inputs=[final_reviewed_video],
        outputs=[voiceover_status, final_with_voiceover]
    )


if __name__ == "__main__":
    import socket
    
    # Find an available port
    port = 7860
    for p in range(7860, 7880):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("0.0.0.0", p))
            sock.close()
            port = p
            break
        except OSError:
            continue
    
    # Port is set by the loop above (7860-7879 range)
    # If 7860 is not available, it will use the next available port
    
    print(f"🚀 Starting AI Content Pipeline on http://0.0.0.0:{port}")
    print(f"📱 Access at: https://chat.yral.com/content")
    # In Docker, listen on 0.0.0.0 to allow port mapping. Host access is restricted by Docker port binding to 127.0.0.1
    app.launch(
        server_name="0.0.0.0",  # Listen on all interfaces inside container (Docker handles host-side restriction)
        server_port=port, 
        share=False,
        root_path="/content"  # Important: allows Gradio to work on subpath
    )
