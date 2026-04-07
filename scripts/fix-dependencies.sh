#!/bin/bash

# AI Catalogue - Dependency Fix Script
# This script fixes common dependency issues before containerization

set -e

echo "🔧 Fixing frontend dependencies..."

# Navigate to frontend directory
cd ./frontend/my-sveltekit-app

# Remove existing node_modules and lock file
echo "🧹 Cleaning existing dependencies..."
rm -rf node_modules package-lock.json

# Clear npm cache
echo "🧹 Clearing npm cache..."
npm cache clean --force

# Reinstall dependencies with updated lock file
echo "📦 Reinstalling dependencies..."
npm install

# Run audit fix for security vulnerabilities
echo "🔒 Fixing security vulnerabilities..."
npm audit fix --force || echo "Some vulnerabilities may require manual intervention"

# Navigate back to root
cd ../../

echo "✅ Frontend dependencies fixed!"
echo ""
echo "🚀 You can now run the containerization:"
echo "   ./scripts/start.sh (production)"
echo "   ./scripts/start-dev.sh (development)"