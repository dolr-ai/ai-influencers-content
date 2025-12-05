# 🚀 Hosting Guide - AI Content Pipeline

## Quick Start

### Option 1: Using the run script (Recommended)
```bash
cd /root/ai-influencers-content
./run.sh
```

### Option 2: Manual activation
```bash
cd /root/ai-influencers-content
source myenv/bin/activate
python app.py
```

### Option 3: Direct execution (without activation)
```bash
cd /root/ai-influencers-content
myenv/bin/python app.py
```

## Environment Setup

1. **Create `.env` file** (if you haven't already):
   ```bash
   cp .env.example .env
   nano .env  # or use your preferred editor
   ```

2. **Add your API keys** to `.env`:
   ```
   GEMINI_API_KEY=your_actual_gemini_key
   REPLICATE_API_TOKEN=your_actual_replicate_token
   ```

## Accessing the App

Once running, the app will be available at:
- **Local access**: `http://localhost:7860` (or the port shown)
- **Network access**: `http://<your-server-ip>:7860`
  - Your server IP: Check with `hostname -I` or look at the startup message

## Running in Background (Production)

### Using nohup:
```bash
cd /root/ai-influencers-content
nohup ./run.sh > app.log 2>&1 &
```

### Using screen:
```bash
screen -S gradio-app
cd /root/ai-influencers-content
./run.sh
# Press Ctrl+A then D to detach
```

### Using tmux:
```bash
tmux new -s gradio-app
cd /root/ai-influencers-content
./run.sh
# Press Ctrl+B then D to detach
```

## Stopping the App

- If running in foreground: Press `Ctrl+C`
- If running in background: Find the process and kill it:
  ```bash
  ps aux | grep app.py
  kill <PID>
  ```

## Firewall Configuration

If you can't access from outside, you may need to open the port:

```bash
# For UFW (Ubuntu)
sudo ufw allow 7860/tcp

# For firewalld (CentOS/RHEL)
sudo firewall-cmd --add-port=7860/tcp --permanent
sudo firewall-cmd --reload
```

## Troubleshooting

1. **Port already in use**: The app will automatically try ports 7860-7879
2. **API keys not working**: Check your `.env` file and ensure keys are correct
3. **Module not found**: Make sure you're using the virtual environment:
   ```bash
   source myenv/bin/activate
   pip install -r requirements.txt
   ```

## Production Deployment

For production, consider:
- Using a reverse proxy (nginx/Apache) with SSL
- Running as a systemd service
- Using process managers like supervisor or PM2
- Setting up proper logging and monitoring


