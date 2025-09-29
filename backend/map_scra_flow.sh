#!/bin/bash

# SCRA Flow Mapper Runner Script
# This script runs the SCRA flow mapper to analyze the website structure

echo "🗺️  SCRA Flow Mapper - Website Structure Analysis"
echo "=================================================="

# Check if credentials are provided
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "❌ Error: Username and password required"
    echo ""
    echo "Usage: ./map_scra_flow.sh <username> <password> [--headless]"
    echo ""
    echo "Examples:"
    echo "  ./map_scra_flow.sh myuser mypass           # Run with visible browser"
    echo "  ./map_scra_flow.sh myuser mypass --headless # Run in background"
    exit 1
fi

USERNAME="$1"
PASSWORD="$2"
HEADLESS_FLAG=""

# Check for headless flag
if [ "$3" == "--headless" ]; then
    HEADLESS_FLAG="--headless"
    echo "🔍 Running in headless mode..."
else
    echo "🖥️  Running with visible browser..."
fi

# Set environment variables if they exist
if [ ! -z "$RESIDENTIAL_PROXY_SERVER" ]; then
    echo "🏠 Using residential proxy: $RESIDENTIAL_PROXY_SERVER"
fi

if [ ! -z "$BROWSER_PLAYWRIGHT_ENDPOINT" ]; then
    echo "🌐 Using Browserless endpoint: $BROWSER_PLAYWRIGHT_ENDPOINT"
fi

echo ""
echo "🚀 Starting SCRA flow mapping..."
echo "⏳ This may take 2-3 minutes to complete..."
echo ""

# Run the mapper
python3 scra_flow_mapper.py --username "$USERNAME" --password "$PASSWORD" $HEADLESS_FLAG

# Check if successful
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Flow mapping completed successfully!"
    echo "📁 Check the 'scra_flow_analysis' directory for results:"
    echo "   - Screenshots of each step"
    echo "   - Complete flow map JSON"
    echo "   - Selector summary for optimization"
    echo ""
    echo "📋 Files created:"
    ls -la scra_flow_analysis/ | grep -E '\.(png|json)$' | head -10
else
    echo ""
    echo "❌ Flow mapping failed. Check the error output above."
    exit 1
fi