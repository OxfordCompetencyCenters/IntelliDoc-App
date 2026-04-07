# 🤖 Public Chatbot Installation Guide

## Zero-Impact Installation for Your AI Catalogue

This guide installs a secure, isolated public chatbot API that has **ZERO impact** on your existing AI Catalogue system.

### 🔒 Security Guarantees

- ✅ Complete isolation from your existing authentication system
- ✅ Separate ChromaDB database (no access to your Milvus data)  
- ✅ Uses dedicated API key: `AICC_CHATBOT_OPENAI_API_KEY`
- ✅ No foreign keys or database connections to your models
- ✅ Rate limiting, prompt injection protection, and monitoring
- ✅ Completely separate from your project API keys and user system

---

## 📋 Installation Steps

### Step 1: Add Environment Variable

Add this to your `.env` file:

```bash
# Public Chatbot API Key (isolated from main system)
AICC_CHATBOT_OPENAI_API_KEY=sk-your-openai-api-key-here

# Optional: ChromaDB Port (defaults to 8001)
CHROMADB_PORT=8001
```

### Step 2: Build and Start Services

```bash
# Build the updated backend with public chatbot
docker-compose build backend

# Start ChromaDB container
docker-compose up -d chromadb

# Restart backend to include public chatbot
docker-compose restart backend
```

### Step 3: Run Django Migrations

```bash
# Create and run migrations for public chatbot
docker-compose exec backend python manage.py makemigrations public_chatbot
docker-compose exec backend python manage.py migrate public_chatbot
```

### Step 4: Initialize Sample Knowledge Base

```bash
# Install sample knowledge documents
docker-compose exec backend python manage.py init_sample_knowledge

# Sync to ChromaDB
docker-compose exec backend python manage.py sync_public_knowledge
```

### Step 5: Test the API

```bash
# Test the public chatbot endpoint
curl -X POST http://localhost:8000/api/public-chatbot/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is artificial intelligence?"}'
```

---

## 🌟 API Endpoints

### Public Chatbot API
- **URL:** `POST /api/public-chatbot/`
- **Authentication:** None required
- **Rate Limit:** 10/minute, 100/day per IP
- **Request:** `{"message": "Your question here"}`
- **Response:** `{"response": "AI generated response", "metadata": {...}}`

### Admin Interface
- **URL:** `/admin/public_chatbot/`
- **Features:** 
  - Manage knowledge base
  - Monitor conversations
  - View usage analytics
  - Security violation alerts

### Health Check
- **URL:** `GET /api/public-chatbot/health/`
- **Response:** Service status and ChromaDB connection health

---

## 🛠️ Management Commands

### Add Knowledge Documents
```bash
# Initialize sample documents
docker-compose exec backend python manage.py init_sample_knowledge --clear-existing

# Sync approved documents to ChromaDB
docker-compose exec backend python manage.py sync_public_knowledge --force-sync
```

### Monitor Usage
```bash
# Check ChromaDB collection stats
docker-compose exec backend python manage.py shell -c "
from public_chatbot.services import PublicKnowledgeService
service = PublicKnowledgeService.get_instance()
print(service.get_collection_stats())
"
```

---

## 📊 Container Architecture

```
┌─ AI Catalogue (Existing) ─┐    ┌─ Public Chatbot (New) ─┐
│                           │    │                        │
│ Django Backend:8000       │◄──►│ Same Django Process    │
│ Milvus:19530 (Private)    │    │ ChromaDB:8001 (Public) │
│ Your Auth System          │    │ No Authentication      │
│ Private Documents         │    │ Public Knowledge Only  │
│                           │    │                        │
└───────────────────────────┘    └────────────────────────┘
```

---

## 🔧 Troubleshooting

### ChromaDB Connection Issues
```bash
# Check ChromaDB container status
docker-compose ps chromadb

# View ChromaDB logs
docker-compose logs chromadb

# Test ChromaDB directly
curl http://localhost:8001/api/v1/heartbeat
```

### API Key Issues
```bash
# Verify environment variable is loaded
docker-compose exec backend python -c "import os; print('API Key:', 'LOADED' if os.getenv('AICC_CHATBOT_OPENAI_API_KEY') else 'MISSING')"
```

### Sync Issues
```bash
# Check sync status
docker-compose exec backend python manage.py sync_public_knowledge --dry-run

# Force resync all documents
docker-compose exec backend python manage.py sync_public_knowledge --force-sync
```

---

## 🚀 Production Considerations

### Security
- Set strong rate limits in production
- Monitor for prompt injection attempts  
- Regular security reviews of public knowledge
- Use dedicated OpenAI API key with usage limits

### Performance
- ChromaDB scales well for public knowledge
- Monitor API response times and adjust resources
- Consider CDN for high-traffic deployments

### Monitoring
- Enable logging in production
- Set up alerts for security violations
- Monitor ChromaDB disk usage and performance

---

## ✅ Verification Checklist

- [ ] ChromaDB container running on port 8001
- [ ] Public chatbot app added to INSTALLED_APPS
- [ ] URL pattern added to main urls.py
- [ ] Migrations created and applied
- [ ] Sample knowledge initialized and synced
- [ ] API responding to test requests
- [ ] Admin interface accessible
- [ ] Health check endpoint working

---

## 🆘 Support

If you encounter issues:
1. Check container logs: `docker-compose logs backend chromadb`
2. Verify environment variables are loaded
3. Ensure ChromaDB is healthy: `curl http://localhost:8001/api/v1/heartbeat`
4. Test database migrations are applied
5. Check admin interface for any configuration issues

The public chatbot is completely isolated and will not affect your existing AI Catalogue functionality.