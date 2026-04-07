# AI Catalogue - Containerized Setup

This document provides complete instructions for running the AI Catalogue application using Docker containers.

## 📋 Prerequisites

- **Docker** (version 20.10 or later)
- **Docker Compose** (version 2.0 or later)
- **Git** (for cloning the repository)
- At least **8GB RAM** available for Docker
- At least **20GB** free disk space

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <your-repository-url>
cd ai_catalogue
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit the .env file with your configuration
nano .env  # or use your preferred editor
```

**Important:** Set your API keys in the `.env` file:
- `GOOGLE_API_KEY` - For PDF/document processing with Gemini
- `OPENAI_API_KEY` - For content summarization
- `ANTHROPIC_API_KEY` - For advanced AI features

### 3. Start the Application

#### Production Mode
```bash
./scripts/start.sh
```

#### Development Mode (with hot reload)
```bash
./scripts/start-dev.sh
```

### 4. Access the Application

- **Main Application**: http://localhost
- **Django Admin**: http://localhost/admin/
- **PgAdmin**: http://localhost:8080
- **Milvus Admin**: http://localhost:9091

## 🏗️ Architecture Overview

The containerized setup includes the following services:

### Core Services
- **Frontend** (SvelteKit) - Port 3000
- **Backend** (Django) - Port 8000
- **Nginx** (Reverse Proxy) - Port 80/443

### Databases
- **PostgreSQL** - Port 5432 (User data, projects, workflows)
- **Milvus** - Port 19530 (Vector embeddings, semantic search)
- **Etcd** - Port 2379 (Milvus metadata)
- **MinIO** - Port 9000 (Milvus object storage)

### Management
- **PgAdmin** - Port 8080 (Database administration)

## 🔧 Configuration

### Environment Variables

Key environment variables in `.env`:

```bash
# Database Configuration
DB_NAME=ai_catalogue_db
DB_USER=ai_catalogue_user
DB_PASSWORD=ai_catalogue_password
DB_HOST=postgres
DB_PORT=5432

# Milvus Configuration
MILVUS_HOST=milvus
MILVUS_PORT=19530

# Django Configuration
DJANGO_SECRET_KEY=your-super-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,backend,frontend,nginx

# API Keys
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Security
API_KEY_ENCRYPTION_KEY=BvAnyMC4-7_2oomBc_PT5lfmZN_LGisAdcvSF1EOAPQ=
```

### Custom Configuration

1. **Database Settings**: Modify PostgreSQL credentials in `.env`
2. **API Keys**: Add your service provider API keys
3. **Security**: Generate new encryption keys for production
4. **Ports**: Modify port mappings in `docker-compose.yml` if needed

## 🛠️ Development

### Development Mode Features

- **Hot Reload**: Both frontend and backend automatically reload on code changes
- **Source Mounting**: Local code is mounted into containers
- **Debug Tools**: Django Debug Toolbar enabled
- **Direct Access**: Frontend dev server on port 5173, backend on port 8000

### Making Changes

1. **Frontend Changes**: Edit files in `./frontend/my-sveltekit-app/src/`
2. **Backend Changes**: Edit files in `./backend/`
3. **Dependencies**: Add to `package.json` (frontend) or `requirements.txt` (backend), then rebuild

### Rebuilding Containers

```bash
# Rebuild specific service
docker-compose build backend
docker-compose build frontend

# Rebuild all services
docker-compose build --no-cache
```

## 📊 Monitoring and Logs

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f milvus

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Container Status

```bash
# View running containers
docker-compose ps

# View resource usage
docker stats

# View networks
docker network ls
```

### Health Checks

All services include health checks:

```bash
# Check service health
docker-compose ps

# Manual health check
curl http://localhost/health
curl http://localhost:8000/admin/
```

## 🗄️ Data Management

### Volumes

The application uses Docker volumes for persistent data:

- `postgres_data` - PostgreSQL database
- `milvus_data` - Milvus vector database
- `etcd_data` - Etcd metadata
- `minio_data` - MinIO object storage
- `backend_media` - Uploaded files
- `backend_logs` - Application logs

### Backup

```bash
# Database backup
docker-compose exec postgres pg_dump -U ai_catalogue_user ai_catalogue_db > backup.sql

# Restore database
docker-compose exec -T postgres psql -U ai_catalogue_user ai_catalogue_db < backup.sql

# Volume backup
docker run --rm -v ai_catalogue_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz -C /data .
```

### Reset Environment

```bash
# Complete reset (DESTROYS ALL DATA)
./scripts/reset.sh

# Stop containers only
./scripts/stop.sh
```

## 🔒 Security

### Production Security

1. **Change Default Passwords**: Update all default passwords in `.env`
2. **Generate New Keys**: Create new Django secret key and encryption keys
3. **HTTPS**: Configure SSL certificates for Nginx
4. **Firewall**: Restrict access to necessary ports only
5. **Updates**: Regularly update base images

### Security Headers

Nginx is configured with security headers:
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

## 🚨 Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check logs
docker-compose logs <service-name>

# Check resource usage
docker system df
docker system prune -f
```

#### Database Connection Issues
```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready -U ai_catalogue_user

# Check Milvus
docker-compose exec milvus curl -f http://localhost:9091/healthz
```

#### Frontend Build Issues
```bash
# Clear frontend cache
docker-compose exec frontend-dev rm -rf node_modules .svelte-kit
docker-compose restart frontend-dev
```

#### Permission Issues
```bash
# Fix volume permissions
sudo chown -R $USER:$USER ./volumes
sudo chown -R $USER:$USER ./logs
```

### Performance Tuning

1. **Memory**: Increase Docker memory limit to 8GB+
2. **CPU**: Allocate multiple CPU cores to Docker
3. **Storage**: Use SSD storage for better performance
4. **Milvus**: Tune Milvus configuration for your hardware

### Debug Mode

Enable detailed debugging:

```bash
# Set in .env
DEBUG=True
DJANGO_DEBUG_TOOLBAR=True

# View detailed logs
docker-compose logs -f backend | grep -i error
```

## 📈 Scaling

### Horizontal Scaling

```bash
# Scale specific services
docker-compose up -d --scale backend=3
docker-compose up -d --scale frontend=2
```

### Load Balancing

Configure Nginx upstream for multiple backend instances:

```nginx
upstream backend {
    server backend_1:8000;
    server backend_2:8000;
    server backend_3:8000;
}
```

## 🔄 Updates and Maintenance

### Updating the Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Run migrations if needed
docker-compose exec backend python manage.py migrate
```

### Regular Maintenance

1. **Weekly**: Check logs and resource usage
2. **Monthly**: Update base images and dependencies
3. **Quarterly**: Security audit and backup verification

## 📞 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review logs for error messages
3. Check Docker resource allocation
4. Verify environment configuration
5. Ensure API keys are correctly set

---

**Note**: This containerized setup ensures consistent deployment across different environments while maintaining the full functionality of the AI Catalogue application.