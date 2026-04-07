⏺ AI Catalogue Setup Summary

  🐳 Docker Development Setup

  Core Architecture

  - Backend: Django REST API with authentication, vector search, and LLM integration
  - Frontend: SvelteKit with Hot Module Replacement (HMR) for development
  - Database: PostgreSQL for relational data
  - Vector Database: Milvus v2.5.15 with authentication enabled
  - Object Storage: MinIO for Milvus data persistence
  - Reverse Proxy: Nginx for production routing
  - Management UIs: PgAdmin, Attu (Milvus UI)

  Authentication Configuration

  # .env - Secure credentials from environment
  MILVUS_ROOT_USER=milvusadmin
  MILVUS_ROOT_PASSWORD=YourSecureMilvusPassword123!
  MINIO_ROOT_USER=minioadmin
  MINIO_ROOT_PASSWORD=SecureMinioPassword123!
  PGADMIN_EMAIL=admin@yourdomain.com
  PGADMIN_PASSWORD=SecurePgAdminPassword123!

  Key Docker Components

  Milvus (Authenticated):
  environment:
    COMMON_SECURITY_AUTHORIZATIONENABLED: "true"
    MILVUS_ROOT_USER: ${MILVUS_ROOT_USER}
    MILVUS_ROOT_PASSWORD: ${MILVUS_ROOT_PASSWORD}
    MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}  # Modern compatibility
    MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
  healthcheck:
    start_period: 300s  # 5-minute startup for authentication

  Development Startup:
  # Enhanced development script
  ./scripts/start-dev.sh
  # - Intelligent health checking (5-minute timeout)
  # - Authentication-aware messaging
  # - Hot reload for both frontend/backend

  Access URLs

  - Application: http://localhost (via Nginx)
  - Frontend Dev: http://localhost:5173 (direct HMR)
  - Backend API: http://localhost:8000
  - Django Admin: http://localhost:8000/admin/
  - PgAdmin: http://localhost:8080
  - Attu (Milvus UI): http://localhost:3001 (requires manual auth)
  - Milvus API: http://localhost:9091

  ---
  ☁️ Azure Kubernetes Service (AKS) Setup

  Production Architecture

  - Managed Kubernetes: AKS with 3-node cluster (Standard_D4s_v3)
  - Container Registry: Azure Container Registry (ACR)
  - Database: Azure Database for PostgreSQL Flexible Server
  - Storage: Azure Premium SSD for persistent volumes
  - Networking: Azure Application Gateway for ingress
  - Security: Azure Key Vault for secrets management

  Azure Resource Configuration

  # Core Azure Settings (.env)
  AZURE_RESOURCE_GROUP=AIMLCC-DEV-RG
  AZURE_LOCATION=uksouth
  AKS_CLUSTER_NAME=aks-ai-catalogue
  AKS_NODE_COUNT=3
  AKS_NODE_SIZE=Standard_D4s_v3

  # Container Registry
  AZURE_CONTAINER_REGISTRY=aicatalogueacr
  ACR_LOGIN_SERVER=aicatalogueacr.azurecr.io

  # Managed PostgreSQL
  AZURE_POSTGRES_SERVER=ai-catalogue-db-server
  AZURE_POSTGRES_SKU=Standard_D2s_v3
  AZURE_POSTGRES_STORAGE=128

  Kubernetes Authentication Setup

  Milvus Production Config:
  # k8s/base/milvus.yaml
  env:
  - name: COMMON_SECURITY_AUTHORIZATIONENABLED
    value: "true"
  - name: MILVUS_ROOT_USER
    valueFrom:
      secretKeyRef:
        name: ai-catalogue-secrets
        key: MILVUS_ROOT_USER
  - name: MILVUS_ROOT_PASSWORD
    valueFrom:
      secretKeyRef:
        name: ai-catalogue-secrets
        key: MILVUS_ROOT_PASSWORD
  livenessProbe:
    initialDelaySeconds: 300  # 5-minute startup
    periodSeconds: 45
    timeoutSeconds: 30
    failureThreshold: 15

  Deployment Strategy

  # Production deployment sequence
  1. Infrastructure: ./k8s/setup-azure-infrastructure.sh
  2. Secrets: kubectl apply -f k8s/overlays/production/secrets.yaml
  3. Storage: kubectl apply -f k8s/base/storage.yaml
  4. Database: kubectl apply -f k8s/base/postgres.yaml
  5. Milvus: kubectl apply -f k8s/base/milvus.yaml (with auth)
  6. Backend: kubectl apply -f k8s/overlays/production/backend.yaml
  7. Frontend: kubectl apply -f k8s/overlays/production/frontend.yaml
  8. Ingress: kubectl apply -f k8s/overlays/production/ingress.yaml

  Production Features

  - Auto-scaling: HPA (2-10 replicas, 70% CPU target)
  - SSL/TLS: Let's Encrypt certificates
  - Monitoring: Prometheus + Grafana
  - Logging: Azure Log Analytics integration
  - Security: Network policies, RBAC, Key Vault integration

  Environment Compatibility

  Both Docker and Kubernetes configurations:
  - ✅ Use identical environment variables from .env
  - ✅ Support same authentication credentials
  - ✅ Share health check timing (5-minute Milvus startup)
  - ✅ Compatible with backend/core/settings.py Milvus config
  - ✅ Use same image tags and versions

  The setup ensures seamless progression from local Docker development to production AKS deployment with consistent authentication and
  security configurations.

