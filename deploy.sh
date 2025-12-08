#!/bin/bash
# Deployment script for AI Content Pipeline
# This script can be run manually on the server or called by CI/CD

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting deployment..."

# Check if required environment variables are set
if [ -z "$GEMINI_API_KEY" ] || [ -z "$REPLICATE_API_TOKEN" ] || [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "❌ Error: Required environment variables not set!"
    echo "   Please set: GEMINI_API_KEY, REPLICATE_API_TOKEN, ELEVENLABS_API_KEY"
    echo ""
    echo "Usage:"
    echo "  GEMINI_API_KEY=\"...\" REPLICATE_API_TOKEN=\"...\" ELEVENLABS_API_KEY=\"...\" ./deploy.sh"
    exit 1
fi

echo "📥 Pulling latest code from main branch..."
git pull origin main

echo "🔨 Building Docker image..."
docker-compose build

echo "🛑 Stopping existing container (if running)..."
docker-compose down || true

echo "🚀 Starting new container with secrets..."
GEMINI_API_KEY="$GEMINI_API_KEY" \
REPLICATE_API_TOKEN="$REPLICATE_API_TOKEN" \
ELEVENLABS_API_KEY="$ELEVENLABS_API_KEY" \
docker-compose up -d

echo "⏳ Waiting for container to be healthy..."
sleep 5

echo "🧹 Cleaning up old Docker images..."
docker image prune -f

echo "✅ Deployment complete!"
echo ""
echo "📊 Container status:"
docker-compose ps

echo ""
echo "📝 View logs with: docker-compose logs -f"
echo "🛑 Stop with: docker-compose down"
