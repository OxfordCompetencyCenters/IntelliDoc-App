#!/bin/bash

# AI Catalogue - Production Startup Script
# This script starts the containerized AI Catalogue application in production mode with Gunicorn

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
ENABLE_SSL=false
REBUILD=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ssl)
            ENABLE_SSL=true
            shift
            ;;
        --rebuild)
            REBUILD=true
            shift
            ;;
        --help|-h)
            echo "AI Catalogue - Production Startup Script"
            echo ""
            echo "Usage: ./scripts/production.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --ssl       Enable SSL/HTTPS (requires certificates in nginx/ssl/)"
            echo "  --rebuild   Force rebuild all Docker images"
            echo "  --help, -h  Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./scripts/production.sh              # Basic production startup"
            echo "  ./scripts/production.sh --ssl        # With SSL certificates"
            echo "  ./scripts/production.sh --rebuild    # Force rebuild images"
            echo "  ./scripts/production.sh --ssl --rebuild"
            echo ""
            echo "Requirements:"
            echo "  - Docker and Docker Compose installed"
            echo "  - .env file with configuration"
            echo "  - For SSL: certificates in nginx/ssl/ (fullchain.pem, privkey.pem)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI Catalogue - Production Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}.env file not found. Creating from template...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}Please edit .env file with your production configuration before running again.${NC}"
        exit 1
    else
        echo -e "${RED}.env.example not found. Please create a .env file manually.${NC}"
        exit 1
    fi
fi

# Load environment variables
set -a
source .env
set +a

# Validate required credentials
if [[ -z "${MILVUS_ROOT_USER}" || -z "${MILVUS_ROOT_PASSWORD}" ]]; then
    echo -e "${RED}Missing required Milvus credentials in .env file!${NC}"
    echo "   Please add:"
    echo "   MILVUS_ROOT_USER=milvusadmin"
    echo "   MILVUS_ROOT_PASSWORD=your_secure_password"
    exit 1
fi

if [[ -z "${MINIO_ROOT_USER}" || -z "${MINIO_ROOT_PASSWORD}" ]]; then
    echo -e "${RED}Missing required MinIO credentials in .env file!${NC}"
    echo "   Please add:"
    echo "   MINIO_ROOT_USER=minioadmin"
    echo "   MINIO_ROOT_PASSWORD=your_secure_password"
    exit 1
fi

# Check SSL certificates if SSL is enabled
if [ "$ENABLE_SSL" = true ]; then
    if [ ! -f ./nginx/ssl/fullchain.pem ] || [ ! -f ./nginx/ssl/privkey.pem ]; then
        echo -e "${RED}SSL enabled but certificates not found!${NC}"
        echo "   Please ensure these files exist:"
        echo "   - nginx/ssl/fullchain.pem"
        echo "   - nginx/ssl/privkey.pem"
        exit 1
    fi
    echo -e "${GREEN}SSL certificates found${NC}"
fi

# Set production environment
export ENVIRONMENT=production
export DEBUG=False

# Compose command
COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# Create necessary directories
echo -e "${BLUE}Creating necessary directories...${NC}"
mkdir -p ./volumes/postgres
mkdir -p ./volumes/milvus
mkdir -p ./volumes/etcd
mkdir -p ./volumes/minio
mkdir -p ./nginx/ssl
mkdir -p ./logs

# Stop existing containers
echo -e "${BLUE}Stopping existing containers...${NC}"
$COMPOSE_CMD down --remove-orphans || true

# Pull latest images for databases
echo -e "${BLUE}Pulling latest database images...${NC}"
docker compose pull postgres etcd minio milvus chromadb

# Enable BuildKit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build images
if [ "$REBUILD" = true ]; then
    echo -e "${BLUE}Force rebuilding all images...${NC}"
    docker builder prune -af --filter "until=24h" > /dev/null 2>&1 || true
    $COMPOSE_CMD build --no-cache
else
    echo -e "${BLUE}Building images...${NC}"
    $COMPOSE_CMD build
fi

# Function to check service health
check_health() {
    local service=$1
    local check_cmd=$2
    local timeout=$3
    local counter=0

    while [ $counter -lt $timeout ]; do
        if eval "$check_cmd" > /dev/null 2>&1; then
            return 0
        fi

        if [ $((counter % 15)) -eq 0 ]; then
            echo -e "   ${YELLOW}Waiting for $service... ($counter/${timeout}s)${NC}"
        fi

        sleep 5
        counter=$((counter + 5))
    done

    return 1
}

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Starting Production Services${NC}"
echo -e "${BLUE}========================================${NC}"

# Step 1: PostgreSQL
echo ""
echo -e "${BLUE}Step 1: Starting PostgreSQL database...${NC}"
$COMPOSE_CMD up -d postgres

echo -e "${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
if check_health "PostgreSQL" "docker compose exec postgres pg_isready -U ${DB_USER:-ai_catalogue_user} -d ${DB_NAME:-ai_catalogue_db}" 60; then
    echo -e "${GREEN}PostgreSQL is ready!${NC}"
else
    echo -e "${RED}PostgreSQL failed to start within timeout${NC}"
    exit 1
fi

