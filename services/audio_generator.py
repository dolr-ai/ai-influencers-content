"""
Audio Generation Service using ElevenLabs
Performs speech-to-speech voice-over on final video
"""

import os
import tempfile
from typing import Optional
from elevenlabs import ElevenLabs, save
import subprocess


def extract_audio_from_video(video_path: str) -> str:
    """
    Extract audio from video file using ffmpeg.
    
    Args:
        video_path: Path to the video file
    
    Returns:
        Path to the extracted audio file
    """
    temp_dir = tempfile.gettempdir()
    audio_path = os.path.join(temp_dir, "extracted_audio.wav")
    
    # Use ffmpeg to extract audio
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file
        "-i", video_path,
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # WAV format
        "-ar", "44100",  # Sample rate
        "-ac", "2",  # Stereo
        audio_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return audio_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to extract audio: {e.stderr.decode()}")


def generate_voiceover(
    video_path: str,
    elevenlabs_api_key: str,
    voice_id: str = "Leo",  # Leo - Energetic Hindi Voice
    model: str = "eleven_multilingual_v2"
) -> str:
    """
    Generate voice-over for video using ElevenLabs speech-to-speech.
    
    Args:
        video_path: Path to the video file
        elevenlabs_api_key: ElevenLabs API key
        voice_id: Voice ID to use (default: "Leo")
        model: Model to use (default: "eleven_multilingual_v2")
    
    Returns:
        Path to the final video with new voice-over
    """
    print(f"🎤 Starting voice-over generation...")
    
    # Initialize ElevenLabs client
    client = ElevenLabs(api_key=elevenlabs_api_key)
    
    # Step 1: Extract audio from video
    print("📤 Extracting audio from video...")
    original_audio_path = extract_audio_from_video(video_path)
    
    # Step 2: Perform speech-to-speech with ElevenLabs
    print(f"🎙️ Generating voice-over with {voice_id}...")
    
    try:
        # Read the audio file
        with open(original_audio_path, "rb") as audio_file:
            audio_data = audio_file.read()
        
        # Generate speech-to-speech
        audio = client.speech_to_speech.convert(
            voice_id=voice_id,
            audio=audio_data,
            model_id=model,
        )
        
        # Save the generated audio
        temp_dir = tempfile.gettempdir()
        voiceover_audio_path = os.path.join(temp_dir, "voiceover_audio.mp3")
        save(audio, voiceover_audio_path)
        
        print("✅ Voice-over audio generated!")
        
    except Exception as e:
        raise RuntimeError(f"ElevenLabs speech-to-speech failed: {str(e)}")
    
    # Step 3: Replace audio in video
    print("🎬 Replacing audio in video...")
    output_path = video_path.replace(".mp4", "_with_voiceover.mp4")
    
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file
        "-i", video_path,  # Input video
        "-i", voiceover_audio_path,  # Input audio
        "-c:v", "copy",  # Copy video stream
        "-c:a", "aac",  # Encode audio to AAC
        "-map", "0:v:0",  # Map video from first input
        "-map", "1:a:0",  # Map audio from second input
        "-shortest",  # Finish when shortest stream ends
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Voice-over complete!")
        return output_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to replace audio in video: {e.stderr.decode()}")


def add_voiceover_to_video(
    video_path: str,
    elevenlabs_api_key: str,
    voice_name: str = "Leo - Energetic Hindi Voice",
    progress_callback: Optional[callable] = None
) -> str:
    """
    High-level function to add voice-over to final video.
    
    Args:
        video_path: Path to the final stitched video
        elevenlabs_api_key: ElevenLabs API key
        voice_name: Human-readable voice name
        progress_callback: Optional callback for progress updates
    
    Returns:
        Path to the video with voice-over
    """
    if progress_callback:
        progress_callback(0.1, "Extracting audio from video...")
    
    # Map voice names to IDs (you may need to adjust these)
    # Get voice ID from ElevenLabs or use the voice name directly
    voice_id = "Leo"  # Leo - Energetic Hindi Voice
    
    if progress_callback:
        progress_callback(0.3, "Generating voice-over with ElevenLabs...")
    
    output_path = generate_voiceover(
        video_path=video_path,
        elevenlabs_api_key=elevenlabs_api_key,
        voice_id=voice_id,
        model="eleven_multilingual_v2"
    )
    
    if progress_callback:
        progress_callback(1.0, "Voice-over complete!")
    
    return output_path

