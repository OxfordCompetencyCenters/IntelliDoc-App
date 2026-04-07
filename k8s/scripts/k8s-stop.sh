#!/bin/bash

# AI Catalogue - Kubernetes Stop Script
# This script gracefully stops all AI Catalogue deployments in Kubernetes

set -e

echo "🛑 Stopping AI Catalogue Kubernetes deployments..."

# Check if kubectl is installed and configured
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Default namespace if not set
K8S_NAMESPACE=${K8S_NAMESPACE:-ai-catalogue}

# Check if namespace exists
if ! kubectl get namespace "$K8S_NAMESPACE" &> /dev/null; then
    echo "⚠️  Namespace $K8S_NAMESPACE does not exist or is not accessible."
    echo "Available namespaces:"
    kubectl get namespaces | grep ai-catalogue || echo "No AI Catalogue namespaces found."
    
    echo ""
    read -p "Enter namespace to stop (or press Enter to skip): " input_namespace
    if [ -n "$input_namespace" ]; then
        K8S_NAMESPACE=$input_namespace
    else
        echo "No namespace specified, exiting."
        exit 1
    fi
fi

# Function to scale down deployments gracefully
scale_down_deployment() {
    local deployment_name=$1
    echo "🔄 Scaling down $deployment_name..."
    
    if kubectl get deployment "$deployment_name" -n "$K8S_NAMESPACE" &> /dev/null; then
        kubectl scale deployment "$deployment_name" --replicas=0 -n "$K8S_NAMESPACE"
        kubectl wait --for=condition=available=false deployment/"$deployment_name" -n "$K8S_NAMESPACE" --timeout=120s || true
    else
        echo "   ⚠️  Deployment $deployment_name not found, skipping..."
    fi
}

# Function to delete resources safely
delete_resource() {
    local resource_type=$1
    local resource_name=$2
    
    if kubectl get "$resource_type" "$resource_name" -n "$K8S_NAMESPACE" &> /dev/null; then
        echo "🗑️  Deleting $resource_type/$resource_name..."
        kubectl delete "$resource_type" "$resource_name" -n "$K8S_NAMESPACE" --wait=true || true
    fi
}

# Scale down application services first
echo "🔄 Scaling down application services..."
scale_down_deployment "frontend"
scale_down_deployment "backend"

# Scale down management UIs
echo "🔄 Scaling down management services..."
scale_down_deployment "pgadmin"
scale_down_deployment "attu"

# Scale down databases (order matters)
echo "🔄 Scaling down database services..."
scale_down_deployment "milvus"
scale_down_deployment "postgres"
scale_down_deployment "minio"
scale_down_deployment "etcd"

# Wait a bit for graceful shutdown
echo "⏳ Waiting for pods to terminate gracefully..."
sleep 10

# Delete ingress first
echo "🌐 Removing ingress configurations..."
delete_resource "ingress" "ai-catalogue-ingress"
delete_resource "ingress" "ai-catalogue-admin-ingress"

# Delete services
echo "🔗 Removing services..."
kubectl delete services --all -n "$K8S_NAMESPACE" --wait=true || true

# Delete deployments
echo "📦 Removing deployments..."
kubectl delete deployments --all -n "$K8S_NAMESPACE" --wait=true || true

# Delete HPA
echo "📊 Removing autoscalers..."
kubectl delete hpa --all -n "$K8S_NAMESPACE" --wait=true || true

# Ask about persistent data
echo ""
echo "⚠️  Persistent volumes contain your data (database, uploads, etc.)"
echo "💾 Data is preserved unless you explicitly delete PVCs."
echo ""
read -p "Do you want to delete persistent volumes and ALL DATA? (y/N): " delete_data

if [[ $delete_data =~ ^[Yy]$ ]]; then
    echo "🗑️  Deleting persistent volume claims (THIS WILL DELETE ALL DATA)..."
    kubectl delete pvc --all -n "$K8S_NAMESPACE" --wait=true || true
    echo "❌ All data has been deleted!"
else
    echo "💾 Data preserved in persistent volumes."
fi

# Ask about ConfigMaps and Secrets
echo ""
read -p "Do you want to delete configuration and secrets? (y/N): " delete_config

if [[ $delete_config =~ ^[Yy]$ ]]; then
    echo "🗑️  Deleting configmaps and secrets..."
    kubectl delete configmaps --all -n "$K8S_NAMESPACE" --wait=true || true
    kubectl delete secrets --all -n "$K8S_NAMESPACE" --wait=true || true
    echo "🔐 Configuration and secrets deleted."
else
    echo "🔐 Configuration and secrets preserved."
fi

# Ask about namespace
echo ""
read -p "Do you want to delete the namespace '$K8S_NAMESPACE'? (y/N): " delete_namespace

if [[ $delete_namespace =~ ^[Yy]$ ]]; then
    echo "🗑️  Deleting namespace $K8S_NAMESPACE..."
    kubectl delete namespace "$K8S_NAMESPACE" --wait=true || true
    echo "📦 Namespace deleted."
else
    echo "📦 Namespace preserved."
fi

echo ""
echo "✅ AI Catalogue stopped successfully!"
echo ""
echo "📋 Remaining resources in namespace $K8S_NAMESPACE:"
kubectl get all -n "$K8S_NAMESPACE" 2>/dev/null || echo "Namespace may have been deleted or is empty."

if [[ ! $delete_data =~ ^[Yy]$ ]]; then
    echo ""
    echo "💾 Your data is preserved in persistent volumes:"
    kubectl get pvc -n "$K8S_NAMESPACE" 2>/dev/null || echo "No PVCs found."
fi

echo ""
echo "🔄 To restart AI Catalogue:"
echo "   Production: ./k8s/scripts/k8s-start.sh"
echo "   Development: ./k8s/scripts/k8s-start-dev.sh"
echo ""
echo "⚠️  Note: If you deleted data, you'll need to reinitialize the application."