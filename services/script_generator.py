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
    
    # Strip whitespace/newlines from API key to prevent errors
    genai.configure(api_key=gemini_key.strip())
    
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    
    prompt = f"""You are an expert short-form video content creator and scriptwriter. 
You specialize in creating engaging, viral-worthy scripts for AI-generated explanation videos.

IMPORTANT GUIDELINES:
- The AI influencer's appearance and background are provided via a reference image
- Focus on WHAT THE CHARACTER SAYS (narration/dialogue)
- Specify the CHARACTER'S EXPRESSIONS and EMOTIONS for each segment
- DO NOT include text overlays - this is a spoken explanation video
- Make the content engaging and easy to follow
- Each segment should flow naturally to the next

Create a script for a {total_duration}-second explanation video about:

"{idea}"

Break this into exactly {num_segments} segments of {segment_duration} seconds each.

For EACH segment, provide:
1. **segment_number**: The segment order (1, 2, 3, etc.)
2. **start_time**: Start time in seconds
3. **end_time**: End time in seconds
4. **narration**: What the AI influencer says (the actual dialogue/script)
5. **expression**: The facial expression and emotion the character should convey (e.g., "excited and smiling", "thoughtful and serious", "surprised with raised eyebrows")

Return ONLY a valid JSON array with {num_segments} objects. No additional text, no markdown code blocks, just pure JSON.

Example format:
[
  {{
    "segment_number": 1,
    "start_time": 0,
    "end_time": {segment_duration},
    "narration": "Today I'm going to share something incredible with you",
    "expression": "excited and smiling, looking directly at camera"
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
📹 SEGMENT {seg['segment_number']} | ⏱️ {seg['start_time']}s - {seg['end_time']}s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎤 DIALOGUE:
{seg.get('narration', '(No narration)')}

😊 EXPRESSION:
{seg.get('expression', seg.get('mood', '(No expression)'))}
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
