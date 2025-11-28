"""
Video Stitching Service
Combines multiple video clips into a single seamless video
"""

import os
import tempfile
from typing import List, Optional
from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx.all import fadein, fadeout


def stitch_videos(
    video_paths: List[str],
    output_path: Optional[str] = None,
    add_transitions: bool = True,
    transition_duration: float = 0.3
) -> str:
    """
    Stitch multiple video clips into a single video.
    
    Args:
        video_paths: List of paths to video files to stitch together
        output_path: Optional output path (generates temp file if not provided)
        add_transitions: Whether to add fade transitions between clips
        transition_duration: Duration of fade transitions in seconds
    
    Returns:
        Path to the stitched video file
    """
    if not video_paths:
        raise ValueError("No video paths provided")
    
    if output_path is None:
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, "final_video.mp4")
    
    clips = []
    
    for i, path in enumerate(video_paths):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Video file not found: {path}")
        
        clip = VideoFileClip(path)
        
        if add_transitions and len(video_paths) > 1:
            # Add fade in for all clips except the first
            if i > 0:
                clip = fadein(clip, transition_duration)
            
            # Add fade out for all clips except the last
            if i < len(video_paths) - 1:
                clip = fadeout(clip, transition_duration)
        
        clips.append(clip)
    
    # Concatenate all clips
    final_video = concatenate_videoclips(clips, method="compose")
    
    # Write the final video
    final_video.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=30,
        preset="medium",
        threads=4
    )
    
    # Clean up
    for clip in clips:
        clip.close()
    final_video.close()
    
    return output_path


def get_video_duration(video_path: str) -> float:
    """Get the duration of a video file in seconds."""
    clip = VideoFileClip(video_path)
    duration = clip.duration
    clip.close()
    return duration


def create_preview_thumbnail(video_path: str, output_path: Optional[str] = None) -> str:
    """Create a thumbnail from the first frame of a video."""
    if output_path is None:
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, "thumbnail.jpg")
    
    clip = VideoFileClip(video_path)
    frame = clip.get_frame(0)
    clip.close()
    
    from PIL import Image
    import numpy as np
    
    img = Image.fromarray(np.uint8(frame))
    img.save(output_path, "JPEG", quality=85)
    
    return output_path

