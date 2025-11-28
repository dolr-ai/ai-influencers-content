# 🎬 AI Content Pipeline

Transform your ideas into stunning AI-generated short-form videos using Google Veo 3.1.

![AI Content Pipeline](https://img.shields.io/badge/AI-Content%20Pipeline-6366f1?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square)
![Gradio](https://img.shields.io/badge/Gradio-4.44+-orange?style=flat-square)

## ✨ Features

- **Idea to Script**: Enter any content idea and get an AI-generated script broken into timed segments
- **Smart Segmentation**: Scripts are automatically divided into 4, 6, or 8-second segments (optimized for Veo 3.1)
- **Script Review**: Edit and refine your script before video generation
- **AI Influencer Consistency**: Upload a reference image to maintain consistent appearance across all segments
- **Automated Video Generation**: Generate video clips using Google Veo 3.1 via Replicate
- **Seamless Stitching**: Automatically combine all segments into a final polished video

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Google Gemini API key (for script generation with Gemini 2.5 Pro)
- Replicate API token (for Veo video generation)

### Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd ai-content-pipeline
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables (optional):**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

### Running the App

```bash
python app.py
```

The app will start at `http://localhost:7860`

## 📖 How to Use

### Step 1: Enter Your Idea
- Type your content idea (e.g., "5 productivity hacks that changed my life")
- Select total video duration (30 or 45 seconds)
- Choose segment duration (4, 6, or 8 seconds based on Veo 3.1 capabilities)

### Step 2: Review the Script
- AI generates a detailed script with:
  - Visual descriptions for each segment
  - Narration/dialogue
  - Text overlays
  - Mood/emotional direction
- Edit the script in JSON format if needed

### Step 3: Upload Reference Image
- Upload a clear image of your AI influencer
- Select aspect ratio (9:16 for TikTok/Reels, 16:9 for YouTube)
- Enable/disable smooth transitions

### Step 4: Generate Video
- Click "Generate Video" to create all segments
- Videos are automatically stitched together
- Download your final video!

## 🔧 Configuration

### API Keys

You can provide API keys in two ways:

1. **Through the UI**: Enter them in the "API Configuration" accordion
2. **Environment Variables**: Set them in a `.env` file

### Video Options

| Option | Values | Description |
|--------|--------|-------------|
| Total Duration | 30, 45 seconds | Total length of the final video |
| Segment Duration | 4, 6, 8 seconds | Length of each Veo-generated clip |
| Aspect Ratio | 9:16, 16:9, 1:1 | Video aspect ratio |
| Transitions | On/Off | Smooth fade transitions between segments |

## 📁 Project Structure

```
ai-content-pipeline/
├── app.py                      # Main Gradio application
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── README.md                  # This file
└── services/
    ├── __init__.py
    ├── script_generator.py    # Gemini 2.5 Pro script generation
    ├── video_generator.py     # Replicate Veo integration
    └── video_stitcher.py      # Video concatenation
```

## 🛠 Tech Stack

- **Frontend**: Gradio 4.44+
- **Script Generation**: Google Gemini 2.5 Pro
- **Video Generation**: Google Veo 3.1 via Replicate
- **Video Processing**: MoviePy
- **Image Handling**: Pillow

## 💡 Tips

1. **Clear Reference Images**: Use high-quality, well-lit images for better AI influencer consistency
2. **Specific Ideas**: More detailed ideas generate better scripts
3. **Script Editing**: Review and tweak the JSON script for better results
4. **Segment Duration**: 6 seconds is a good balance between quality and variety

## ⚠️ Notes

- Video generation can take several minutes per segment
- Replicate charges per generation - check pricing before bulk generation
- Generated videos are saved in the system temp directory

## 📄 License

MIT License - feel free to use and modify!

