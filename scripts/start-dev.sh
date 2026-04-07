#!/bin/bash

# AI Catalogue - Development Startup Script (Updated for Milvus v2.6.0)
# This script starts the containerized AI Catalogue application in development mode with hot reload

set -e

echo "🚀 Starting AI Catalogue in Development Mode (Milvus v2.6.0 Compatible)..."

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
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env file with your configuration before running again."
    echo "🔑 Especially set your API keys and Milvus/MinIO credentials!"
    echo ""
    echo "🆕 NEW REQUIRED SETTINGS for Milvus v2.6.0:"
    echo "   MILVUS_ROOT_USER=milvusadmin"
    echo "   MILVUS_ROOT_PASSWORD=your_secure_password"
    echo "   MINIO_ROOT_USER=minioadmin"
    echo "   MINIO_ROOT_PASSWORD=your_secure_password"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Validate required Milvus credentials
if [[ -z "${MILVUS_ROOT_USER}" || -z "${MILVUS_ROOT_PASSWORD}" ]]; then
    echo "❌ Missing required Milvus credentials in .env file!"
    echo "   Please add:"
    echo "   MILVUS_ROOT_USER=milvusadmin"
    echo "   MILVUS_ROOT_PASSWORD=your_secure_password"
    exit 1
fi

if [[ -z "${MINIO_ROOT_USER}" || -z "${MINIO_ROOT_PASSWORD}" ]]; then
    echo "❌ Missing required MinIO credentials in .env file!"
    echo "   Please add:"
    echo "   MINIO_ROOT_USER=minioadmin"
    echo "   MINIO_ROOT_PASSWORD=your_secure_password"
    exit 1
fi

# Set development mode
export DEVELOPMENT_MODE=true

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p ./volumes/postgres
mkdir -p ./volumes/milvus
mkdir -p ./volumes/etcd
mkdir -p ./volumes/minio
mkdir -p ./logs

# Check for existing containers and stop them if running
echo "🧹 Cleaning up existing containers..."
docker compose -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans || true

# Pull latest images for databases
echo "📦 Pulling latest database images..."
docker compose pull postgres etcd minio milvus redis

# Enable BuildKit for better network handling and caching
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build development images
echo "🔨 Building development images (with BuildKit enabled)..."
# Prune old BuildKit cache to avoid corruption issues
echo "🧹 Cleaning old BuildKit cache..."
docker builder prune -af --filter "until=24h" > /dev/null 2>&1 || true
docker compose -f docker-compose.yml -f docker-compose.override.yml build --no-cache

# Start services in proper order for Milvus v2.6.0
echo ""
echo "🏗️  Starting Milvus v2.6.0 Infrastructure..."
echo "   ℹ️  Milvus v2.6.0 has significant architectural changes and may take longer to initialize."

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
sleep 20

# Check etcd health
ETCD_TIMEOUT=60
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

echo "🔍 Step 3: Starting Milvus v2.6.0 (Unified Architecture)..."
echo "   📋 This version includes architectural improvements with unified coordinators"
docker compose up -d milvus

echo ""
echo "⏳ Waiting for Milvus v2.6.0 to initialize (this may take 2-3 minutes)..."
echo "   ⚙️  Milvus v2.6.0 features:"
echo "      • Unified coordinators (mixCoord)"
echo "      • Enhanced streaming capabilities"
echo "      • Improved authentication system"
echo ""

# Enhanced Milvus health check with better timeout handling
MILVUS_TIMEOUT=240  # 4 minutes for v2.6.0
MILVUS_COUNTER=0
MILVUS_HEALTHY=false

while [ $MILVUS_COUNTER -lt $MILVUS_TIMEOUT ]; do
    # Check both the health endpoint and container status
    if curl -f -s http://localhost:9091/healthz > /dev/null 2>&1; then
        echo "✅ Milvus v2.6.0 is healthy and ready!"
        MILVUS_HEALTHY=true
        break
    fi
    
    # Show progress every 15 seconds
    if [ $((MILVUS_COUNTER % 15)) -eq 0 ]; then
        echo "   ⏱️  Milvus initializing... ($MILVUS_COUNTER/${MILVUS_TIMEOUT}s)"
        # Show container logs on longer waits
        if [ $MILVUS_COUNTER -gt 60 ]; then
            echo "      🔍 Recent Milvus logs:"
            docker compose logs --tail=3 milvus | sed 's/^/         /'
        fi
    fi
    
    sleep 5
    MILVUS_COUNTER=$((MILVUS_COUNTER + 5))
done

if [ "$MILVUS_HEALTHY" = "false" ]; then
    echo ""
    echo "⚠️  Milvus health check timed out after ${MILVUS_TIMEOUT} seconds"
    echo "   💡 This might be normal for first-time setup or slower systems"
    echo "   🔧 The application will continue startup and retry connecting automatically"
    echo ""
    echo "   📋 Troubleshooting tips:"
    echo "      • Check logs: docker compose logs milvus"
    echo "      • Verify credentials in .env file"
    echo "      • Restart Milvus: docker compose restart milvus"
    echo "      • Check system resources (RAM/CPU)"
fi

echo ""
echo "🔧 Step 4: Starting ChromaDB (Public Chatbot Vector Database)..."
echo "   📋 ChromaDB is required for the public chatbot vector search functionality"
docker compose up -d chromadb

