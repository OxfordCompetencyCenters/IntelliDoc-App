# AI Catalogue - Docker & Kubernetes Deployment Guide

This guide covers deploying the AI Catalogue application using Docker and Kubernetes. The application is designed to be cloud-native and container-ready.

## 🌐 Deployment Options

- ✅ **Local Development** (Docker Compose)
- ✅ **Kubernetes** (AKS, EKS, GKE, self-managed)
- ✅ **Docker Production** (Docker Compose with production overrides)

## 📋 Prerequisites

1. **Docker & Docker Compose** installed
2. **Kubernetes cluster** (for K8s deployment)
3. **kubectl** configured for your cluster
4. **Domain name** (optional, for custom domains)
5. **SSL certificates** (for production)

## 🐳 Docker Deployment

### 1. Local Development

```bash
# Start development environment with hot reload
./scripts/start-dev.sh

# Or manually with Docker Compose
cp .env.template .env
# Edit .env with your configuration
docker-compose up -d
```

### 2. Production Docker Deployment

```bash
# Copy production environment template
cp .env.template .env

# Edit .env for production:
ENVIRONMENT=production
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CORS_ALLOWED_ORIGINS=https://your-domain.com
DB_SSL_MODE=require

# Deploy with production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 3. Environment Configuration

Edit `.env` with your specific values:

```bash
# Database Configuration (use managed cloud databases in production)
DB_HOST=your-postgres-server.example.com
DB_NAME=ai_catalogue_db
DB_USER=your_db_user
DB_PASSWORD=your_secure_password
DB_SSL_MODE=require

# Vector Database
MILVUS_HOST=your-milvus-host.example.com
MILVUS_PORT=19530
MILVUS_ROOT_USER=milvus_admin
MILVUS_ROOT_PASSWORD=secure_milvus_password

# AI API Keys
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Security
DJANGO_SECRET_KEY=your-super-secure-django-secret-key
API_KEY_ENCRYPTION_KEY=your-secure-encryption-key

# Public URLs for CORS
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

## ☸️ Kubernetes Deployment

### 1. Create Kubernetes Manifests

Create the following Kubernetes manifests in a `k8s/` directory:

#### Namespace
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-catalogue
```

#### ConfigMap for Environment Variables
```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ai-catalogue-config
  namespace: ai-catalogue
data:
  ENVIRONMENT: "production"
  DEBUG: "False"
  DB_HOST: "postgresql.example.com"
  DB_NAME: "ai_catalogue_db"
  DB_PORT: "5432"
  MILVUS_HOST: "milvus.example.com"
  MILVUS_PORT: "19530"
  ALLOWED_HOSTS: "your-domain.com,www.your-domain.com"
  CORS_ALLOWED_ORIGINS: "https://your-domain.com"
```

#### Secret for Sensitive Data
```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: ai-catalogue-secrets
  namespace: ai-catalogue
type: Opaque
stringData:
  DB_PASSWORD: "your-secure-db-password"
  DJANGO_SECRET_KEY: "your-super-secure-django-secret-key"
  GOOGLE_API_KEY: "your-google-api-key"
  OPENAI_API_KEY: "your-openai-api-key"
  ANTHROPIC_API_KEY: "your-anthropic-api-key"
  API_KEY_ENCRYPTION_KEY: "your-secure-encryption-key"
  MILVUS_ROOT_PASSWORD: "your-milvus-password"
```

#### Backend Deployment
```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-catalogue-backend
  namespace: ai-catalogue
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ai-catalogue-backend
  template:
    metadata:
      labels:
        app: ai-catalogue-backend
    spec:
      containers:
      - name: backend
        image: your-registry/ai-catalogue-backend:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: ai-catalogue-config
        - secretRef:
            name: ai-catalogue-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /admin/
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /admin/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

#### Backend Service
```yaml
# k8s/backend-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-catalogue-backend-service
  namespace: ai-catalogue
spec:
  selector:
    app: ai-catalogue-backend
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP
```

#### Frontend Deployment
```yaml
# k8s/frontend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-catalogue-frontend
  namespace: ai-catalogue
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ai-catalogue-frontend
  template:
    metadata:
      labels:
        app: ai-catalogue-frontend
    spec:
      containers:
      - name: frontend
        image: your-registry/ai-catalogue-frontend:latest
        ports:
        - containerPort: 3000
        env:
        - name: NODE_ENV
          value: "production"
        - name: BACKEND_URL
          value: "http://ai-catalogue-backend-service:8000"
        - name: VITE_BACKEND_URL
          value: "https://your-domain.com/api"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

#### Frontend Service
```yaml
# k8s/frontend-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-catalogue-frontend-service
  namespace: ai-catalogue