# Step 2: etcd and MinIO
echo ""
echo -e "${BLUE}Step 2: Starting etcd and MinIO...${NC}"
$COMPOSE_CMD up -d etcd minio

echo -e "${YELLOW}Waiting for etcd to be ready...${NC}"
sleep 10
if check_health "etcd" "docker compose exec etcd etcdctl endpoint health" 60; then
    echo -e "${GREEN}etcd is healthy!${NC}"
else
    echo -e "${YELLOW}etcd health check timed out (may still be starting)${NC}"
fi

# Step 3: Milvus
echo ""
echo -e "${BLUE}Step 3: Starting Milvus v2.6.0...${NC}"
$COMPOSE_CMD up -d milvus

echo -e "${YELLOW}Waiting for Milvus to initialize (this may take 2-4 minutes)...${NC}"
MILVUS_HEALTHY=false
if check_health "Milvus" "curl -f -s http://localhost:9091/healthz" 240; then
    echo -e "${GREEN}Milvus is healthy and ready!${NC}"
    MILVUS_HEALTHY=true
else
    echo -e "${YELLOW}Milvus health check timed out${NC}"
    echo -e "${YELLOW}The application will continue startup and retry connecting automatically${NC}"
fi

# Step 4: ChromaDB
echo ""
echo -e "${BLUE}Step 4: Starting ChromaDB...${NC}"
$COMPOSE_CMD up -d chromadb

echo -e "${YELLOW}Waiting for ChromaDB to be ready...${NC}"
if check_health "ChromaDB" "curl -f -s http://localhost:8001/api/v2/heartbeat" 60; then
    echo -e "${GREEN}ChromaDB is healthy and ready!${NC}"
else
    echo -e "${YELLOW}ChromaDB health check timed out (may still be starting)${NC}"
fi

# Step 5: Backend (Gunicorn)
echo ""
echo -e "${BLUE}Step 5: Starting Django backend with Gunicorn...${NC}"
$COMPOSE_CMD up -d backend --no-deps

echo -e "${YELLOW}Waiting for Django backend to be ready...${NC}"
if check_health "Backend" "curl -f -s http://localhost:8000/health/" 120; then
    echo -e "${GREEN}Django backend is ready!${NC}"
else
    # Try admin endpoint as fallback
    if check_health "Backend" "curl -f -s http://localhost:8000/admin/" 30; then
        echo -e "${GREEN}Django backend is ready!${NC}"
    else
        echo -e "${YELLOW}Backend health check timed out (may still be initializing)${NC}"
    fi
fi

# Step 6: Frontend (Node production)
echo ""
echo -e "${BLUE}Step 6: Starting SvelteKit frontend (production)...${NC}"
$COMPOSE_CMD up -d frontend --no-deps

echo -e "${YELLOW}Waiting for frontend to be ready...${NC}"
if check_health "Frontend" "curl -f -s http://localhost:3000/" 60; then
    echo -e "${GREEN}Frontend is ready!${NC}"
else
    echo -e "${YELLOW}Frontend health check timed out (may still be starting)${NC}"
fi

# Step 7: Nginx
echo ""
echo -e "${BLUE}Step 7: Starting Nginx reverse proxy...${NC}"
$COMPOSE_CMD up -d nginx --no-deps

sleep 5
echo -e "${GREEN}Nginx started!${NC}"

# Step 8: Management tools (optional)
echo ""
echo -e "${BLUE}Step 8: Starting management tools...${NC}"
$COMPOSE_CMD up -d pgadmin attu || echo -e "${YELLOW}Management tools may have failed to start${NC}"

# Show status
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  Production Deployment Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}Container Status:${NC}"
$COMPOSE_CMD ps
echo ""

echo -e "${BLUE}Access URLs:${NC}"
echo "   Application: http://localhost (via Nginx)"
if [ "$ENABLE_SSL" = true ]; then
    echo "   Application (HTTPS): https://localhost (via Nginx)"
fi
echo "   Backend API: http://localhost:8000"
echo "   Django Admin: http://localhost:8000/admin/"
echo "   Frontend: http://localhost:3000"
echo "   PgAdmin: http://localhost:8080"
echo "   ChromaDB API: http://localhost:8001"
if [ "$MILVUS_HEALTHY" = true ]; then
    echo "   Attu (Milvus UI): http://localhost:3001"
    echo "   Milvus API: http://localhost:9091"
fi

echo ""
echo -e "${BLUE}Production Features:${NC}"
echo "   - Gunicorn WSGI server (4 workers, 2 threads)"
echo "   - Rate limiting enabled"
echo "   - Security headers configured"
if [ "$ENABLE_SSL" = true ]; then
    echo "   - HTTPS with TLS 1.2/1.3"
    echo "   - HSTS enabled (1 year)"
fi
echo "   - Static file caching"
echo "   - Extended AI processing timeouts (25 min)"

echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "   View all logs: $COMPOSE_CMD logs -f"
echo "   Backend logs: $COMPOSE_CMD logs -f backend"
echo "   Verify Gunicorn: $COMPOSE_CMD exec backend ps aux | grep gunicorn"
echo "   Stop all: $COMPOSE_CMD down"
echo ""
echo -e "${GREEN}Production deployment is running!${NC}"
