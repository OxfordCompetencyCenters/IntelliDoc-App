#!/bin/bash

# AI Catalogue - Kubernetes Development Startup Script
# This script deploys the AI Catalogue application to Kubernetes in development mode

set -e

echo "🔧 Starting AI Catalogue on Kubernetes (Development Mode)..."

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
    echo "🔑 Especially set your Kubernetes configuration."
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Override for development
export K8S_NAMESPACE=${K8S_NAMESPACE_DEV:-ai-catalogue-dev}
export IMAGE_TAG=${IMAGE_TAG:-dev}
export DEVELOPMENT_MODE=true
export DEBUG=True

# Validate required variables
required_vars=(
    "K8S_NAMESPACE"
    "CONTAINER_REGISTRY"
    "STORAGE_CLASS_NAME"
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
echo "📝 Processing Kubernetes manifests for development..."

for yaml_file in k8s/base/*.yaml; do
    filename=$(basename "$yaml_file")
    substitute_env_vars "$yaml_file" "$TEMP_DIR/$filename"
done

# Create development namespace
echo "📦 Creating development namespace: $K8S_NAMESPACE"
kubectl apply -f "$TEMP_DIR/namespace.yaml"

# Apply secrets and configmaps (development versions)
echo "🔐 Applying development secrets and configuration..."
# Use development configmap
sed -i.bak "s/ai-catalogue-config/ai-catalogue-config-dev/g" "$TEMP_DIR/configmap.yaml"
sed -i.bak "s/ai-catalogue-secrets/ai-catalogue-secrets-dev/g" "$TEMP_DIR/secrets.yaml"
kubectl apply -f "$TEMP_DIR/secrets.yaml"
kubectl apply -f "$TEMP_DIR/configmap.yaml"

# Start databases with reduced resources for development
echo "🗄️  Deploying PostgreSQL database (development)..."
# Reduce postgres resources for dev
sed -i.bak 's/memory: "1Gi"/memory: "512Mi"/g' "$TEMP_DIR/postgres.yaml"
sed -i.bak 's/cpu: "500m"/cpu: "250m"/g' "$TEMP_DIR/postgres.yaml"
kubectl apply -f "$TEMP_DIR/postgres.yaml"

echo "⏳ Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n "$K8S_NAMESPACE" --timeout=300s

echo "🔍 Deploying Milvus vector database (development)..."
# Reduce milvus resources for dev  
sed -i.bak 's/memory: "2Gi"/memory: "1Gi"/g' "$TEMP_DIR/milvus.yaml"
sed -i.bak 's/cpu: "1000m"/cpu: "500m"/g' "$TEMP_DIR/milvus.yaml"
kubectl apply -f "$TEMP_DIR/milvus.yaml"

echo "⏳ Waiting for Milvus dependencies..."
kubectl wait --for=condition=ready pod -l app=etcd -n "$K8S_NAMESPACE" --timeout=300s || true
kubectl wait --for=condition=ready pod -l app=minio -n "$K8S_NAMESPACE" --timeout=300s || true
kubectl wait --for=condition=ready pod -l app=milvus -n "$K8S_NAMESPACE" --timeout=600s || true

# Deploy application services with development settings
echo "🐍 Deploying Django backend (development)..."
# Update backend to use dev image and settings
sed -i.bak "s/replicas: 2/replicas: 1/g" "$TEMP_DIR/backend.yaml"
sed -i.bak "s/ai-catalogue-config/ai-catalogue-config-dev/g" "$TEMP_DIR/backend.yaml"
sed -i.bak "s/ai-catalogue-secrets/ai-catalogue-secrets-dev/g" "$TEMP_DIR/backend.yaml"
kubectl apply -f "$TEMP_DIR/backend.yaml"

echo "⏳ Waiting for backend to be ready..."
kubectl wait --for=condition=ready pod -l app=backend -n "$K8S_NAMESPACE" --timeout=300s || true

echo "⚛️  Deploying Svelte frontend (development)..."
# Update frontend for dev
sed -i.bak "s/replicas: 2/replicas: 1/g" "$TEMP_DIR/frontend.yaml"
sed -i.bak "s/ai-catalogue-config/ai-catalogue-config-dev/g" "$TEMP_DIR/frontend.yaml"
kubectl apply -f "$TEMP_DIR/frontend.yaml"

echo "⏳ Waiting for frontend to be ready..."
kubectl wait --for=condition=ready pod -l app=frontend -n "$K8S_NAMESPACE" --timeout=300s || true

# Deploy management UIs
echo "🎛️  Deploying management UIs..."
kubectl apply -f "$TEMP_DIR/management-ui.yaml" || true

# Cleanup temporary files
rm -rf "$TEMP_DIR"

# Show status
echo ""
echo "✅ AI Catalogue Development Environment deployed to Kubernetes!"
echo ""
echo "📋 Development Deployment Status:"
kubectl get pods -n "$K8S_NAMESPACE" -o wide

echo ""
echo "🔗 Services:"
kubectl get services -n "$K8S_NAMESPACE"

echo ""
echo "🌟 Development Access (Port Forwarding):"
echo "   📱 Frontend:  kubectl port-forward -n $K8S_NAMESPACE service/frontend-service 3000:3000"
echo "   🐍 Backend:   kubectl port-forward -n $K8S_NAMESPACE service/backend-service 8000:8000"
echo "   🗄️  PgAdmin:   kubectl port-forward -n $K8S_NAMESPACE service/pgadmin-service 8080:8080"
echo "   🔍 Attu:      kubectl port-forward -n $K8S_NAMESPACE service/attu-service 3001:3001"

echo ""
echo "📝 Development Features:"
echo "   🔥 Reduced resource usage for local development"
echo "   🐛 Debug mode enabled"
echo "   📁 Single replica deployments"
echo "   🔍 Detailed logging enabled"

echo ""
echo "📝 To view logs:"
echo "   Backend:       kubectl logs -n $K8S_NAMESPACE deployment/backend -f"
echo "   Frontend:      kubectl logs -n $K8S_NAMESPACE deployment/frontend -f"
echo "   PostgreSQL:    kubectl logs -n $K8S_NAMESPACE deployment/postgres -f"
echo "   Milvus:        kubectl logs -n $K8S_NAMESPACE deployment/milvus -f"

echo ""
echo "🛠️  Development Tips:"
echo "   - Use port-forwarding to access services locally"
echo "   - Logs are available via kubectl logs commands"
echo "   - Scale deployments as needed: kubectl scale deployment backend --replicas=2 -n $K8S_NAMESPACE"

echo ""
echo "🔐 Database Connection Info:"
echo "   Host: postgres-service.$K8S_NAMESPACE.svc.cluster.local"  
echo "   Database: ${DB_NAME}_dev"
echo "   Username: $DB_USER"

echo ""
echo "⚠️  Development environment uses reduced resources and single replicas."
echo "🔄 To access services, run the port-forward commands above in separate terminals."