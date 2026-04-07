#!/bin/bash

# AI Catalogue - Stop Script
# This script gracefully stops all AI Catalogue containers

set -e

echo "🛑 Stopping AI Catalogue containers..."

# Stop services gracefully
echo "🔄 Stopping application services..."
docker compose stop frontend nginx backend

echo "🔄 Stopping database services..."
docker compose stop milvus postgres etcd minio pgadmin

echo "✅ All containers stopped successfully!"

# Optionally remove containers (uncomment if desired)
# echo "🗑️  Removing containers..."
# docker compose down

echo ""
echo "📋 Container Status:"
docker compose ps

echo ""
echo "ℹ️  Containers have been stopped but not removed."
echo "💾 Data is preserved in Docker volumes."
echo ""
echo "🔄 To restart: ./scripts/start.sh or ./scripts/start-dev.sh"
echo "🗑️  To remove containers: docker compose down"
echo "⚠️  To remove volumes (DELETES ALL DATA): docker compose down -v"