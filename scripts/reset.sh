#!/bin/bash

# AI Catalogue - Reset Script
# This script completely resets the development environment
# WARNING: This will delete all data including databases

set -e

echo "⚠️  AI Catalogue Environment Reset"
echo ""
echo "🚨 WARNING: This will:"
echo "   - Stop all containers"
echo "   - Remove all containers" 
echo "   - Delete all volumes (databases, uploads, etc.)"
echo "   - Delete all images"
echo "   - This action cannot be undone!"
echo ""

read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Reset cancelled."
    exit 1
fi

echo ""
echo "🛑 Stopping all containers..."
docker-compose -f docker-compose.yml -f docker-compose.override.yml down

echo "🗑️  Removing containers and volumes..."
docker-compose -f docker-compose.yml -f docker-compose.override.yml down -v --remove-orphans

echo "🧹 Removing images..."
docker-compose -f docker-compose.yml -f docker-compose.override.yml down --rmi all

echo "🧹 Cleaning up Docker system..."
docker system prune -f

echo "🧹 Removing created directories..."
sudo rm -rf ./volumes 2>/dev/null || true
sudo rm -rf ./logs 2>/dev/null || true

echo "🧹 Cleaning up frontend node_modules and build artifacts..."
rm -rf ./frontend/my-sveltekit-app/node_modules 2>/dev/null || true
rm -rf ./frontend/my-sveltekit-app/build 2>/dev/null || true
rm -rf ./frontend/my-sveltekit-app/.svelte-kit 2>/dev/null || true
rm -rf ./frontend/my-sveltekit-app/.vite_cache 2>/dev/null || true

echo "🧹 Cleaning up backend Python cache..."
find ./backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find ./backend -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find ./backend -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "✅ Environment reset complete!"
echo ""
echo "🆕 To start fresh:"
echo "   1. Run: ./scripts/start.sh (production) or ./scripts/start-dev.sh (development)"
echo "   2. Edit .env file with your API keys and configuration"
echo ""
echo "📝 Note: You may need to recreate your .env file if it was in a mounted volume."