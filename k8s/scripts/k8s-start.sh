#!/bin/bash

# AI Catalogue - Kubernetes Production Startup Script
# This script deploys the AI Catalogue application to Kubernetes in production mode

set -e

echo "🚀 Starting AI Catalogue on Kubernetes (Production Mode)..."

# Check if kubectl is installed and configured
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ kubectl is not configured or cluster is not accessible."
    echo "   Please configure kubectl to connect to your Kubernetes cluster."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.template .env
    echo "📝 Please edit .env file with your configuration before running again."
    echo "🔑 Especially set your Azure and Kubernetes configuration."
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Validate required variables
required_vars=(
    "K8S_NAMESPACE"
    "CONTAINER_REGISTRY" 
    "IMAGE_TAG"
    "STORAGE_CLASS_NAME"
    "DOMAIN_NAME"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Required environment variable $var is not set."
        echo "   Please check your .env file configuration."
        exit 1
    fi
done

# Function to substitute environment variables in YAML files
substitute_env_vars() {
    local file=$1
    local output_file=$2
    
    # Create temporary file with environment variables substituted
    envsubst < "$file" > "$output_file"
}

# Create temporary directory for processed manifests
TEMP_DIR=$(mktemp -d)
echo "📁 Using temporary directory: $TEMP_DIR"

# Process all YAML files and substitute environment variables
echo "📝 Processing Kubernetes manifests..."

for yaml_file in k8s/base/*.yaml; do
    filename=$(basename "$yaml_file")
    substitute_env_vars "$yaml_file" "$TEMP_DIR/$filename"
done

# Create namespace first (idempotent)
echo "📦 Checking/Creating namespace: $K8S_NAMESPACE"
if kubectl get namespace "$K8S_NAMESPACE" &>/dev/null; then
    echo "✅ Namespace $K8S_NAMESPACE already exists"
else
    echo "➕ Creating namespace $K8S_NAMESPACE"
    kubectl apply -f "$TEMP_DIR/namespace.yaml"
fi

# Apply secrets and configmaps (idempotent - kubectl apply handles this)
echo "🔐 Applying/Updating secrets and configuration..."
kubectl apply -f "$TEMP_DIR/secrets.yaml"
kubectl apply -f "$TEMP_DIR/configmap.yaml"

# Start databases and storage services in order (idempotent)
echo "🗄️  Deploying/Updating PostgreSQL database..."
kubectl apply -f "$TEMP_DIR/postgres.yaml"

echo "⏳ Waiting for PostgreSQL to be ready..."
if kubectl get pods -l app=postgres -n "$K8S_NAMESPACE" --no-headers 2>/dev/null | grep -q "Running"; then
    echo "✅ PostgreSQL is already running"
else
    kubectl wait --for=condition=ready pod -l app=postgres -n "$K8S_NAMESPACE" --timeout=300s
fi

echo "🔍 Deploying/Updating Milvus vector database and dependencies..."
kubectl apply -f "$TEMP_DIR/milvus.yaml"

echo "⏳ Waiting for Milvus dependencies to be ready..."
if kubectl get pods -l app=etcd -n "$K8S_NAMESPACE" --no-headers 2>/dev/null | grep -q "Running"; then
    echo "✅ etcd is already running"
else
    kubectl wait --for=condition=ready pod -l app=etcd -n "$K8S_NAMESPACE" --timeout=300s
fi

if kubectl get pods -l app=minio -n "$K8S_NAMESPACE" --no-headers 2>/dev/null | grep -q "Running"; then
    echo "✅ MinIO is already running"
else
    kubectl wait --for=condition=ready pod -l app=minio -n "$K8S_NAMESPACE" --timeout=300s
fi

echo "⏳ Waiting for Milvus to be ready..."
if kubectl get pods -l app=milvus -n "$K8S_NAMESPACE" --no-headers 2>/dev/null | grep -q "Running"; then
    echo "✅ Milvus is already running"
else
    kubectl wait --for=condition=ready pod -l app=milvus -n "$K8S_NAMESPACE" --timeout=600s
fi

# Deploy application services (idempotent)
echo "🐍 Deploying/Updating Django backend..."
kubectl apply -f "$TEMP_DIR/backend.yaml"

echo "⏳ Waiting for backend to be ready..."
if kubectl get pods -l app=backend -n "$K8S_NAMESPACE" --no-headers 2>/dev/null | grep -q "Running"; then
    echo "✅ Backend is already running"
else
    kubectl wait --for=condition=ready pod -l app=backend -n "$K8S_NAMESPACE" --timeout=300s
fi

echo "⚛️  Deploying/Updating Svelte frontend..."
kubectl apply -f "$TEMP_DIR/frontend.yaml"

echo "⏳ Waiting for frontend to be ready..."
if kubectl get pods -l app=frontend -n "$K8S_NAMESPACE" --no-headers 2>/dev/null | grep -q "Running"; then
    echo "✅ Frontend is already running"
else
    kubectl wait --for=condition=ready pod -l app=frontend -n "$K8S_NAMESPACE" --timeout=300s
fi

# Deploy management UIs (idempotent)
echo "🎛️  Deploying/Updating management UIs..."
kubectl apply -f "$TEMP_DIR/management-ui.yaml"

# Deploy ingress (if domain is configured) - idempotent
if [ "$DOMAIN_NAME" != "your-domain.com" ]; then
    echo "🌐 Deploying/Updating ingress configuration..."
    kubectl apply -f "$TEMP_DIR/ingress.yaml"
    
    echo ""
    echo "🌟 Access URLs:"
    echo "   📱 Application: https://$DOMAIN_NAME"
    echo "   🔧 Django Admin: https://$DOMAIN_NAME/admin/"
    echo "   🗄️  PgAdmin: https://admin.$DOMAIN_NAME/pgadmin"
    echo "   🔍 Attu (Milvus UI): https://admin.$DOMAIN_NAME/attu"
else
    echo "⚠️  Domain not configured, skipping ingress deployment."
    echo "   You can access services via port-forwarding."
fi

# Cleanup temporary files
rm -rf "$TEMP_DIR"

# Show status
echo ""
echo "✅ AI Catalogue deployed successfully to Kubernetes!"
echo ""
echo "📋 Deployment Status:"
kubectl get pods -n "$K8S_NAMESPACE" -o wide

echo ""
echo "🔗 Services:"
kubectl get services -n "$K8S_NAMESPACE"

if [ "$DOMAIN_NAME" = "your-domain.com" ]; then
    echo ""
    echo "🔧 Port Forwarding Commands (for local access):"
    echo "   Frontend:  kubectl port-forward -n $K8S_NAMESPACE service/frontend-service 3000:3000"
    echo "   Backend:   kubectl port-forward -n $K8S_NAMESPACE service/backend-service 8000:8000"
    echo "   PgAdmin:   kubectl port-forward -n $K8S_NAMESPACE service/pgadmin-service 8080:8080"
    echo "   Attu:      kubectl port-forward -n $K8S_NAMESPACE service/attu-service 3001:3001"
fi

echo ""
echo "📝 To view logs:"
echo "   All pods:      kubectl logs -n $K8S_NAMESPACE -l app=backend -f"
echo "   Backend:       kubectl logs -n $K8S_NAMESPACE deployment/backend -f"
echo "   Frontend:      kubectl logs -n $K8S_NAMESPACE deployment/frontend -f"
echo "   PostgreSQL:    kubectl logs -n $K8S_NAMESPACE deployment/postgres -f"
echo "   Milvus:        kubectl logs -n $K8S_NAMESPACE deployment/milvus -f"

echo ""
echo "🔐 Database Connection Info:"
echo "   Host: postgres-service.$K8S_NAMESPACE.svc.cluster.local"
echo "   Database: $DB_NAME"
echo "   Username: $DB_USER"
echo ""
echo "🔐 Milvus Connection Info:"
echo "   Host: milvus-service.$K8S_NAMESPACE.svc.cluster.local"
echo "   Port: 19530"
echo "   Username: $MILVUS_ROOT_USER"
echo ""
echo "⚠️  First deployment may take longer as images are pulled and containers initialize."
echo "🔐 Remember to configure your domain DNS to point to your cluster's ingress IP."