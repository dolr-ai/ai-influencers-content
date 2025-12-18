"""
Video Stitching Service
Combines multiple video clips into a single seamless video
"""

import os
import tempfile
from typing import List, Optional, Dict, Any
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip,
)
from moviepy.video.fx.all import fadein, fadeout
from moviepy.video.tools.subtitles import SubtitlesClip


def stitch_videos(
    video_paths: List[str],
    output_path: Optional[str] = None,
    add_transitions: bool = True,
    transition_duration: float = 0.3,
    transition_style: str = "fade",
    transition_overrides: Optional[Dict[str, str]] = None,
    add_subtitles: bool = False,
    script_segments: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Stitch multiple video clips into a single video.
    
    Args:
        video_paths: List of paths to video files to stitch together
        output_path: Optional output path (generates temp file if not provided)
        add_transitions: Whether to add transitions between clips
        transition_duration: Duration of transitions in seconds
        transition_style: Global transition style: \"fade\", \"crossfade\", or \"none\"
        transition_overrides: Optional mapping of 1-based segment index -> style
        add_subtitles: Whether to burn subtitles at the top of the video
        script_segments: Optional list of script segment dicts (for subtitles)
    
    Returns:
        Path to the stitched video file
    """
    if not video_paths:
        raise ValueError("No video paths provided")
    
    if output_path is None:
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, "final_video.mp4")
    
    clips: List[VideoFileClip] = []
    
    for path in video_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Video file not found: {path}")
        clips.append(VideoFileClip(path))
    
    # Build subtitles timing info based on raw clip durations
    subtitles_clip: Optional[SubtitlesClip] = None
    if add_subtitles and script_segments:
        try:
            subtitles_data = []
            current_time = 0.0
            for idx, clip in enumerate(clips):
                segment = script_segments[idx] if idx < len(script_segments) else None
                text = None
                if segment:
                    # Prefer explicit narration if available
                    narration = segment.get("narration")
                    if narration:
                        text = str(narration)
                    else:
                        # Fallback: try to extract dialogue from prompt
                        prompt = segment.get("prompt", "") or ""
                        prompt_lower = prompt.lower()
                        if "the person says:" in prompt_lower:
                            # Try to grab text between quotes after \"The person says:\"
                            try:
                                after = prompt.split("The person says:", 1)[1].strip()
                            except Exception:
                                after = prompt
                            # Remove leading text before first quote
                            quote_chars = ['"', "'"]  # noqa: W605
                            start_idx = -1
                            for qc in quote_chars:
                                if qc in after:
                                    start_idx = after.find(qc)
                                    break
                            if start_idx != -1:
                                qc = after[start_idx]
                                end_idx = after.find(qc, start_idx + 1)
                                if end_idx != -1:
                                    text = after[start_idx + 1 : end_idx]
                            if not text:
                                # Fallback: take up to the first period
                                if "." in after:
                                    text = after.split(".", 1)[0].strip().strip("'").strip('"')
                                else:
                                    text = after.strip().strip("'").strip('"')
                        elif prompt:
                            text = str(prompt)
                
                if text:
                    # Simple wrapping to avoid overly long lines
                    max_chars = 40
                    words = text.split()
                    lines = []
                    line = []
                    for w in words:
                        candidate = (" ".join(line + [w])).strip()
                        if len(candidate) <= max_chars:
                            line.append(w)
                        else:
                            if line:
                                lines.append(" ".join(line))
                            line = [w]
                    if line:
                        lines.append(" ".join(line))
                    wrapped_text = "\n".join(lines) if lines else text
                    
                    start = current_time
                    end = current_time + clips[idx].duration
                    subtitles_data.append(((start, end), wrapped_text))
                
                current_time += clips[idx].duration
            
            if subtitles_data:
                def make_textclip(txt: str) -> TextClip:
                    # Use caption mode for automatic wrapping to the video width
                    sample_clip = clips[0]
                    width = int(sample_clip.w * 0.9)
                    return TextClip(
                        txt,
                        fontsize=42,
                        color="white",
                        stroke_color="black",
                        stroke_width=2,
                        method="caption",
                        size=(width, None),
                    )
                
                subtitles_clip = SubtitlesClip(subtitles_data, make_textclip).set_position(
                    ("center", "top")
                )
        except Exception as e:
            # If subtitle rendering fails, log and continue without subtitles
            print(f"⚠️ Failed to generate subtitles: {e}")
            subtitles_clip = None
    
    # Normalize transition settings
    transition_style = (transition_style or "fade").lower()
    if transition_style not in {"none", "fade", "crossfade"}:
        transition_style = "fade"
    
    base_clip = None
    try:
        if not add_transitions or len(clips) == 1:
            base_clip = concatenate_videoclips(clips, method="compose")
        else:
            overrides = transition_overrides or {}
            
            # If there are no overrides and the style is crossfade,
            # use MoviePy's padding-based crossfade across all boundaries.
            if not overrides and transition_style == "crossfade":
                base_clip = concatenate_videoclips(
                    clips,
                    method="compose",
                    padding=-transition_duration,
                )
            else:
                # Support per-segment \"none\" vs \"fade\" transitions.
                # When overrides are provided, we treat \"crossfade\" like \"fade\"
                processed_clips: List[VideoFileClip] = []
                num_clips = len(clips)
                
                for idx, clip in enumerate(clips):
                    c = clip
                    
                    # Boundary BEFORE this clip: between segment (idx) and (idx+1) in 1-based terms
                    if idx > 0:
                        before_key = str(idx)
                        before_style = overrides.get(before_key, transition_style)
                        if before_style in {"fade", "crossfade"}:
                            c = fadein(c, transition_duration)
                    
                    # Boundary AFTER this clip: between segment (idx+1) and (idx+2) in 1-based terms
                    if idx < num_clips - 1:
                        after_key = str(idx + 1)
                        after_style = overrides.get(after_key, transition_style)
                        if after_style in {"fade", "crossfade"}:
                            c = fadeout(c, transition_duration)
                    
                    processed_clips.append(c)
                
                base_clip = concatenate_videoclips(processed_clips, method="compose")
        
        # Overlay subtitles if requested
        final_clip = base_clip
        if subtitles_clip is not None:
            final_clip = CompositeVideoClip([base_clip, subtitles_clip])
        
        # Write the final video
        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="medium",
            threads=4,
        )
    finally:
        # Clean up
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass
        if base_clip is not None:
            try:
                base_clip.close()
            except Exception:
                pass
    
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

