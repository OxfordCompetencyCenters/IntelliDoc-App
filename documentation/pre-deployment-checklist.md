# Pre-Deployment Checklist for Azure Kubernetes

## 🎯 Status: ALMOST READY - Need 3 Quick Fixes

### ✅ Already Configured
- Azure Subscription ID: `bbeb7561-f822-4950-82f6-64dcae8a93ab`
- Azure Tenant ID: `cc95de1b-97f5-4f93-b4ba-fe68b852cf91`
- Resource names and locations: All set
- Database configuration: Complete

### 🚨 REQUIRED BEFORE DEPLOYMENT

#### 1. Create Service Principal (2 minutes)
```bash
az login
az ad sp create-for-rbac --name "ai-catalogue-sp" --role="Contributor" \
    --scopes="/subscriptions/bbeb7561-f822-4950-82f6-64dcae8a93ab"
```

#### 2. Update .env with Output from Above
```bash
# Replace these lines in .env:
AZURE_CLIENT_ID=your-azure-client-id          # Use "appId" from output
AZURE_CLIENT_SECRET=your-azure-client-secret  # Use "password" from output

# Also fix this line:
CONTAINER_REGISTRY=aicatalogueacr.azurecr.io  # Remove "your-registry."
```

#### 3. Generate New Django Secret (1 minute)
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Copy output to replace: `DJANGO_SECRET_KEY=your-super-secret-key-change-in-production`

### 📋 OPTIONAL (Can Configure Later)
- Domain name: Currently set to `your-domain.com` (works without real domain)
- Container registry credentials: Will be auto-configured by Azure
- SSL certificates: Auto-configured by cert-manager

### ✅ AFTER COMPLETING ABOVE
```bash
# Run these in order:
./k8s/scripts/azure-setup.sh   # Creates Azure infrastructure
./k8s/scripts/k8s-start.sh     # Deploys applications
```

## 🎉 You're 95% Ready!
Just need the service principal credentials and you're good to go!