echo "⏳ Waiting for ChromaDB to be ready..."
CHROMADB_TIMEOUT=60
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

echo ""
echo "🔴 Step 5: Starting Redis cache..."
echo "   📋 Redis is required for caching and WebSearch functionality"
docker compose up -d redis

echo "⏳ Waiting for Redis to be ready..."
REDIS_TIMEOUT=30
REDIS_COUNTER=0
while [ $REDIS_COUNTER -lt $REDIS_TIMEOUT ]; do
    if docker compose exec redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo "✅ Redis is healthy and ready!"
        break
    fi
    
    if [ $((REDIS_COUNTER % 10)) -eq 0 ]; then
        echo "   📋 Waiting for Redis... ($REDIS_COUNTER/${REDIS_TIMEOUT}s)"
    fi
    
    sleep 2
    REDIS_COUNTER=$((REDIS_COUNTER + 2))
done

echo ""
echo "🐍 Step 6: Starting Django backend (development mode)..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d backend --no-deps

echo "⏳ Waiting for Django backend to be ready..."
BACKEND_TIMEOUT=60
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

echo "⚛️  Step 7: Starting SvelteKit frontend (development with HMR)..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d frontend-dev --no-deps

echo "🌐 Step 8: Starting Nginx reverse proxy..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d nginx --no-deps

echo "🎛️  Step 9: Starting management tools..."
docker compose up -d pgadmin attu

# Show comprehensive status
echo ""
echo "🎉 AI Catalogue Development Environment Started!"
echo ""
echo "📊 Container Status:"
docker compose -f docker-compose.yml -f docker-compose.override.yml ps

echo ""
echo "🌟 Access URLs:"
echo "   📱 Application: http://localhost (via Nginx)"
echo "   🔥 Frontend Dev Server: http://localhost:5173 (direct, hot reload)"
echo "   🐍 Backend Dev Server: http://localhost:8000 (direct)"
echo "   🔧 Django Admin: http://localhost:8000/admin/"
echo "   🗄️  PgAdmin: http://localhost:8080"
echo "   🤖 ChromaDB API: http://localhost:8001 (Public Chatbot Vector DB)"

if [ "$MILVUS_HEALTHY" = "true" ]; then
    echo "   🔍 Attu (Milvus UI): http://localhost:3001"
    echo "   📊 Milvus API: http://localhost:9091"
    echo "   🌐 Milvus WebUI: http://localhost:9091/webui/"
else
    echo "   ⚠️  Attu (Milvus UI): http://localhost:3001 (may be unavailable initially)"
    echo "   ⚠️  Milvus API: http://localhost:9091 (may be unavailable initially)"
fi

echo ""
echo "🆕 Milvus v2.6.0 Features:"
echo "   • Storage Format V2 with improved performance"
echo "   • Enhanced JSON processing capabilities"
echo "   • Unified coordinator architecture (mixCoord)"
echo "   • Better authentication and security"
echo "   • Native WAL with improved streaming"

echo ""
echo "🔐 Authentication Details:"
if [ "$MILVUS_HEALTHY" = "true" ]; then
    echo "   Milvus/Attu Login:"
    echo "     URL: http://localhost:3001"
    echo "     Milvus Address: milvus:19530"
    echo "     Username: ${MILVUS_ROOT_USER}"
    echo "     Password: [check .env file]"
    echo "     Enable Authentication: ✓"
else
    echo "   ⚠️  Milvus authentication - verify once Milvus is healthy"
fi
echo "   PgAdmin Login:"
echo "     Email: ${PGADMIN_EMAIL:-admin@example.com}"
echo "     Password: ${PGADMIN_PASSWORD:-admin123}"

echo ""
echo "📝 Development Features:"
echo "   🔥 Hot reload: Edit files in ./frontend/ and ./backend/"
echo "   🐛 Debug tools: Django Debug Toolbar enabled"
echo "   📋 Detailed logging available via docker compose logs"
echo "   🔄 Auto-restart on changes"

echo ""
echo "📋 Useful Commands:"
echo "   View all logs: docker compose -f docker-compose.yml -f docker-compose.override.yml logs -f"
echo "   Backend logs: docker compose logs -f backend"
echo "   Frontend logs: docker compose logs -f frontend-dev"
echo "   Milvus logs: docker compose logs -f milvus"
echo "   Restart service: docker compose restart <service-name>"
echo "   Stop all: docker compose -f docker-compose.yml -f docker-compose.override.yml down"

echo ""
if [ "$MILVUS_HEALTHY" = "false" ]; then
    echo "⚠️  NOTE: Milvus v2.6.0 Status"
    echo "   • If Milvus is still initializing, vector search features may not work immediately"
    echo "   • The Django backend will retry connecting automatically"
    echo "   • Monitor progress: docker compose logs -f milvus"
    echo "   • Manual restart if needed: docker compose restart milvus"
    echo ""
fi

echo "🎯 Next Steps:"
echo "   1. Verify all services are healthy: docker compose ps"
echo "   2. Check application logs for any issues"
echo "   3. Test Milvus connection through the Django admin or API"
echo "   4. Configure your AI API keys in the web interface"
echo ""
echo "💡 For production deployment, use: ./scripts/start.sh"
echo "🆘 For support, check the logs and README-DOCKER.md"
