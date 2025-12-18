"""
Video Generation Service using Google Veo 3.1 via Replicate
Generates video clips from image + prompt
"""

import replicate
import httpx
import base64
import os
import tempfile
from typing import List, Dict, Optional, Callable


def image_to_data_uri(image_path: str) -> str:
    """Convert an image file to a data URI for Replicate."""
    with open(image_path, "rb") as f:
        image_data = f.read()
    
    # Determine MIME type
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", 
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }
    mime_type = mime_types.get(ext, "image/jpeg")
    
    encoded = base64.b64encode(image_data).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def generate_single_clip(
    prompt: str,
    reference_image_path: str,
    duration: int,
    replicate_api_token: str,
    aspect_ratio: str = "9:16",
    segment_num: int = 1,
    max_retries: int = 2
) -> str:
    """
    Generate a single video clip using Veo 3.1 on Replicate.
    
    Args:
        prompt: Visual description for the video
        reference_image_path: Path to the AI influencer's reference image
        duration: Duration in seconds (4, 6, or 8)
        replicate_api_token: Replicate API token
        aspect_ratio: Video aspect ratio (9:16 for vertical, 16:9 for horizontal)
        segment_num: Segment number for logging
        max_retries: Maximum number of retries for sensitive content errors (default: 2)
    
    Returns:
        Path to the generated video file
    """
    # Strip whitespace/newlines from token to prevent header errors
    os.environ["REPLICATE_API_TOKEN"] = replicate_api_token.strip()
    
    # Prepare the image input
    image_uri = image_to_data_uri(reference_image_path)
    
    # Create a clear, concise prompt paragraph
    # The photo provides scene and person details
    enhanced_prompt = prompt

    # Call Replicate Veo 3.1 with retry logic
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"Retrying segment {segment_num} (attempt {attempt + 1}/{max_retries + 1})...")
            
            output = replicate.run(
                "google/veo-3.1", 
                input={
                    "prompt": enhanced_prompt,
                    "image": image_uri,
                    "duration": duration,
                    "aspect_ratio": aspect_ratio,
                    "resolution": "1080p",
                    "generate_audio": True
                }
            )
            
            # Handle different output formats from Replicate
            # Output can be: str (URL), FileOutput object, or iterator
            video_url = None
            video_bytes = None
            
            if isinstance(output, str):
                # Direct URL string
                video_url = output
            elif hasattr(output, 'read'):
                # FileOutput object with read() method - contains bytes
                video_bytes = output.read()
            elif hasattr(output, '__iter__'):
                # Iterator - get first item
                first_item = list(output)[0] if output else None
                if first_item:
                    if isinstance(first_item, str):
                        video_url = first_item
                    elif hasattr(first_item, 'read'):
                        video_bytes = first_item.read()
                    else:
                        video_url = str(first_item)
            else:
                video_url = str(output)
            
            # Save video to file
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"segment_{segment_num}.mp4")
            
            if video_bytes:
                # Already have the bytes, write directly
                with open(output_path, "wb") as f:
                    f.write(video_bytes)
            elif video_url:
                # Download from URL
                response = httpx.get(video_url, follow_redirects=True, timeout=120.0)
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(response.content)
            else:
                raise ValueError("No video data returned from Replicate")
            
            return output_path
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            # Check if this is a sensitive content error that we should retry
            if "flagged as sensitive" in error_msg.lower() or "(E005)" in error_msg:
                if attempt < max_retries:
                    print(f"Sensitive content error for segment {segment_num}, retrying...")
                    continue
                else:
                    print(f"Max retries reached for segment {segment_num}")
            else:
                # For non-sensitive errors, don't retry
                break
    
    # If we get here, all retries failed
    raise RuntimeError(f"Failed to generate segment {segment_num}: {str(last_error)}")


def generate_all_clips(
    script_segments: List[Dict],
    reference_image_path: str,
    segment_duration: int,
    replicate_api_token: str,
    aspect_ratio: str = "9:16",
    progress_callback: Optional[Callable] = None,
    reference_image_paths: Optional[List[str]] = None,
) -> List[str]:
    """
    Generate all video clips for the script.
    
    Args:
        script_segments: List of script segment dictionaries
        reference_image_path: Default path to the AI influencer's reference image
        segment_duration: Duration of each segment (4, 6, or 8)
        replicate_api_token: Replicate API token
        aspect_ratio: Video aspect ratio
        progress_callback: Optional callback for progress updates
        reference_image_paths: Optional list of per-segment reference image paths
    
    Returns:
        List of paths to generated video files
    """
    video_paths = []
    total_segments = len(script_segments)
    
    for i, segment in enumerate(script_segments):
        if progress_callback:
            progress_callback(
                (i / total_segments),
                f"Generating segment {i + 1}/{total_segments}..."
            )
        
        # Check if segment has a direct "prompt" field (from editing/regeneration)
        if "prompt" in segment and segment["prompt"].strip():
            # Use the prompt directly (user edited or LLM formatted)
            prompt = segment["prompt"]
        else:
            # Build from structured fields (original LLM script generation)
            # Focus on: what the character SAYS + their EXPRESSION
            # (The image already provides appearance and background)
            narration = segment.get("narration", "")
            expression = segment.get("expression", segment.get("mood", ""))
            
            # Create prompt focusing on dialogue and expression
            prompt_parts = []
            
            if narration:
                prompt_parts.append(f"The person says: '{narration}'")
            
            if expression:
                prompt_parts.append(f"with {expression}")
            else:
                prompt_parts.append("speaking naturally")
            
            prompt = ". ".join(prompt_parts) + "."
        
        # Choose reference image for this segment (fallback to default if None/absent)
        segment_image_path = reference_image_path
        if reference_image_paths and i < len(reference_image_paths):
            candidate_path = reference_image_paths[i]
            if candidate_path:
                segment_image_path = candidate_path
        
        video_path = generate_single_clip(
            prompt=prompt,
            reference_image_path=segment_image_path,
            duration=segment_duration,
            replicate_api_token=replicate_api_token,
            aspect_ratio=aspect_ratio,
            segment_num=i + 1
        )
        
        video_paths.append(video_path)
        
        if progress_callback:
            progress_callback(
                ((i + 1) / total_segments),
                f"Completed segment {i + 1}/{total_segments}"
            )
    
    return video_paths

