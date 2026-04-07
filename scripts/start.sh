#!/bin/bash

# AI Catalogue - Production Startup Script
# This script starts the containerized AI Catalogue application in production mode

set -e

echo "🚀 Starting AI Catalogue in Production Mode..."

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env file with your configuration before running again."
    echo "🔑 Especially set your API keys for Google, OpenAI, and other services."
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p ./volumes/postgres
mkdir -p ./volumes/milvus
mkdir -p ./volumes/etcd
mkdir -p ./volumes/minio
mkdir -p ./logs

# Pull latest images
echo "📦 Pulling latest Docker images..."
docker-compose pull

# Build custom images
echo "🔨 Building custom images..."
docker-compose build --no-cache

# Start services in order
echo "🗄️  Starting databases first..."
docker-compose up -d postgres etcd minio

echo "⏳ Waiting for databases to be ready..."
sleep 30

echo "🔍 Starting Milvus vector database..."
docker-compose up -d milvus

echo "⏳ Waiting for Milvus to be ready..."
sleep 30

echo "🤖 Starting ChromaDB (Public Chatbot Vector Database)..."
docker-compose up -d chromadb

echo "⏳ Waiting for ChromaDB to be ready..."
sleep 15

echo "🐍 Starting Django backend..."
docker-compose up -d backend

echo "⏳ Waiting for backend to be ready..."
sleep 20

echo "⚛️  Starting Svelte frontend..."
docker-compose up -d frontend

echo "🌐 Starting Nginx reverse proxy..."
docker-compose up -d nginx

echo "🎛️  Starting optional services..."
docker-compose up -d pgadmin

# Show status
echo ""
echo "✅ AI Catalogue started successfully!"
echo ""
echo "🌟 Access URLs:"
echo "   📱 Application: http://localhost"
echo "   🔧 Django Admin: http://localhost/admin/"
echo "   🗄️  PgAdmin: http://localhost:8080"
echo "   🔍 Attu (Milvus UI): http://localhost:3001"
echo "   📊 Milvus API: http://localhost:9091"
echo ""
echo "📋 Container Status:"
docker-compose ps

echo ""
echo "📝 To view logs:"
echo "   All services: docker-compose logs -f"
echo "   Backend only: docker-compose logs -f backend"
echo "   Frontend only: docker-compose logs -f frontend"
echo ""
echo "🔐 Attu (Milvus UI) Authentication:"
echo "   URL: http://localhost:3001"
echo "   Address: milvus:19530"
echo "   Username: ${MILVUS_ROOT_USER:-milvusadmin}"
echo "   Password: ${MILVUS_ROOT_PASSWORD:-[check .env file]}"
echo "   Authentication: ✓ Enable"
echo ""
echo "⚠️  Note: First startup may take longer as databases initialize."
echo "🔐 Remember to set your API keys in the .env file for full functionality."