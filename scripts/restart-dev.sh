#!/bin/bash

# AI Catalogue - Development Restart Script (Milvus v2.6.0)
# This script restarts the containerized AI Catalogue application in development mode

set -e

echo "🔄 Restarting AI Catalogue Development Environment..."

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please run ./scripts/start-dev.sh first to initialize the environment."
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Set development mode
export DEVELOPMENT_MODE=true

echo "🛑 Stopping all services gracefully..."
docker compose -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans

echo "⏳ Waiting for services to fully stop..."
sleep 5

echo "🧹 Removing any dangling containers..."
docker container prune -f || true

echo "🚀 Starting services in proper order..."

echo "🗄️  Step 1: Starting PostgreSQL database..."
docker compose up -d postgres

echo "⏳ Waiting for PostgreSQL to be ready..."
until docker compose exec postgres pg_isready -U ${DB_USER:-ai_catalogue_user} -d ${DB_NAME:-ai_catalogue_db} > /dev/null 2>&1; do
    echo "   📋 Waiting for PostgreSQL..."
    sleep 3
done
echo "✅ PostgreSQL is ready!"

echo "🔧 Step 2: Starting etcd and MinIO..."
docker compose up -d etcd minio

echo "⏳ Waiting for etcd and MinIO to be ready..."
sleep 10

# Check etcd health
ETCD_TIMEOUT=30
ETCD_COUNTER=0
echo "📋 Checking etcd health..."
while [ $ETCD_COUNTER -lt $ETCD_TIMEOUT ]; do
    if docker compose exec etcd etcdctl endpoint health > /dev/null 2>&1; then
        echo "✅ etcd is healthy!"
        break
    fi
    
    if [ $((ETCD_COUNTER % 10)) -eq 0 ]; then
        echo "   ⏱️  Waiting for etcd... ($ETCD_COUNTER/${ETCD_TIMEOUT}s)"
    fi
    
    sleep 2
    ETCD_COUNTER=$((ETCD_COUNTER + 2))
done

echo "🔍 Step 3: Starting Milvus v2.6.0..."
docker compose up -d milvus

echo "⏳ Waiting for Milvus to initialize..."
MILVUS_TIMEOUT=120  # Reduced timeout for restart
MILVUS_COUNTER=0
MILVUS_HEALTHY=false

while [ $MILVUS_COUNTER -lt $MILVUS_TIMEOUT ]; do
    if curl -f -s http://localhost:9091/healthz > /dev/null 2>&1; then
        echo "✅ Milvus v2.6.0 is healthy and ready!"
        MILVUS_HEALTHY=true
        break
    fi
    
    if [ $((MILVUS_COUNTER % 15)) -eq 0 ]; then
        echo "   ⏱️  Milvus initializing... ($MILVUS_COUNTER/${MILVUS_TIMEOUT}s)"
    fi
    
    sleep 5
    MILVUS_COUNTER=$((MILVUS_COUNTER + 5))
done

if [ "$MILVUS_HEALTHY" = "false" ]; then
    echo "⚠️  Milvus health check timed out. Application will continue startup."
fi

echo "🔧 Step 4: Starting ChromaDB..."
docker compose up -d chromadb

echo "⏳ Waiting for ChromaDB to be ready..."
CHROMADB_TIMEOUT=30
CHROMADB_COUNTER=0
while [ $CHROMADB_COUNTER -lt $CHROMADB_TIMEOUT ]; do
    if curl -f -s http://localhost:8001/api/v1/heartbeat > /dev/null 2>&1; then
        echo "✅ ChromaDB is healthy and ready!"
        break
    fi
    
    if [ $((CHROMADB_COUNTER % 10)) -eq 0 ]; then
        echo "   📋 Waiting for ChromaDB... ($CHROMADB_COUNTER/${CHROMADB_TIMEOUT}s)"
    fi
    
    sleep 2
    CHROMADB_COUNTER=$((CHROMADB_COUNTER + 2))
done

echo "🐍 Step 5: Starting Django backend..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d backend --no-deps

echo "⏳ Waiting for Django backend to be ready..."
BACKEND_TIMEOUT=30
BACKEND_COUNTER=0
while [ $BACKEND_COUNTER -lt $BACKEND_TIMEOUT ]; do
    if curl -f -s http://localhost:8000/admin/ > /dev/null 2>&1; then
        echo "✅ Django backend is ready!"
        break
    fi
    
    if [ $((BACKEND_COUNTER % 10)) -eq 0 ]; then
        echo "   📋 Waiting for Django backend... ($BACKEND_COUNTER/${BACKEND_TIMEOUT}s)"
    fi
    
    sleep 2
    BACKEND_COUNTER=$((BACKEND_COUNTER + 2))
done

echo "⚛️  Step 6: Starting SvelteKit frontend..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d frontend-dev --no-deps

echo "🌐 Step 7: Starting Nginx reverse proxy..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d nginx --no-deps

echo "🎛️  Step 8: Starting management tools..."
docker compose up -d pgadmin attu

echo ""
echo "✅ AI Catalogue Development Environment Restarted Successfully!"
echo ""
echo "📊 Container Status:"
docker compose -f docker-compose.yml -f docker-compose.override.yml ps

echo ""
echo "🌟 Access URLs:"
echo "   📱 Application: http://localhost"
echo "   🔥 Frontend Dev Server: http://localhost:5173"
echo "   🐍 Backend Dev Server: http://localhost:8000"
echo "   🔧 Django Admin: http://localhost:8000/admin/"
echo "   🗄️  PgAdmin: http://localhost:8080"
echo "   🤖 ChromaDB API: http://localhost:8001"

if [ "$MILVUS_HEALTHY" = "true" ]; then
    echo "   🔍 Attu (Milvus UI): http://localhost:3001"
    echo "   📊 Milvus API: http://localhost:9091"
else
    echo "   ⚠️  Attu (Milvus UI): http://localhost:3001 (may need more time)"
    echo "   ⚠️  Milvus API: http://localhost:9091 (may need more time)"
fi

echo ""
echo "📋 Useful Commands:"
echo "   View logs: docker compose logs -f"
echo "   Stop all: docker compose -f docker-compose.yml -f docker-compose.override.yml down"
echo "   Full restart: ./scripts/restart-dev.sh"

if [ "$MILVUS_HEALTHY" = "false" ]; then
    echo ""
    echo "💡 If Milvus is still starting up, monitor with: docker compose logs -f milvus"
fi

echo ""
echo "🎉 Development environment is ready!"