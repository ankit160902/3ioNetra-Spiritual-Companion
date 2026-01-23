#!/bin/bash

# Spiritual Voice Bot - Setup Script
echo "=================================="
echo "Spiritual Voice Bot - Setup"
echo "=================================="
echo ""

# Check if running in the correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p data/{scriptures,processed,qdrant_storage,vector_db}
mkdir -p models
mkdir -p logs
echo "✓ Directories created"
echo ""

# Backend setup
echo "Setting up backend..."
cd backend

# Copy env file if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ Created .env file (please update with your settings)"
else
    echo "✓ .env file already exists"
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Python dependencies installed"

cd ..
echo ""

# Frontend setup
echo "Setting up frontend..."
cd frontend

# Install dependencies
if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install
    echo "✓ Node dependencies installed"
else
    echo "✓ Node dependencies already installed"
fi

cd ..
echo ""

# Docker setup
echo "Docker Setup:"
echo "To run with Docker, execute:"
echo "  docker-compose up -d"
echo ""

# Manual setup instructions
echo "Manual Setup:"
echo "1. Backend:"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   uvicorn main:app --reload"
echo ""
echo "2. Frontend:"
echo "   cd frontend"
echo "   npm run dev"
echo ""

echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Update backend/.env with your configuration"
echo "2. Run 'docker-compose up' or start services manually"
echo "3. Open http://localhost:3000 in your browser"
echo ""
echo "For voice features, ensure:"
echo "- Microphone permissions are granted"
echo "- Audio output is enabled"
echo "- GPU is available for faster processing (optional)"
echo ""
