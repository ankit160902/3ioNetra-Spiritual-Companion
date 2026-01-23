#!/bin/bash
# Docker Push Script for Spiritual Voice Bot Backend

echo "=========================================="
echo "🐳 Docker Push - Spiritual Voice Bot"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

echo "✅ Docker is installed"
echo ""

# Check Docker Hub username
DOCKER_USERNAME=${DOCKER_USERNAME:-""}

if [ -z "$DOCKER_USERNAME" ]; then
    echo "📝 Enter your Docker Hub username:"
    read DOCKER_USERNAME
fi

if [ -z "$DOCKER_USERNAME" ]; then
    echo "❌ No username provided"
    exit 1
fi

echo ""
echo "🔑 Logging in to Docker Hub..."
docker login -u "$DOCKER_USERNAME" || exit 1

echo ""
echo "📦 Tagging image..."
docker tag spiritual-voice-bot-backend:latest "$DOCKER_USERNAME/spiritual-voice-bot-backend:latest"
docker tag spiritual-voice-bot-backend:1.0.0 "$DOCKER_USERNAME/spiritual-voice-bot-backend:1.0.0"

echo ""
echo "🚀 Pushing to Docker Hub..."
docker push "$DOCKER_USERNAME/spiritual-voice-bot-backend:latest" || exit 1
docker push "$DOCKER_USERNAME/spiritual-voice-bot-backend:1.0.0" || exit 1

echo ""
echo "=========================================="
echo "✅ Push Complete!"
echo "=========================================="
echo ""
echo "📍 Image URLs:"
echo "   • $DOCKER_USERNAME/spiritual-voice-bot-backend:latest"
echo "   • $DOCKER_USERNAME/spiritual-voice-bot-backend:1.0.0"
echo ""
echo "To pull later:"
echo "   docker pull $DOCKER_USERNAME/spiritual-voice-bot-backend:latest"
echo ""
