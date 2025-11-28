"""
Script Generation Service using Google Gemini 2.5 Pro
Generates segmented scripts for short-form video content
"""

import json
import os
import google.generativeai as genai
from typing import List, Dict


def generate_script(
    idea: str,
    total_duration: int,
    segment_duration: int,
    api_key: str = None
) -> List[Dict[str, str]]:
    """
    Generate a video script broken into segments.
    
    Args:
        idea: The content idea to generate a script for
        total_duration: Total video duration (30 or 45 seconds)
        segment_duration: Duration of each segment (4, 6, or 8 seconds)
        api_key: Gemini API key (optional, will use env var if not provided)
    
    Returns:
        List of script segments with timing and visual descriptions
    """
    num_segments = total_duration // segment_duration
    
    # Use provided key or fall back to environment variable
    gemini_key = api_key or os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not provided")
    
    genai.configure(api_key=gemini_key)
    
    model = genai.GenerativeModel("gemini-2.5-pro-preview-06-05")
    
    prompt = f"""You are an expert short-form video content creator and scriptwriter. 
You specialize in creating engaging, viral-worthy scripts for AI-generated video content.
Your scripts should be visually descriptive, emotionally engaging, and perfectly timed.

IMPORTANT GUIDELINES:
- Each segment must be self-contained with clear visual direction
- Include specific camera angles, movements, and transitions
- Describe the AI influencer's actions, expressions, and positioning
- Include any text overlays or captions to display
- Make the content hook-worthy from the first second
- End with a strong call-to-action or memorable moment

Create a script for a {total_duration}-second short-form video about:

"{idea}"

Break this into exactly {num_segments} segments of {segment_duration} seconds each.

For EACH segment, provide:
1. **segment_number**: The segment order (1, 2, 3, etc.)
2. **start_time**: Start time in seconds
3. **end_time**: End time in seconds
4. **visual_description**: Detailed visual direction for AI video generation (describe the scene, the AI influencer's appearance/actions, camera angle, lighting, background, any motion)
5. **narration**: What the AI influencer says or any voiceover (if any)
6. **text_overlay**: Any on-screen text to display
7. **mood**: The emotional tone of this segment

Return ONLY a valid JSON array with {num_segments} objects. No additional text, no markdown code blocks, just pure JSON.

Example format:
[
  {{
    "segment_number": 1,
    "start_time": 0,
    "end_time": {segment_duration},
    "visual_description": "Close-up of AI influencer looking directly at camera with excited expression...",
    "narration": "You won't believe what I just discovered!",
    "mood": "excited, attention-grabbing"
  }}
]"""

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.8,
            max_output_tokens=4000,
        )
    )
    
    script_text = response.text.strip()
    
    # Clean up markdown code blocks if present
    if script_text.startswith("```"):
        lines = script_text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        script_text = "\n".join(lines)
    
    script_segments = json.loads(script_text.strip())
    
    return script_segments


def format_script_for_display(segments: List[Dict[str, str]]) -> str:
    """Format script segments for user-friendly display."""
    formatted = []
    
    for seg in segments:
        formatted.append(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📹 SEGMENT {seg['segment_number']} | ⏱️ {seg['start_time']}s - {seg['end_time']}s | 🎭 {seg.get('mood', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎬 VISUAL DIRECTION:
{seg['visual_description']}

🎤 NARRATION:
{seg.get('narration', '(No narration)')}

📝 TEXT OVERLAY:
{seg.get('text_overlay', '(No overlay)')}
""")
    
    return "\n".join(formatted)


def parse_edited_script(edited_text: str, original_segments: List[Dict]) -> List[Dict[str, str]]:
    """
    Parse user-edited script back into segments.
    Falls back to original if parsing fails.
    """
    try:
        # If the user provides JSON directly
        if edited_text.strip().startswith("["):
            return json.loads(edited_text)
    except:
        pass
    
    # Return original if we can't parse edits
    return original_segments
