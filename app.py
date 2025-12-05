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

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

# Global state
current_script_segments: List[Dict] = []


def generate_script_handler(idea: str, total_duration: int, segment_duration: int):
    """Generate script from idea"""
    global current_script_segments
    
    if not idea.strip():
        return "❌ Please enter an idea", ""
    
    if not GEMINI_API_KEY:
        return "❌ No Gemini API key provided in .env file", ""
    
    try:
        segments = generate_script(idea, total_duration, segment_duration, GEMINI_API_KEY)
        current_script_segments = segments
        formatted = format_script_for_display(segments)
        return "✅ Script generated successfully!", formatted
    except Exception as e:
        return f"❌ Error: {str(e)}", ""


def generate_video_handler(image, segment_duration: int, aspect_ratio: str, add_transitions: bool):
    """Generate video from script"""
    global current_script_segments
    
    if not current_script_segments:
        return "❌ Generate script first", None
    
    if image is None:
        return "❌ Upload reference image", None
    
    if not REPLICATE_API_TOKEN:
        return "❌ No Replicate API token provided in .env file", None
    
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
        
        # Stitch videos
        output_path = os.path.join(temp_dir, "final_output.mp4")
        final_video = stitch_videos(video_paths, output_path, add_transitions)
        
        return f"✅ Video created! Segments: {len(video_paths)}", final_video
    except Exception as e:
        return f"❌ Error: {str(e)}", None


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
    
    # Connect buttons
    gen_script_btn.click(
        fn=generate_script_handler,
        inputs=[idea, total_duration, segment_duration],
        outputs=[script_status, script_display]
    )
    
    gen_video_btn.click(
        fn=generate_video_handler,
        inputs=[image, segment_duration, aspect_ratio, add_transitions],
        outputs=[video_status, final_video]
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
    
    # Use fixed port for production deployment
    port = 7860
    
    print(f"🚀 Starting AI Content Pipeline on http://0.0.0.0:{port}")
    print(f"📱 Access at: https://chat.yral.com/content")
    app.launch(
        server_name="127.0.0.1",  # Only listen on localhost (nginx will proxy)
        server_port=port, 
        share=False,
        root_path="/content"  # Important: allows Gradio to work on subpath
    )
