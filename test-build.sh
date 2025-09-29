#!/bin/bash

echo "Testing frontend build locally..."

# Navigate to frontend directory
cd frontend

echo "Installing dependencies..."
npm install

echo "Building application..."
npm run build

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    echo "📁 Build output directory:"
    ls -la out/
    echo ""
    echo "📄 Key files check:"
    if [ -f "out/index.html" ]; then
        echo "✅ index.html exists"
    else
        echo "❌ index.html missing"
    fi
    
    if [ -d "out/_next" ]; then
        echo "✅ _next directory exists"
    else
        echo "❌ _next directory missing"
    fi
else
    echo "❌ Build failed!"
    exit 1
fi