spec:
  selector:
    app: ai-catalogue-frontend
  ports:
  - protocol: TCP
    port: 3000
    targetPort: 3000
  type: ClusterIP
```

#### Ingress
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-catalogue-ingress
  namespace: ai-catalogue
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: ai-catalogue-tls
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: ai-catalogue-backend-service
            port:
              number: 8000
      - path: /admin
        pathType: Prefix
        backend:
          service:
            name: ai-catalogue-backend-service
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ai-catalogue-frontend-service
            port:
              number: 3000
```

### 2. Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Apply configurations
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# Deploy applications
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml

# Setup ingress (if using)
kubectl apply -f k8s/ingress.yaml

# Check deployment status
kubectl get pods -n ai-catalogue
kubectl get services -n ai-catalogue
```

### 3. Horizontal Pod Autoscaling

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-catalogue-backend-hpa
  namespace: ai-catalogue
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-catalogue-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## 🔒 Security Best Practices

### 1. Secrets Management
- Use Kubernetes Secrets or cloud secret managers
- Never commit secrets to repositories
- Rotate secrets regularly

### 2. Network Security
```yaml
# k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ai-catalogue-network-policy
  namespace: ai-catalogue
spec:
  podSelector:
    matchLabels:
      app: ai-catalogue-backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: ai-catalogue-frontend
    ports:
    - protocol: TCP
      port: 8000
```

### 3. RBAC (Role-Based Access Control)
```yaml
# k8s/rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ai-catalogue-sa
  namespace: ai-catalogue
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: ai-catalogue
  name: ai-catalogue-role
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ai-catalogue-binding
  namespace: ai-catalogue
subjects:
- kind: ServiceAccount
  name: ai-catalogue-sa
  namespace: ai-catalogue
roleRef:
  kind: Role
  name: ai-catalogue-role
  apiGroup: rbac.authorization.k8s.io
```

## 📊 Monitoring & Logging

### 1. Health Checks
Both Docker and Kubernetes deployments include:
- **Liveness probes** - Restart unhealthy containers
- **Readiness probes** - Route traffic only to healthy pods
- **Startup probes** - Handle slow-starting containers

### 2. Logging
```yaml
# Add to container spec for centralized logging
volumeMounts:
- name: logs
  mountPath: /app/logs
volumes:
- name: logs
  emptyDir: {}
```

### 3. Metrics
The application exposes health endpoints:
- `/health/` - Basic health check
- `/metrics/` - Application metrics (if enabled)

## 🚨 Troubleshooting

### Common Docker Issues
```bash
# Check container logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Check container status
docker-compose ps

# Restart specific service
docker-compose restart backend
```

### Common Kubernetes Issues
```bash
# Check pod status
kubectl get pods -n ai-catalogue

# View pod logs
kubectl logs -f deployment/ai-catalogue-backend -n ai-catalogue

# Debug pod issues
kubectl describe pod <pod-name> -n ai-catalogue

# Check service endpoints
kubectl get endpoints -n ai-catalogue

# Scale deployment
kubectl scale deployment ai-catalogue-backend --replicas=3 -n ai-catalogue
```

### Database Connection Issues
```bash
# Test database connectivity from backend pod
kubectl exec -it <backend-pod-name> -n ai-catalogue -- python manage.py dbshell

# Check environment variables
kubectl exec -it <backend-pod-name> -n ai-catalogue -- env | grep DB_
```

## 📈 Scaling Considerations

### 1. Stateless Services
- Backend and frontend are stateless and can be scaled horizontally
- Use horizontal pod autoscaling for automatic scaling

### 2. Stateful Services
- PostgreSQL: Use managed cloud services or PostgreSQL operators
- Milvus: Consider Milvus cluster setup for high availability
- MinIO: Use cloud object storage (S3, Azure Blob, GCS)

### 3. Performance Optimization
```bash
# Production environment variables for better performance
WORKER_PROCESSES=auto
WORKER_CONNECTIONS=1000
DB_CONN_MAX_AGE=600
TOKENIZERS_PARALLELISM=false
```

## 🎉 Success!

Your AI Catalogue is now ready for production deployment with Docker and Kubernetes! Choose the deployment method that best fits your infrastructure and scaling needs.

For local development, use Docker Compose. For production and enterprise deployments, Kubernetes provides the best scalability, reliability, and management capabilities.