# Public Chatbot Integration Guide

## 🚀 Zero-Impact Implementation Complete

This public chatbot implementation is **completely isolated** from your existing AI Catalogue system with **ZERO impact** on your sophisticated infrastructure.

## 🔒 Security Architecture

### Isolation Strategy
- **ChromaDB**: Separate vector database (port 8001) - NO access to your Milvus data
- **Models**: Independent tables with `public_chatbot_` prefix - NO foreign keys to your models
- **API Keys**: Uses system-level keys only - NO access to project-specific encrypted keys
- **Processing**: Completely separate service layer - NO impact on your existing workflows

### Security Features
- ✅ Prompt injection detection
- ✅ Rate limiting (10/min, 100/day per IP)
- ✅ Input sanitization and validation
- ✅ IP-based blocking for abuse
- ✅ Security violation tracking
- ✅ CORS control for approved domains

## 📋 Installation Steps

### 1. Add App to Settings
```python
# backend/core/settings.py
INSTALLED_APPS = [
    # ... your existing apps ...
    'public_chatbot',  # Add this line - ZERO impact on existing apps
]

# Optional: Add CORS settings for production
CORS_ALLOWED_ORIGINS = [
    "https://your-trusted-domain.com",
    "https://partner-site.org",
    # Add approved domains that will embed the chatbot
]

# Optional: ChromaDB settings
CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
CHROMA_PORT = os.getenv('CHROMA_PORT', '8001')  # Different from your services
```

### 2. Add URL Pattern
```python
# backend/core/urls.py
from django.urls import path, include

urlpatterns = [
    # ... your existing URLs ...
    path('api/public-chatbot/', include('public_chatbot.urls')),  # Add this line
    # ... rest of your URLs remain unchanged ...
]
```

### 3. Install Dependencies
```bash
# In your backend directory
pip install chromadb==0.4.24
pip install django-ratelimit  # Optional, has fallback
```

### 4. Run Migrations
```bash
# Create isolated tables (no impact on existing schema)
python manage.py makemigrations public_chatbot
python manage.py migrate public_chatbot
```

### 5. Start ChromaDB Container
```bash
# Start isolated ChromaDB container
docker-compose -f docker-compose-chroma-addon.yml up -d

# Verify it's running
curl http://localhost:8001/api/v1/heartbeat
```

### 6. Initialize Sample Knowledge
```bash
# Create sample knowledge base for testing
python manage.py init_sample_knowledge

# Sync to ChromaDB
python manage.py sync_public_knowledge
```

## 🧪 Testing the API

### Basic Test
```bash
curl -X POST http://localhost:8000/api/public-chatbot/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is artificial intelligence?"}'
```

### Expected Response
```json
{
  "status": "success",
  "response": "Artificial Intelligence (AI) refers to the development of computer systems that can perform tasks that typically require human intelligence...",
  "metadata": {
    "request_id": "pub_20241221_143022_1234",
    "timestamp": "2024-12-21T14:30:22.123Z",
    "response_time_ms": 1250,
    "provider_used": "openai",
    "model_used": "gpt-3.5-turbo",
    "context_sources": 1,
    "tokens_used": 85
  },
  "sources": [
    {
      "title": "Artificial Intelligence Basics",
      "source": "Public Knowledge Base",
      "category": "technology",
      "relevance_score": 0.92,
      "excerpt": "Artificial Intelligence (AI) refers to the development of computer systems..."
    }
  ]
}
```

### Health Check
```bash
curl http://localhost:8000/api/public-chatbot/health/
```

## 🎛️ Admin Interface

Access the admin at: `/admin/`

**Available Management:**
- **Chat Requests**: Monitor API usage and responses
- **IP Usage Limits**: Track and manage rate limiting
- **Knowledge Documents**: Manage public knowledge base
- **Configuration**: Control chatbot settings

## 📊 Monitoring & Analytics

### Built-in Tracking
- Request/response metrics
- IP-based usage analytics  
- LLM provider performance
- ChromaDB search performance
- Security violation alerts

### Database Tables Created
```
public_chatbot_requests     - API request tracking
public_chatbot_ip_limits    - Rate limiting and security
public_chatbot_knowledge    - Public knowledge documents
public_chatbot_config       - Global configuration
```

## 🔧 Configuration Options

### Environment Variables
```bash
# ChromaDB settings
CHROMA_HOST=localhost
CHROMA_PORT=8001

# LLM settings (uses your existing keys)
OPENAI_API_KEY=your_system_key
GOOGLE_API_KEY=your_system_key  
ANTHROPIC_API_KEY=your_system_key
```

### Admin Configuration
- Rate limits per IP (default: 10/min, 100/day)
- Max message length (default: 500 chars)
- LLM provider selection
- Security scanning toggles
- Maintenance mode

## 🚀 Production Deployment

### 1. Update CORS Settings
```python
CORS_ALLOWED_ORIGINS = [
    "https://your-production-domain.com",
    # Add all approved domains
]
```

### 2. Configure Rate Limiting
```python
# In admin interface or via code:
ChatbotConfiguration.objects.update(
    daily_requests_per_ip=50,  # Stricter for production
    hourly_requests_per_ip=10,
    enable_security_scanning=True,
    block_suspicious_ips=True
)
```

### 3. SSL/HTTPS
The endpoint works with your existing Nginx/SSL setup - no changes needed.

### 4. Monitoring
- Use your existing logging infrastructure
- Monitor ChromaDB container health
- Set up alerts for high error rates

## 🛡️ Security Compliance

### Data Isolation
- ✅ NO access to your private Milvus collections
- ✅ NO access to user projects or documents  
- ✅ NO foreign keys to existing models
- ✅ Separate vector database with public data only

### Privacy
- ✅ Messages truncated in logs (first 100 chars)
- ✅ No full conversation storage by default
- ✅ Configurable data retention policies

### Rate Limiting
- ✅ Per-IP request limits
- ✅ Token usage tracking
- ✅ Automatic IP blocking for abuse
- ✅ Security violation alerts

## 🔄 Maintenance

### Adding Knowledge
1. Create `PublicKnowledgeDocument` in admin
2. Set `is_approved=True` and `security_reviewed=True`
3. Run: `python manage.py sync_public_knowledge`

### Monitoring Performance
```bash
# Check ChromaDB health
curl http://localhost:8001/api/v1/heartbeat

# Check API health  
curl http://localhost:8000/api/public-chatbot/health/

# View recent requests in admin
# /admin/public_chatbot/publicchatrequest/
```

### Scaling
- ChromaDB container can be scaled independently
- No impact on your main Milvus performance
- Separate resource limits and monitoring

## ❓ Troubleshooting

### ChromaDB Connection Issues
```bash
# Check container status
docker-compose -f docker-compose-chroma-addon.yml ps

# View logs
docker logs ai_catalogue_chroma_public

# Restart if needed
docker-compose -f docker-compose-chroma-addon.yml restart chroma_public
```

### API Not Responding
1. Check Django logs for errors
2. Verify URL configuration
3. Test ChromaDB connection
4. Check rate limiting status

### No Knowledge Results
1. Verify documents are approved in admin
2. Run sync command: `python manage.py sync_public_knowledge`
3. Check ChromaDB collection stats

## 🎯 Success Metrics

Your implementation provides:
- **Complete isolation** from existing system
- **Zero downtime** deployment
- **Enterprise security** with rate limiting
- **Scalable architecture** with separate containers
- **Comprehensive monitoring** and admin interface
- **Production-ready** with SSL, CORS, logging

The public chatbot is now ready to serve third-party websites while keeping your sophisticated AI Catalogue system completely secure and isolated!