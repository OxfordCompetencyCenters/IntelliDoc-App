# AI Catalogue - Quick Start Guide

## 🚀 Getting Started with Docker

### Prerequisites
- Docker Desktop installed and running
- At least 8GB RAM available for Docker
- 20GB free disk space

### 1. Clone and Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd ai_catalogue

# Create environment file
cp .env.example .env
```

### 2. Configure Environment
Edit `.env` file and set your API keys:
```bash
# Required for full functionality
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 3. Start the Application

#### Option A: Production Mode
```bash
./scripts/start.sh
```

#### Option B: Development Mode (Hot Reload)
```bash
./scripts/start-dev.sh
```

### 4. Access the Application
- **Main App**: http://localhost
- **Django Admin**: http://localhost/admin/
- **Database Admin**: http://localhost:8080
- **Direct Backend** (dev): http://localhost:8000
- **Direct Frontend** (dev): http://localhost:5173

### 5. First Time Setup
1. Create a superuser account:
   ```bash
   docker-compose exec backend python manage.py createsuperuser
   ```
2. Visit http://localhost/admin/ to configure initial settings
3. Upload your first documents and start using the AI features!

### Troubleshooting

#### Container Issues
```bash
# View logs
docker-compose logs -f

# Restart services
./scripts/stop.sh
./scripts/start.sh

# Complete reset (removes all data)
./scripts/reset.sh
```

#### Build Issues
```bash
# Fix frontend dependencies
./scripts/fix-dependencies.sh

# Rebuild containers
docker-compose build --no-cache
```

---

**🎉 You're ready to go!** The AI Catalogue is now running in containers with all functionality preserved.