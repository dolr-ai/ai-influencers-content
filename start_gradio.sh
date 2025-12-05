#!/bin/bash
# Start script with better output

cd "$(dirname "$0")"

echo "🔍 Checking virtual environment..."
if [ ! -d "myenv" ]; then
    echo "❌ Virtual environment not found!"
    exit 1
fi

echo "✅ Activating virtual environment..."
source myenv/bin/activate

echo "🔍 Checking Python version..."
python --version

echo "🔍 Checking required packages..."
python -c "import gradio; print(f'✅ Gradio {gradio.__version__} installed')" 2>/dev/null || {
    echo "❌ Gradio not installed. Installing requirements..."
    pip install -r requirements.txt
}

echo ""
echo "🚀 Starting Gradio app..."
echo ""

python app.py
