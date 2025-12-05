#!/bin/bash
# Script to run the Gradio app

cd "$(dirname "$0")"

# Activate virtual environment
source myenv/bin/activate

# Run the app
python app.py


