"""
AI Content Pipeline - Simplified Gradio App
Generate short-form AI video content from ideas
"""

"""
AI Content Pipeline - Gradio App
Generate short-form AI video content from ideas using Google Gemini & Veo
"""

import gradio as gr
import json
import os
import tempfile
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv

from services.script_generator import generate_script, format_script_for_display
from services.video_generator import generate_all_clips
from services.video_stitcher import stitch_videos
from services.audio_generator import add_voiceover_to_video

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# Global state
current_script_segments: List[Dict] = []
generated_clips: List[Dict] = []  # Store {segment_idx, video_path, prompt}


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

IMPORTANT: The character's appearance and background are provided via a reference image. 
Focus on:
- What the character SAYS (dialogue/narration)
- What EXPRESSION/EMOTION they should convey

Each segment should be approximately {segment_duration} seconds of spoken content.

User's edited script:
{edited_script}

Return ONLY valid JSON (no markdown):
[
  {{"prompt": "The person says: 'dialogue here'. with expression/emotion"}},
  {{"prompt": "The person says: 'more dialogue'. with another expression"}},
  ...
]"""

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
        
        current_script_segments = segments_data
        return f"✅ Script auto-formatted by LLM! {len(segments_data)} segments ready"
        
    except json.JSONDecodeError as e:
        return f"❌ Error parsing LLM response: {str(e)}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def generate_video_handler(image, segment_duration: int, aspect_ratio: str, add_transitions: bool):
    """Generate video from script"""
    global current_script_segments, generated_clips
    
    if not current_script_segments:
        return "❌ Generate script first", None, gr.update(visible=False)
    
    if image is None:
        return "❌ Upload reference image", None, gr.update(visible=False)
    
    if not REPLICATE_API_TOKEN:
        return "❌ No Replicate API token provided in .env file", None, gr.update(visible=False)
    
    try:
        # Save image
        temp_dir = tempfile.gettempdir()
        image_path = os.path.join(temp_dir, "reference_image.png")
        image.save(image_path)
        
        # Generate clips
        video_paths = generate_all_clips(
            script_segments=current_script_segments,
            reference_image_path=image_path,
            segment_duration=segment_duration,
            replicate_api_token=REPLICATE_API_TOKEN,
            aspect_ratio=aspect_ratio
        )
        
        # Store generated clips for review with the actual prompts sent to Veo
        generated_clips = []
        for idx, video_path in enumerate(video_paths):
            segment = current_script_segments[idx]
            
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
            
            generated_clips.append({
                "segment_idx": idx,
                "video_path": video_path,
                "prompt": segment.get("prompt", ""),
                "actual_prompt": actual_prompt
            })
        
        # Stitch videos
        output_path = os.path.join(temp_dir, "final_output.mp4")
        final_video = stitch_videos(video_paths, output_path, add_transitions)
        
        return f"✅ Video created! Segments: {len(video_paths)}", final_video, gr.update(visible=True)
    except Exception as e:
        return f"❌ Error: {str(e)}", None, gr.update(visible=False)


def get_clip_for_review(clip_index: int):
    """Get a specific clip for review"""
    global generated_clips, current_script_segments
    
    if not generated_clips or clip_index >= len(generated_clips):
        return None, "No clip available", "", ""
    
    clip = generated_clips[clip_index]
    
    # Show what was actually sent to Veo
    actual_veo_prompt = clip.get('actual_prompt', clip['prompt'])
    
    # Show the source segment info if available
    segment = current_script_segments[clip_index] if clip_index < len(current_script_segments) else {}
    
    # Build display text
    display_lines = [f"**Segment {clip_index + 1} of {len(generated_clips)}**\n"]
    
    if segment.get('narration'):
        display_lines.append(f"🎤 **Dialogue:** {segment['narration']}")
    
    if segment.get('expression') or segment.get('mood'):
        expression_text = segment.get('expression', segment.get('mood', ''))
        display_lines.append(f"😊 **Expression:** {expression_text}")
    
    segment_info = "\n".join(display_lines)
    
    return (
        clip['video_path'], 
        f"Reviewing Segment {clip_index + 1}/{len(generated_clips)}", 
        segment_info,
        actual_veo_prompt
    )


def regenerate_clip_handler(clip_index: int, image, segment_duration: int, aspect_ratio: str, edited_prompt: str):
    """Regenerate a specific clip"""
    global generated_clips, current_script_segments
    
    if not generated_clips or clip_index >= len(generated_clips):
        return "❌ Invalid clip index", None
    
    if image is None:
        return "❌ Upload reference image", None
    
    if not REPLICATE_API_TOKEN:
        return "❌ No Replicate API token provided in .env file", None
    
    try:
        # Update prompt if edited
        prompt = edited_prompt.strip()
        if not prompt:
            prompt = current_script_segments[clip_index]["prompt"]
        else:
            current_script_segments[clip_index]["prompt"] = prompt
        
        # Save image
        temp_dir = tempfile.gettempdir()
        image_path = os.path.join(temp_dir, "reference_image.png")
        image.save(image_path)
        
        # Regenerate single clip
        video_paths = generate_all_clips(
            script_segments=[{"prompt": prompt}],
            reference_image_path=image_path,
            segment_duration=segment_duration,
            replicate_api_token=REPLICATE_API_TOKEN,
            aspect_ratio=aspect_ratio
        )
        
        # Update stored clip
        generated_clips[clip_index]["video_path"] = video_paths[0]
        generated_clips[clip_index]["prompt"] = prompt
        
        return f"✅ Segment {clip_index + 1} regenerated!", video_paths[0]
    except Exception as e:
        return f"❌ Error: {str(e)}", None


def finalize_video_handler(add_transitions: bool, add_voiceover: bool):
    """Stitch all clips together after review and optionally add voice-over"""
    global generated_clips
    
    if not generated_clips:
        return "❌ No clips to stitch", None, gr.update(visible=False)
    
    try:
        temp_dir = tempfile.gettempdir()
        video_paths = [clip["video_path"] for clip in generated_clips]
        
        # Step 1: Stitch videos
        output_path = os.path.join(temp_dir, "final_output_reviewed.mp4")
        final_video = stitch_videos(video_paths, output_path, add_transitions)
        
        status = f"✅ Final video created with {len(video_paths)} segments!"
        
        # Step 2: Add voice-over if requested
        if add_voiceover:
            if not ELEVENLABS_API_KEY:
                return "❌ No ElevenLabs API key provided in .env file", final_video, gr.update(visible=False)
            
            status += "\n🎤 Adding voice-over..."
            return status, final_video, gr.update(visible=True, value=final_video)
        
        return status, final_video, gr.update(visible=False)
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
    gr.Markdown("# ✨ AI Content Pipeline")
    gr.Markdown("Transform ideas into AI-generated short-form videos using Google Gemini & Veo")
    
    gr.Markdown("### Step 1: Generate Script")
    
    with gr.Row():
        with gr.Column():
            idea = gr.Textbox(label="Video Idea", lines=3, placeholder="E.g., '5 productivity hacks that changed my life'")
            total_duration = gr.Radio([30, 45], value=30, label="Total Duration (seconds)")
        with gr.Column():
            segment_duration = gr.Radio([4, 6, 8], value=6, label="Segment Duration (seconds)")
            gen_script_btn = gr.Button("🎬 Generate Script", variant="primary", size="lg")
    
    script_status = gr.Textbox(label="Status", interactive=False)
    script_display = gr.Textbox(label="Generated Script", lines=15, interactive=False)
    
    # Script editing section (hidden by default)
    with gr.Group(visible=False) as edit_script_section:
        gr.Markdown("#### ✏️ Edit Script (Optional)")
        gr.Markdown("✨ **Write freely!** The LLM will automatically format your text.")
        gr.Markdown("💡 Focus on the **dialogue** and **expressions** - the character's appearance comes from the image!")
        edited_script = gr.Textbox(
            label="Edit Script", 
            lines=10, 
            placeholder="Write what the character should say...\n\nE.g.:\n1. Hello everyone! (excited)\n2. Today I'll explain... (confident)\n3. Let me show you... (friendly)"
        )
        with gr.Row():
            update_script_btn = gr.Button("💾 Update Script (Auto-formats with LLM)", variant="secondary")
            update_status = gr.Textbox(label="Update Status", interactive=False, scale=2)
    
    gr.Markdown("---")
    gr.Markdown("### Step 2: Generate Video")
    
    with gr.Row():
        with gr.Column():
            image = gr.Image(label="AI Influencer Reference Image", type="pil")
            aspect_ratio = gr.Radio(["9:16", "16:9", "1:1"], value="9:16", label="Aspect Ratio")
        with gr.Column():
            add_transitions = gr.Checkbox(label="Add Transitions", value=True)
            gen_video_btn = gr.Button("🚀 Generate Video", variant="primary", size="lg")
    
    video_status = gr.Textbox(label="Status", interactive=False)
    final_video = gr.Video(label="Final Video")
    
    # Clip review section (hidden by default)
    with gr.Group(visible=False) as review_section:
        gr.Markdown("---")
        gr.Markdown("### Step 3: Review & Regenerate Clips")
        
        with gr.Row():
            clip_selector = gr.Slider(
                minimum=0, 
                maximum=10, 
                step=1, 
                value=0, 
                label="Select Clip to Review",
                interactive=True
            )
            review_status = gr.Textbox(label="Review Status", interactive=False, scale=2)
        
        review_video = gr.Video(label="Current Clip")
        
        segment_info = gr.Markdown(label="Segment Details")
        
        with gr.Accordion("🎯 Actual Prompt Sent to Veo", open=True):
            actual_veo_prompt = gr.Textbox(
                label="This is what was sent to the video generator", 
                lines=4, 
                interactive=False,
                show_label=False
            )
        
        with gr.Row():
            with gr.Column():
                edited_prompt = gr.Textbox(
                    label="✏️ Edit Prompt for Regeneration (Optional)", 
                    lines=3, 
                    placeholder="E.g., The person says: 'new dialogue here'. with excited expression"
                )
            with gr.Column():
                regenerate_btn = gr.Button("🔄 Regenerate This Clip", variant="secondary", size="lg")
                regen_status = gr.Textbox(label="Regeneration Status", interactive=False)
        
        gr.Markdown("#### Finalize Video")
        with gr.Row():
            final_transitions = gr.Checkbox(label="Add Transitions", value=True)
            add_voiceover_checkbox = gr.Checkbox(label="Add Voice-Over (ElevenLabs)", value=True)
            finalize_btn = gr.Button("✅ Finalize & Stitch All Clips", variant="primary", size="lg")
        
        finalize_status = gr.Textbox(label="Finalize Status", interactive=False)
        final_reviewed_video = gr.Video(label="Final Stitched Video")
    
    # Voice-over section (hidden by default, shown after finalization if voice-over selected)
    with gr.Group(visible=False) as voiceover_section:
        gr.Markdown("---")
        gr.Markdown("### Step 4: Add Voice-Over 🎤")
        gr.Markdown("Using **ElevenLabs** with **Leo - Energetic Hindi Voice** (Multilingual v2)")
        
        with gr.Row():
            voiceover_btn = gr.Button("🎙️ Generate Voice-Over", variant="primary", size="lg")
            voiceover_status = gr.Textbox(label="Voice-Over Status", interactive=False, scale=2)
        
        final_with_voiceover = gr.Video(label="Final Video with Voice-Over")
    
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
        inputs=[image, segment_duration, aspect_ratio, add_transitions],
        outputs=[video_status, final_video, review_section]
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
        inputs=[clip_selector, image, segment_duration, aspect_ratio, edited_prompt],
        outputs=[regen_status, review_video]
    )
    
    # Finalize video
    finalize_btn.click(
        fn=finalize_video_handler,
        inputs=[final_transitions, add_voiceover_checkbox],
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
    
    print(f"🚀 Starting AI Content Pipeline on http://localhost:{port}")
    app.launch(
        server_name="127.0.0.1", 
        server_port=port, 
        share=False
    )
