#!/bin/bash

# Docker Cleanup Script for AI Catalogue
# Removes orphaned containers, unused images, and networks while preserving volume data

set -e

echo "🧹 Docker Space Cleanup - AI Catalogue"
echo "==============================================="

# Function to show disk space
show_space() {
    echo "📊 Current disk usage:"
    df -h /var/lib/docker 2>/dev/null || df -h /
    echo ""
    echo "🐳 Docker system usage:"
    docker system df
    echo ""
}

# Function to list volumes that will be preserved
list_preserved_volumes() {
    echo "🔒 Volumes that will be PRESERVED:"
    echo "   - ai_catalogue_postgres_data"
    echo "   - ai_catalogue_milvus_data"
    echo "   - ai_catalogue_etcd_data"
    echo "   - ai_catalogue_minio_data"
    echo "   - ai_catalogue_pgadmin_data"
    echo "   - ai_catalogue_chromadb_data"
    echo "   - ./volumes/* (bind mounts)"
    echo ""
}

# Show initial state
echo "🔍 Initial state:"
show_space

# Safety check - ensure we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found!"
    echo "   Please run this script from the project root directory."
    exit 1
fi

# List volumes that will be preserved
list_preserved_volumes

# Confirmation prompt
echo "⚠️  WARNING: This script will remove:"
echo "   ❌ All stopped containers"
echo "   ❌ All orphaned containers"
echo "   ❌ All unused Docker images"
echo "   ❌ All unused Docker networks"
echo "   ❌ Build cache"
echo ""
echo "✅ This script will PRESERVE:"
echo "   🔒 All named volumes (your database data)"
echo "   🔒 All bind mount directories (./volumes/)"
echo ""

read -p "🤔 Do you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "🚫 Cleanup cancelled."
    exit 0
fi

echo ""
echo "🚀 Starting cleanup process..."
echo ""

# Step 1: Stop all running containers for this project
echo "🛑 Step 1: Stopping AI Catalogue containers..."
docker compose -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans || true
echo "✅ AI Catalogue containers stopped"
echo ""

# Step 2: Remove all stopped containers
echo "🗑️  Step 2: Removing all stopped containers..."
STOPPED_CONTAINERS=$(docker ps -aq --filter "status=exited")
if [ ! -z "$STOPPED_CONTAINERS" ]; then
    docker rm $STOPPED_CONTAINERS
    echo "✅ Removed stopped containers"
else
    echo "ℹ️  No stopped containers found"
fi
echo ""

# Step 3: Remove orphaned containers
echo "🧸 Step 3: Removing orphaned containers..."
ORPHANED_CONTAINERS=$(docker ps -aq --filter "label=com.docker.compose.project" --filter "status=exited")
if [ ! -z "$ORPHANED_CONTAINERS" ]; then
    docker rm $ORPHANED_CONTAINERS
    echo "✅ Removed orphaned containers"
else
    echo "ℹ️  No orphaned containers found"
fi
echo ""

# Step 4: Remove unused images (keep images used by existing containers)
echo "🖼️  Step 4: Removing unused Docker images..."
UNUSED_IMAGES=$(docker images -q --filter "dangling=true")
if [ ! -z "$UNUSED_IMAGES" ]; then
    docker rmi $UNUSED_IMAGES
    echo "✅ Removed dangling images"
else
    echo "ℹ️  No dangling images found"
fi

# Remove unused images that are not referenced by any container
echo "🔍 Removing unreferenced images..."
docker image prune -f
echo "✅ Removed unused images"
echo ""

# Step 5: Remove unused networks
echo "🌐 Step 5: Removing unused Docker networks..."
docker network prune -f
echo "✅ Removed unused networks"
echo ""

# Step 6: Remove build cache
echo "🏗️  Step 6: Removing Docker build cache..."
docker builder prune -f
echo "✅ Removed build cache"
echo ""

# Step 7: System prune (but preserve volumes)
echo "🧽 Step 7: Final system cleanup (preserving volumes)..."
docker system prune -f
echo "✅ System cleanup completed"
echo ""

# Step 8: Verify volumes are still intact
echo "🔍 Step 8: Verifying volume integrity..."
echo "📦 Named volumes still present:"
docker volume ls --filter "name=ai_catalogue" || echo "ℹ️  No named volumes found (normal if using bind mounts)"

echo ""
echo "📁 Bind mount directories:"
if [ -d "./volumes" ]; then
    ls -la ./volumes/ | grep -E "^d" || echo "ℹ️  No subdirectories in ./volumes/"
else
    echo "ℹ️  ./volumes directory not found"
fi
echo ""

# Show final state
echo "🎉 Cleanup completed!"
echo ""
echo "🔍 Final state:"
show_space

# Show space reclaimed
echo "💾 Space Reclamation Summary:"
echo "   Run 'docker system df' to see detailed usage"
echo "   Run 'df -h' to see overall disk usage"
echo ""

echo "✅ All your data volumes have been preserved!"
echo ""
echo "🚀 Next steps:"
echo "   1. Run your start-dev.sh script to rebuild and start containers"
echo "   2. Your database data and configurations will be intact"
echo "   3. Docker will download/rebuild only what's needed"
echo ""

echo "📋 If you need to reclaim more space, you can also:"
echo "   • Remove old log files: docker compose logs --tail=0 -f > /dev/null &"
echo "   • Clean system logs: sudo journalctl --vacuum-time=3d"
echo "   • Check for large files: sudo find /var/lib/docker -size +100M -type f"
echo ""

echo "🆘 Emergency volume recovery (if something goes wrong):"
echo "   • Named volumes: docker volume ls"
echo "   • Bind mounts: Check ./volumes/ directory"
echo "   • Restore from backup if available"