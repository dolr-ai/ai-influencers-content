# Deployment Summary - AI Content Pipeline

## Current Setup

Your Gradio app is deployed using Docker and accessible at:
**https://chat.yral.com/content**

### Configuration Details

1. **Deployment Method**: Docker Compose
   - Container: `gradio-content`
   - Auto-restart: Enabled (`restart: unless-stopped`)
   - Port: 7860 (localhost only, bound to 127.0.0.1)
   - Build: Automatic on push to `main` branch via GitHub Actions

2. **CI/CD Pipeline**: GitHub Actions
   - Trigger: Push to `main` branch
   - Auto-deploys to server via SSH
   - Secrets: Managed in GitHub repository secrets

3. **Nginx Reverse Proxy**:
   - Main app: `https://chat.yral.com/` → FastAPI (port 8000)
   - Content app: `https://chat.yral.com/content` → Gradio (port 7860)

4. **API Keys**: 
   - Managed via GitHub Secrets (GEMINI_API_KEY, REPLICATE_API_TOKEN, ELEVENLABS_API_KEY)
   - Injected as environment variables at container startup
   - Backup `.env` file kept on server (not used by Docker)

## Docker Management Commands

### Check Container Status
```bash
cd /root/ai-influencers-content
docker compose ps
# or
docker ps | grep gradio-content
```

### View Container Logs
```bash
cd /root/ai-influencers-content
docker compose logs -f gradio-content

# Or view last 100 lines
docker compose logs --tail=100 gradio-content
```

### Restart Container
```bash
cd /root/ai-influencers-content
docker compose restart gradio-content
```

### Stop Container
```bash
cd /root/ai-influencers-content
docker compose down
```

### Start Container
```bash
cd /root/ai-influencers-content
GEMINI_API_KEY="..." REPLICATE_API_TOKEN="..." ELEVENLABS_API_KEY="..." docker compose up -d
```

### Rebuild and Restart
```bash
cd /root/ai-influencers-content
docker compose build
docker compose down
GEMINI_API_KEY="..." REPLICATE_API_TOKEN="..." ELEVENLABS_API_KEY="..." docker compose up -d
```

### View Container Resource Usage
```bash
docker stats gradio-content
```

## Troubleshooting

### If the app is not accessible:

1. **Check container status**:
   ```bash
   docker compose ps
   docker ps -a | grep gradio-content
   ```

2. **Check container logs**:
   ```bash
   docker compose logs gradio-content
   ```

3. **Check if port is listening**:
   ```bash
   ss -tlnp | grep 7860
   # or
   netstat -tlnp | grep 7860
   ```

4. **Check nginx configuration**:
   ```bash
   nginx -t
   systemctl status nginx
   ```

5. **Test local connection**:
   ```bash
   curl http://127.0.0.1:7860/content
   ```

6. **Check if port is in use**:
   ```bash
   # If port 7860 is blocked, check what's using it
   lsof -i :7860
   ss -tlnp | grep :7860
   ```

### If API features don't work:

1. **Verify container environment variables**:
   ```bash
   docker compose exec gradio-content env | grep -E "GEMINI|REPLICATE|ELEVENLABS"
   ```

2. **Restart container with correct secrets**:
   ```bash
   cd /root/ai-influencers-content
   docker compose down
   GEMINI_API_KEY="..." REPLICATE_API_TOKEN="..." ELEVENLABS_API_KEY="..." docker compose up -d
   ```

### If container won't start:

1. **Check Docker daemon**:
   ```bash
   systemctl status docker
   ```

2. **Check disk space**:
   ```bash
   df -h
   docker system df
   ```

3. **Clean up Docker resources**:
   ```bash
   docker system prune -f
   docker image prune -f
   ```

## Deployment Process

### Automatic Deployment (via GitHub Actions)

1. Push code to `main` branch
2. GitHub Actions workflow triggers automatically
3. Workflow:
   - Checks out code
   - SSHs into server
   - Pulls latest code
   - Stops any service using port 7860
   - Builds Docker image
   - Stops old container
   - Starts new container with secrets from GitHub Secrets
   - Cleans up old Docker images

### Manual Deployment

Use the provided `deploy.sh` script:
```bash
cd /root/ai-influencers-content
GEMINI_API_KEY="..." REPLICATE_API_TOKEN="..." ELEVENLABS_API_KEY="..." ./deploy.sh
```

Or manually:
```bash
cd /root/ai-influencers-content
git pull origin main
docker compose build
docker compose down
GEMINI_API_KEY="..." REPLICATE_API_TOKEN="..." ELEVENLABS_API_KEY="..." docker compose up -d
```

## Files and Configuration

- **Dockerfile**: Container image definition
- **docker-compose.yml**: Service configuration
- **.github/workflows/deploy.yml**: CI/CD pipeline
- **deploy.sh**: Manual deployment script
- **.env**: Backup file (not used by Docker, secrets from GitHub)

## Security Notes

- The Gradio app only listens on `127.0.0.1:7860` (localhost)
- External access is only through nginx with SSL
- API keys are stored as GitHub Secrets (never in repository)
- Secrets injected at container startup via environment variables
- Docker container runs with minimal privileges

## Access URLs

- **Main Chat App**: https://chat.yral.com/
- **Content Pipeline**: https://chat.yral.com/content

Both apps are running permanently and will auto-restart on server reboot!

## Migration Notes

- Old systemd service (`gradio-content.service`) has been removed
- Deployment now uses Docker exclusively
- CI/CD pipeline handles all deployments automatically
