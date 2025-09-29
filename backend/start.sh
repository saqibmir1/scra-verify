#!/bin/bash

# Active Duty Verification Service Startup Script

echo "🚀 Starting Active Duty Verification Service..."

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "📁 Loading environment variables from .env file..."
    set -a
    source .env
    set +a
    echo "✅ Environment variables loaded"
else
    echo "ℹ️  No .env file found - using default configuration"
    echo "   SCRA credentials will be loaded from user settings in database"
fi

# Environment is now Railway-based

# Install Playwright browsers if needed
echo "🎭 Installing Playwright browsers..."
poetry run playwright install chromium --with-deps

# Get port from environment or default to 8000
PORT=${PORT:-8000}

# Start the service
echo "🌐 Starting FastAPI service on http://localhost:$PORT"
poetry run uvicorn main:app --host 0.0.0.0 --port $PORT --reload