# Public Chatbot Architecture Documentation

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [System Isolation](#system-isolation)
3. [Components Deep Dive](#components-deep-dive)
4. [Configuration Guide](#configuration-guide)
5. [API Reference](#api-reference)
6. [Deployment Guide](#deployment-guide)
7. [Domain/Origin Management](#domainorigin-management) - **How to add new domains that can access the chatbot**
8. [Security Considerations](#security-considerations)
9. [Admin Guide](#admin-guide)
10. [Integration Points](#integration-points)
11. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The Public Chatbot is a completely isolated system from the main AI Catalogue application. It provides a public-facing API endpoint for chatbot interactions using ChromaDB for vector search and existing LLM infrastructure.

### Key Design Principles

1. **Complete Isolation**: Separate database tables, ChromaDB instance, and no foreign key dependencies on main system
2. **Safe Integration**: Uses existing LLM services without impacting project-specific configurations
3. **Public-Facing**: Designed for external access with proper CORS, rate limiting, and security
4. **Scalable**: Supports large documents, advanced chunking, and multiple embedding strategies

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Public Chatbot System                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │   Django     │      │   ChromaDB   │                   │
│  │   Models     │◄─────►│   Service    │                   │
│  └──────────────┘      └──────────────┘                   │
│         │                    │                             │
│         │                    │                             │
│         ▼                    ▼                             │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │   API Views  │      │  Vector      │                   │
│  │   (CORS)     │      │  Search      │                   │
│  └──────────────┘      └──────────────┘                   │
│         │                    │                             │
│         │                    │                             │
│         └─────────┬──────────┘                             │
│                   │                                         │
│                   ▼                                         │
│         ┌──────────────────┐                               │
│         │  LLM Service     │                               │
│         │  (System-level)  │                               │
│         └──────────────────┘                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │
         │ (Isolated - No FK dependencies)
         │
┌─────────────────────────────────────────────────────────────┐
│              Main AI Catalogue System                        │
│         (Completely Separate - No Impact)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## System Isolation

### Database Isolation

The Public Chatbot uses completely separate database tables with explicit table names:

- `public_chatbot_requests` - Request tracking
- `public_chatbot_ip_limits` - IP-based rate limiting
- `public_chatbot_knowledge` - Knowledge base documents
- `public_chatbot_config` - Global configuration

**No Foreign Keys**: The system intentionally avoids foreign key relationships to the main AI Catalogue models, ensuring complete isolation.

### ChromaDB Isolation

- Separate ChromaDB instance running in isolated Docker container
- Collection name: `public_knowledge_base`
- Metadata includes `isolation_level: 'public_only'`
- No connection to main Milvus system

### API Key Isolation

- Uses system-level API keys only (`AICC_CHATBOT_OPENAI_API_KEY`)
- No access to project-specific API keys
- Completely isolated from project API key management

### Network Isolation

- ChromaDB runs on separate port (8001 by default)
- Uses dedicated Docker network
- No shared volumes with main system

---

## Components Deep Dive

### 1. Models (Django)

#### PublicChatRequest
Tracks all public API requests with comprehensive metadata.

**Key Fields:**
- `request_id`: Unique identifier (format: `pub_YYYYMMDD_HHMMSS_xxxx`)
- `session_id`: Optional conversation tracking
- `ip_address`: Client IP for rate limiting
- `message_preview`: Privacy-safe truncated message (first 100 chars)
- `response_generated`: Boolean flag
- `chroma_search_time_ms`: ChromaDB search performance
- `llm_provider_used`: Which LLM provider handled the request
- `status`: success, error, blocked, rate_limited, security_violation

**Indexes:**
- Composite indexes on `ip_address + created_at`, `session_id + created_at`
- Single indexes on `status`, `llm_provider_used`, `origin_domain`

#### IPUsageLimit
Tracks IP-based usage limits and blocking.

**Key Features:**
- Daily limits: 100 requests per IP (configurable)
- Hourly limits: 20 requests per IP (configurable)
- Automatic blocking after 5 security violations
- Auto-reset of daily/hourly counters
- Geographic tracking (optional GeoIP)

**Methods:**
- `is_rate_limited()`: Check if IP is currently rate limited
- `increment_usage()`: Update usage counters
- `reset_daily_counts()`: Reset daily counters

#### PublicKnowledgeDocument
Admin-managed knowledge base documents for ChromaDB.

**Key Features:**
- `document_id`: Unique identifier (format: `pub_YYYYMMDD_xxxx`)
- `is_approved`: Admin approval flag
- `security_reviewed`: Security review flag
- `synced_to_chromadb`: Sync status
- `chromadb_id`: ChromaDB document ID
- `search_count`: Usage tracking
- `quality_score`: Content quality (0-100)

**Workflow:**
1. Admin uploads document → `is_approved=False`
2. Admin reviews and approves → `is_approved=True, security_reviewed=True`
3. Sync command runs → `synced_to_chromadb=True`
4. Document available for search

#### ChatbotConfiguration
Global configuration singleton (only one instance allowed).

**Key Settings:**
- Rate limiting: `daily_requests_per_ip`, `hourly_requests_per_ip`
- ChromaDB: `max_search_results`, `similarity_threshold`
- LLM: `default_llm_provider`, `default_model`, `max_response_tokens`
- System prompt: Customizable AI assistant behavior
- Feature flags: `enable_vector_search`, `enable_query_rephrasing`
- Security: `enable_security_scanning`, `block_suspicious_ips`

**Methods:**
- `get_config()`: Get or create singleton configuration

### 2. Services

#### PublicKnowledgeService
Isolated ChromaDB service for public chatbot.

**Key Features:**
- Singleton pattern for connection management
- Advanced chunking support (if available)
- Large chunk embedding strategies
- Smart sync with duplicate prevention
- Context-aware search with conversation history

**Initialization:**
```python
service = PublicKnowledgeService.get_instance()
# Automatically initializes:
# - ChromaDB client connection
# - Embedding function (SentenceTransformer)
# - Advanced chunker (if available)
# - Large chunk embedder (if available)
```

**Key Methods:**
- `search_knowledge(query, limit, conversation_context)`: Vector search with context
- `add_knowledge(documents, metadatas, ids)`: Add documents to ChromaDB
- `delete_knowledge(document_id)`: Delete document and all chunks
- `smart_sync_knowledge(...)`: Smart sync with update detection
- `document_exists_in_chromadb(document_id)`: Check existence

**Advanced Features:**
- Query rephrasing: Uses LLM to rephrase subsequent queries for better retrieval
- Context-aware search: Appends previous queries from conversation
- Large chunk support: Handles documents up to 4096 tokens

#### ChatbotSecurityService
Security validation and rate limiting.

**Key Features:**
- Input validation: Length, injection patterns, special characters
- Rate limiting: IP-based daily/hourly limits
- Security violation tracking
- Auto-blocking after violations

**Methods:**
- `validate_input(message, client_ip)`: Validate user input
- `check_rate_limit_exceeded(ip_address)`: Check rate limits

#### PublicLLMService
LLM integration using system-level API keys.

**Supported Providers:**
- OpenAI (with streaming support)
- Google Gemini
- Anthropic Claude

**Key Features:**
- System-level API keys only (no project access)
- Streaming support (OpenAI only)
- Fallback handling
- Token usage tracking

**Methods:**
- `generate_response(prompt, provider, model, ...)`: Generate response
- `get_available_providers()`: List available providers
- `health_check()`: Check provider health

### 3. Advanced Components

#### AdvancedTextChunker (`chunking.py`)
Professional text chunking system with multiple strategies.

**Chunking Strategies:**
- `SMALL_SEMANTIC`: 512 tokens, 50 overlap
- `MEDIUM_SEMANTIC`: 1024 tokens, 100 overlap
- `LARGE_SEMANTIC`: 2048 tokens, 750 overlap (default)
- `XLARGE_SEMANTIC`: 4096 tokens, 750 overlap
- `PARAGRAPH_BASED`: Natural paragraph breaks
- `SECTION_BASED`: Headers and sections
- `HYBRID`: Multiple strategies combined

**Features:**
- Sentence boundary preservation
- Overlap management
- Token estimation
- Optimal strategy recommendation

**Usage:**
```python
chunker = AdvancedTextChunker(ChunkStrategy.LARGE_SEMANTIC)
chunks = chunker.chunk_document(content, document_id, metadata)
```

#### LargeChunkEmbedder (`embedding_strategies.py`)
Advanced embedding system for large text chunks.

**Embedding Strategies:**
- `TRUNCATION`: Truncate to model limit
- `SLIDING_WINDOW`: Multiple overlapping windows (default)
- `HIERARCHICAL`: Summary + detail embeddings
- `MEAN_POOLING`: Average of chunk embeddings
- `MAX_POOLING`: Max of chunk embeddings
- `WEIGHTED_AVERAGE`: Weighted by chunk importance

**Supported Models:**
- `all-MiniLM-L6-v2`: 256 tokens, 384 dimensions (current)
- `all-mpnet-base-v2`: 384 tokens, 768 dimensions
- `multi-qa-mpnet-base-dot-v1`: 512 tokens, 768 dimensions (recommended)
- `paraphrase-multilingual-mpnet-base-v2`: 512 tokens, 768 dimensions

**Usage:**
```python
embedder = LargeChunkEmbedder(
    strategy=EmbeddingStrategy.SLIDING_WINDOW,
    use_enhanced_model=True
)
result = embedder.embed_large_text(text, metadata)
```

#### DocumentProcessor (`document_processor.py`)
File upload and format conversion.

**Supported Formats:**
- Text: `.txt`, `.md`, `.markdown`
- Microsoft Office: `.docx`, `.doc`
- PDF: `.pdf` (requires PyPDF2, pdfplumber)
- Web: `.html`, `.htm` (requires BeautifulSoup)
- Data: `.csv`, `.json`
- Excel: `.xlsx`, `.xls` (requires openpyxl)

**Features:**
- Automatic format detection
- Content extraction
- Title extraction
- Category detection
- Quality scoring
- Tag extraction

**Security:**
- File size limits (50MB per file, 200MB batch)
- Content validation
- Security scanning integration

#### DocumentSecurityValidator (`security.py`)
Comprehensive security validation for uploads.

**Validation Checks:**
- Dangerous file extensions (`.exe`, `.bat`, `.js`, etc.)
- Suspicious filename patterns (directory traversal, etc.)
- File size limits (type-specific)
- MIME type validation
- Content scanning (dangerous patterns, sensitive info)
- Batch constraints (max 50 files, 200MB total)

**Dangerous Patterns Detected:**
- JavaScript injection
- PHP code
- Shell execution
- API key exposure
- Private key exposure

### 4. Views/Endpoints

#### `/api/public-chatbot/` (POST)
Main chat API endpoint.

**Request:**
```json
{
  "message": "What is AI?",
  "session_id": "optional-session-id",
  "conversation": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ],
  "context_limit": 5
}
```

**Response:**
```json
{
  "status": "success",
  "response": "AI is...",
  "metadata": {
    "request_id": "pub_20250101_120000_xxxx",
    "timestamp": "2025-01-01T12:00:00Z",
    "response_time_ms": 1234,
    "provider_used": "openai",
    "model_used": "gpt-3.5-turbo",
    "context_sources": 3,
    "vector_search_enabled": true,
    "vector_search_used": true,
    "chromadb_search_time_ms": 45,
    "tokens_used": 150
  },
  "sources": [
    {
      "title": "Knowledge Entry",
      "source": "Public Knowledge Base",
      "category": "General",
      "relevance_score": 0.95,
      "excerpt": "..."
    }
  ]
}
```

**Features:**
- CORS support
- Rate limiting
- Security validation
- ChromaDB context search
- LLM response generation
- Request tracking

#### `/api/public-chatbot/stream/` (POST)
Streaming chat API using Server-Sent Events (SSE).

**Request:** Same as regular endpoint

**Response:** SSE stream with chunks:
```
data: {"type": "content", "content": "AI is", "request_id": "..."}

data: {"type": "content", "content": " a", "request_id": "..."}

data: {"type": "completion", "request_id": "...", "response_time_ms": 1234, "total_content": "AI is a...", "tokens_used": 150}

data: [DONE]
```

**Features:**
- Real-time streaming (OpenAI only)
- Same security and rate limiting
- Request tracking with completion data

#### `/api/public-chatbot/health/` (GET)
Health check endpoint for monitoring.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00Z",
  "components": {
    "chromadb": {
      "status": "healthy",
      "document_count": 150
    },
    "configuration": {
      "enabled": true,
      "maintenance_mode": false,
      "vector_search_enabled": true
    },
    "performance": {
      "requests_last_5min": 25
    }
  }
}
```

### 5. Middleware

#### PublicChatbotCORSMiddleware
Custom CORS middleware for public chatbot endpoints.

**Features:**
- Whitelist-based origin checking
- Null origin support (file:// protocol)
- Preflight request handling
- Streaming response support

**Allowed Origins:**
- `https://oxfordcompetencycenters.github.io`
- `https://aicc.uksouth.cloudapp.azure.com`
- `https://eng.ox.ac.uk`
- `https://oerc.ox.ac.uk`
- `http://localhost:3000`, `http://localhost:5173`, `http://localhost:8080`

**Priority:** Highest priority in middleware stack (before django-cors-headers)

> **Note:** For detailed information on adding new domains and configuring allowed origins, see the [Domain/Origin Management](#domainorigin-management) section.

### 6. Signals

#### Document Deletion Signals (`signals.py`)
Automatic ChromaDB cleanup when documents are deleted.

**Signal Handlers:**
- `pre_delete`: Delete from ChromaDB before Django deletion
- `post_delete`: Log successful deletion

**Features:**
- Automatic chunk cleanup
- Error handling (doesn't block Django deletion)
- Logging for debugging

### 7. Forms

#### BulkDocumentUploadForm (`forms.py`)
Simplified form for bulk document upload in Django admin.

**Fields:**
- `files`: Multiple file upload (MultipleFileField)
- `category`: Default category for all documents

**Supported Formats:**
- `.txt`, `.pdf`, `.docx`, `.html`, `.md`, `.csv`, `.json`

### 8. Management Commands

#### `sync_public_knowledge`
Sync approved knowledge documents to ChromaDB.

**Usage:**
```bash
python manage.py sync_public_knowledge
python manage.py sync_public_knowledge --force-sync
python manage.py sync_public_knowledge --category technical --limit 50
python manage.py sync_public_knowledge --dry-run
```

**Options:**
- `--force-sync`: Force sync all documents, even if already synced
- `--category`: Only sync documents from specific category
- `--limit`: Maximum number of documents to sync (default: 100)
- `--dry-run`: Show what would be synced without actually syncing

**Features:**
- Advanced chunking support
- Smart sync with duplicate prevention
- Progress reporting
- Error handling

#### `init_sample_knowledge`
Initialize sample public knowledge documents for testing.

**Usage:**
```bash
python manage.py init_sample_knowledge
python manage.py init_sample_knowledge --clear-existing
```

**Features:**
- Creates 6 sample documents across multiple categories
- Auto-approved for testing
- Provides next steps instructions

#### `test_bulk_upload`
Test bulk document upload functionality.

**Usage:**
```bash
python manage.py test_bulk_upload --create-samples
python manage.py test_bulk_upload --test-security
python manage.py test_bulk_upload --test-formats
```

**Features:**
- Creates sample files for testing
- Tests security validation
- Tests format processing
- Dependency checking

### 9. Admin Interface

#### PublicChatRequestAdmin
Admin interface for request tracking.

**Features:**
- List view with filters (status, provider, date)
- Search by request_id, IP, message
- Export to CSV/JSON
- Read-only (no manual creation/editing)
- Detailed fieldsets

**Actions:**
- Export selected as CSV
- Export ALL as CSV
- Export selected as JSON
- Export ALL as JSON

#### IPUsageLimitAdmin
Admin interface for IP usage tracking.

**Features:**
- List view with blocking status
- Filters for blocked IPs, violations
- Manual blocking/unblocking
- Usage statistics

#### PublicKnowledgeDocumentAdmin
Admin interface for knowledge documents.

**Features:**
- List view with approval/sync status
- Bulk upload button
- Approval workflow
- Immediate sync to ChromaDB
- Search and filtering

**Actions:**
- Approve selected documents
- Sync to ChromaDB immediately
- Mark for later sync

**Custom Views:**
- Bulk upload view (`/admin/public_chatbot/publicknowledgedocument/bulk-upload/`)

#### ChatbotConfigurationAdmin
Admin interface for global configuration.

**Features:**
- Singleton enforcement (only one config)
- Fieldsets for organization
- Status displays (vector search, query rephrasing)
- Audit trail (updated_by, timestamps)

---

## Configuration Guide

### Environment Variables

#### ChromaDB Configuration
```bash
CHROMADB_HOST=localhost          # ChromaDB container host
CHROMADB_PORT=8001               # ChromaDB container port
CHROMA_PUBLIC_PORT=8001          # External port mapping
```

#### LLM API Keys
```bash
# OpenAI (dedicated for public chatbot)
AICC_CHATBOT_OPENAI_API_KEY=sk-...

# System-level keys (shared with main system)
GOOGLE_API_KEY=...               # For Gemini
ANTHROPIC_API_KEY=...            # For Claude
```

#### Django Settings
```python
# In settings.py
INSTALLED_APPS = [
    ...
    'public_chatbot',  # Public Chatbot API
]

MIDDLEWARE = [
    'public_chatbot.middleware.cors.PublicChatbotCORSMiddleware',  # Highest priority
    ...
]

# CORS settings
CORS_ALLOWED_ORIGINS = [
    'https://oxfordcompetencycenters.github.io',
    'https://aicc.uksouth.cloudapp.azure.com',
    ...
]
```

### Django Settings Integration

The public chatbot is integrated into Django settings:

1. **App Registration**: `public_chatbot` in `INSTALLED_APPS`
2. **Middleware**: `PublicChatbotCORSMiddleware` at highest priority
3. **URL Routing**: `/api/public-chatbot/` in `urls.py`
4. **CORS Configuration**: Whitelist origins in `CORS_ALLOWED_ORIGINS`

### ChromaDB Connection Settings

ChromaDB connection is configured via environment variables:
- `CHROMADB_HOST`: Default `localhost`
- `CHROMADB_PORT`: Default `8000` (internal), `8001` (external)

Fallback to persistent local mode if HTTP connection fails:
- Path: `./chroma_public_db`
- Settings: `anonymized_telemetry=False`, `allow_reset=False`

### API Key Management

**System-Level Keys:**
- `AICC_CHATBOT_OPENAI_API_KEY`: Dedicated OpenAI key for public chatbot
- `GOOGLE_API_KEY`: Shared Gemini key
- `ANTHROPIC_API_KEY`: Shared Claude key

**Isolation:**
- No access to project-specific API keys
- Completely isolated from `project_api_keys` app
- Uses only system-level keys from environment/settings

### Feature Flags

Configured in `ChatbotConfiguration` model (Django admin):

- `is_enabled`: Global on/off switch
- `enable_vector_search`: Enable/disable ChromaDB search
- `enable_query_rephrasing`: Enable LLM-based query rephrasing
- `maintenance_mode`: Maintenance mode with custom message

---

## API Reference

### Authentication

**No Authentication Required**: Public chatbot is designed for unauthenticated public access.

**Rate Limiting**: IP-based rate limiting provides protection instead of authentication.

### Endpoints

#### POST `/api/public-chatbot/`

Main chat endpoint.

**Request Headers:**
```
Content-Type: application/json
Origin: https://oxfordcompetencycenters.github.io
```

**Request Body:**
```json
{
  "message": "What is artificial intelligence?",
  "session_id": "optional-session-id-for-conversation-tracking",
  "conversation": [
    {
      "role": "user",
      "content": "Tell me about AI"
    },
    {
      "role": "assistant",
      "content": "Artificial intelligence is..."
    }
  ],
  "context_limit": 5
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "response": "Artificial intelligence (AI) is...",
  "metadata": {
    "request_id": "pub_20250101_120000_xxxx",
    "timestamp": "2025-01-01T12:00:00Z",
    "response_time_ms": 1234,
    "provider_used": "openai",
    "model_used": "gpt-3.5-turbo",
    "context_sources": 3,
    "vector_search_enabled": true,
    "vector_search_used": true,
    "chromadb_search_time_ms": 45,
    "tokens_used": 150
  },
  "sources": [
    {
      "title": "AI Basics",
      "source": "Public Knowledge Base",
      "category": "Technology",
      "relevance_score": 0.95,
      "excerpt": "Artificial Intelligence (AI) refers to..."
    }
  ]
}
```

**Error Responses:**

- `400 Bad Request`: Invalid input, security violation
- `429 Too Many Requests`: Rate limit exceeded
- `503 Service Unavailable`: Service disabled or maintenance mode
- `500 Internal Server Error`: LLM or system error

#### POST `/api/public-chatbot/stream/`

Streaming chat endpoint (SSE).

**Request:** Same as regular endpoint

**Response:** Server-Sent Events stream

**Limitations:**
- Only supports OpenAI provider
- Requires `default_llm_provider` to be `openai`

#### GET `/api/public-chatbot/health/`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00Z",
  "components": {
    "chromadb": {
      "status": "healthy",
      "document_count": 150,
      "collection_name": "public_knowledge_base"
    },
    "configuration": {
      "enabled": true,
      "maintenance_mode": false,
      "vector_search_enabled": true,
      "daily_limit": 100,
      "hourly_limit": 20
    },
    "performance": {
      "requests_last_5min": 25
    }
  }
}
```

### Rate Limiting

**Daily Limits:**
- Default: 100 requests per IP per day
- Configurable in `ChatbotConfiguration`

**Hourly Limits:**
- Default: 20 requests per IP per hour
- Configurable in `ChatbotConfiguration`

**Response (429):**
```json
{
  "status": "error",
  "error": "Rate limit exceeded. Please try again later.",
  "retry_after": 3600,
  "request_id": "pub_..."
}
```

### Security Validation

**Input Validation:**
- Maximum message length: 500 characters (configurable)
- Prompt injection pattern detection
- Special character ratio checking

**Security Violations:**
- Auto-blocking after 5 violations
- 24-hour block duration
- Tracking in `IPUsageLimit` model

---

## Deployment Guide

### Docker Compose Setup

#### 1. Start ChromaDB Container

```bash
docker-compose -f docker-compose.yml -f docker-compose-chroma-addon.yml up -d chroma_public
```

**Configuration:**
- Image: `ghcr.io/chroma-core/chroma:0.4.24`
- Port: `8001:8000` (external:internal)
- Volume: `chroma_public_data`
- Network: `ai_catalogue_network`

#### 2. Environment Variables

Create `.env` file or set environment variables:

```bash
# ChromaDB
CHROMADB_HOST=chroma_public
CHROMADB_PORT=8000
CHROMA_PUBLIC_PORT=8001

# LLM API Keys
AICC_CHATBOT_OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...

# Django
DEBUG=False
ALLOWED_HOSTS=aicc.uksouth.cloudapp.azure.com,eng.ox.ac.uk
```

#### 3. Database Migrations

```bash
python manage.py migrate public_chatbot
```

#### 4. Initialize Sample Knowledge (Optional)

```bash
python manage.py init_sample_knowledge
```

#### 5. Sync Knowledge to ChromaDB

```bash
python manage.py sync_public_knowledge
```

### Network Configuration

**ChromaDB Network:**
- Container name: `ai_catalogue_chroma_public`
- Internal port: `8000`
- External port: `8001` (configurable via `CHROMA_PUBLIC_PORT`)
- Network: `ai_catalogue_network` (external)

**Django Connection:**
- Host: `chroma_public` (Docker) or `localhost` (local)
- Port: `8000` (internal) or `8001` (external)

### Volume Management

**ChromaDB Data:**
- Volume: `chroma_public_data`
- Mount point: `/chroma/chroma`
- Persistence: Enabled (`IS_PERSISTENT=TRUE`)

**Backup:**
```bash
docker run --rm -v ai_catalogue_chroma_public_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/chromadb_backup.tar.gz /data
```

**Restore:**
```bash
docker run --rm -v ai_catalogue_chroma_public_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/chromadb_backup.tar.gz -C /
```

### Health Monitoring

**Health Check Endpoint:**
```bash
curl https://your-domain.com/api/public-chatbot/health/
```

**ChromaDB Health:**
```bash
curl http://localhost:8001/api/v1/heartbeat
```

**Docker Health Check:**
- Interval: 30s
- Timeout: 10s
- Retries: 5
- Start period: 10s

### Scaling Considerations

**ChromaDB:**
- Resource limits: 1GB memory, 0.5 CPU
- Can scale horizontally with multiple instances
- Consider persistent storage for production

**Django:**
- Stateless design allows horizontal scaling
- Shared database for request tracking
- Consider Redis for rate limiting at scale

---

## Domain/Origin Management

This section explains how to configure which domains can access and deploy the Public Chatbot API.

### Current Allowed Domains

The Public Chatbot currently allows access from the following domains:

**Production Domains:**
- `https://oxfordcompetencycenters.github.io` - GitHub Pages deployment
- `https://aicc.uksouth.cloudapp.azure.com` - Azure cloud deployment
- `https://eng.ox.ac.uk` - Oxford Engineering domain
- `https://oerc.ox.ac.uk` - Oxford e-Research Centre domain

**Development/Local Domains:**
- `http://localhost:3000` - Local development (port 3000)
- `http://localhost:5173` - Local development (port 5173, Vite default)
- `http://localhost:8080` - Local development (port 8080)
- `http://127.0.0.1:3000` - Localhost alternative
- `http://127.0.0.1:5173` - Localhost alternative
- `http://127.0.0.1:8080` - Localhost alternative

**Special Cases:**
- `null` origin (file:// protocol) - Allowed with wildcard for local testing
- Empty origin - Allowed with wildcard for certain testing scenarios

### Adding New Domains

To add a new domain that can access the Public Chatbot, you need to update the allowed origins in **two locations**:

**1. Middleware Configuration** (`backend/public_chatbot/middleware/cors.py`):

```python
class PublicChatbotCORSMiddleware(MiddlewareMixin):
    # Allowed origins for public chatbot
    ALLOWED_ORIGINS = [
        'https://oxfordcompetencycenters.github.io',
        'https://aicc.uksouth.cloudapp.azure.com',
        'https://eng.ox.ac.uk',
        'https://oerc.ox.ac.uk',
        'http://localhost:3000',
        'http://localhost:5173',
        'http://localhost:8080',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:5173',
        'http://127.0.0.1:8080',
        # Add your new domain here:
        'https://your-new-domain.com',
        'https://subdomain.your-domain.com',
    ]
```

**2. Django Settings** (`backend/core/settings.py`):

```python
# CORS settings - Cloud-ready configuration with Public Chatbot support
cors_origins = os.getenv('CORS_ALLOWED_ORIGINS', 
    'http://localhost:5173,http://localhost:3000,'
    'https://oxfordcompetencycenters.github.io,'
    'https://eng.ox.ac.uk,https://oerc.ox.ac.uk,'
    'https://your-new-domain.com'  # Add here too
)
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]
```

**3. Environment Variables (Optional but Recommended):**

For production deployments, configure via environment variables:

```bash
# .env file or environment variables
CORS_ALLOWED_ORIGINS=https://oxfordcompetencycenters.github.io,https://aicc.uksouth.cloudapp.azure.com,https://your-new-domain.com
```

**After Making Changes:**
1. Restart Django server: `python manage.py runserver` (development) or restart your production server
2. Test the new domain by making a request from that origin
3. Check logs for CORS-related messages if issues occur

### Domain Configuration Best Practices

**1. Use HTTPS in Production:**
- Always use `https://` for production domains
- Never allow `http://` for production domains (security risk)

**2. Include Protocol:**
- Always include the protocol (`http://` or `https://`)
- Include port numbers if non-standard (e.g., `http://localhost:3000`)

**3. Exact Match Required:**
- Origins must match exactly (case-sensitive for domain part)
- `https://example.com` ≠ `https://Example.com`
- `https://example.com` ≠ `https://www.example.com` (unless both added)

**4. Subdomain Handling:**
- Each subdomain must be added separately
- `https://www.example.com` and `https://api.example.com` are different origins
- Consider adding all necessary subdomains

**5. Wildcard Domains:**
- The middleware does NOT support wildcard patterns like `https://*.example.com`
- Each domain must be explicitly listed
- For multiple subdomains, add each one individually

**6. Development vs Production:**
- Keep development domains (localhost) separate from production
- Consider using environment variables to switch between dev/prod lists
- Never expose localhost origins in production

### Deployment Configuration

**For New Domain Deployment:**

1. **Add Domain to Allowed Origins:**
   - Update `PublicChatbotCORSMiddleware.ALLOWED_ORIGINS`
   - Update `CORS_ALLOWED_ORIGINS` in settings
   - Update environment variables if used

2. **Update CSRF Trusted Origins** (if using CSRF protection):
   ```python
   # settings.py
   CSRF_TRUSTED_ORIGINS = [
       'https://your-new-domain.com',
       # ... other domains
   ]
   ```

3. **Update ALLOWED_HOSTS** (if domain hosts Django):
   ```python
   # settings.py
   ALLOWED_HOSTS = [
       'your-new-domain.com',
       'www.your-new-domain.com',
       # ... other hosts
   ]
   ```

4. **Restart Services:**
   - Restart Django application server
   - Restart any reverse proxy (nginx, etc.)
   - Clear any caches if applicable

5. **Test Configuration:**
   ```bash
   # Test from new domain
   curl -H "Origin: https://your-new-domain.com" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type" \
        -X OPTIONS \
        https://your-api-domain.com/api/public-chatbot/
   ```

6. **Verify in Browser:**
   - Open browser console on new domain
   - Make a test API call
   - Check for CORS errors
   - Verify `Access-Control-Allow-Origin` header in response

### Domain Verification Checklist

When adding a new domain, verify:

- [ ] Domain added to `PublicChatbotCORSMiddleware.ALLOWED_ORIGINS`
- [ ] Domain added to `CORS_ALLOWED_ORIGINS` in settings
- [ ] Domain added to environment variables (if used)
- [ ] Domain added to `CSRF_TRUSTED_ORIGINS` (if needed)
- [ ] Domain added to `ALLOWED_HOSTS` (if hosting Django)
- [ ] Server restarted after changes
- [ ] CORS preflight (OPTIONS) request succeeds
- [ ] Actual API request succeeds
- [ ] No CORS errors in browser console
- [ ] Response includes correct `Access-Control-Allow-Origin` header

### Troubleshooting Domain Issues

**Issue: "Origin not allowed" error**

**Solutions:**
1. Verify domain is in `ALLOWED_ORIGINS` list (exact match)
2. Check protocol (http vs https)
3. Check port number if non-standard
4. Verify middleware is loaded (check `MIDDLEWARE` in settings)
5. Check middleware order (should be first)
6. Review server logs for CORS debug messages

**Issue: CORS works in some browsers but not others**

**Solutions:**
1. Check browser-specific CORS handling
2. Verify credentials setting (some browsers stricter)
3. Check for mixed content (http/https issues)
4. Clear browser cache and cookies

**Issue: Preflight (OPTIONS) fails but POST works**

**Solutions:**
1. Verify OPTIONS method is allowed
2. Check `Access-Control-Allow-Methods` header
3. Verify `Access-Control-Allow-Headers` includes required headers
4. Check middleware handles OPTIONS requests correctly

---

## Security Considerations

### Input Validation

**Message Validation:**
- Maximum length: 500 characters
- Prompt injection pattern detection
- Special character ratio checking (< 30%)

**File Upload Security:**
- Dangerous extension blocking
- Filename pattern validation
- File size limits (50MB per file, 200MB batch)
- MIME type validation
- Content scanning for malicious patterns

### Rate Limiting

**IP-Based Limits:**
- Daily: 100 requests (configurable)
- Hourly: 20 requests (configurable)
- Automatic blocking after violations

**Implementation:**
- Django cache-based (simple)
- `IPUsageLimit` model (persistent)
- Automatic reset at day/hour boundaries

### CORS Security

**Whitelist Approach:**
- Only specific origins allowed
- Null origin support for file:// protocol
- Credentials: false for wildcard compatibility

**Headers:**
- `Access-Control-Allow-Origin`: Whitelisted origin
- `Access-Control-Allow-Methods`: GET, POST, OPTIONS
- `Access-Control-Allow-Headers`: Controlled list
- `Access-Control-Max-Age`: 86400 (24 hours)

### API Key Security

**Isolation:**
- System-level keys only
- No project-specific key access
- Dedicated OpenAI key for chatbot

**Storage:**
- Environment variables (recommended)
- Django settings (fallback)
- Never in code or version control

### Data Privacy

**Request Tracking:**
- Message preview: First 100 characters only
- No full conversation logging (unless enabled)
- IP address tracking for rate limiting only

**Response Data:**
- No PII in responses
- Sources include only public knowledge
- No user data stored

### ChromaDB Security

**Container Security:**
- Non-root user (1000:1000)
- Resource limits
- Network isolation
- No external exposure (internal network only)

**Data Security:**
- `ALLOW_RESET=FALSE`: Prevents API reset
- `ANONYMIZED_TELEMETRY=FALSE`: No telemetry
- Persistent storage with proper permissions

---

## Admin Guide

### Document Management

#### Uploading Documents

1. **Single Upload:**
   - Navigate to Django Admin → Public Knowledge Documents
   - Click "Add Public Knowledge Document"
   - Fill in title, content, category
   - Save (requires approval)

2. **Bulk Upload:**
   - Navigate to Public Knowledge Documents list
   - Click "📁 Bulk Upload Documents" button
   - Select multiple files (TXT, PDF, DOCX, HTML, MD, CSV, JSON)
   - Enter category
   - Submit
   - Documents created with `is_approved=False`

#### Approval Workflow

1. **Review Documents:**
   - Navigate to Public Knowledge Documents
   - Review content, quality, security
   - Check quality score

2. **Approve Documents:**
   - Select documents
   - Choose "Approve selected documents" action
   - Documents marked as `is_approved=True, security_reviewed=True`

3. **Sync to ChromaDB:**
   - Option 1: Select approved documents → "Sync to ChromaDB immediately"
   - Option 2: Run management command: `python manage.py sync_public_knowledge`

#### Document Status

**Status Indicators:**
- ✅ APPROVED: `is_approved=True, security_reviewed=True`
- ⏳ PENDING SECURITY: `is_approved=True, security_reviewed=False`
- ❌ NOT APPROVED: `is_approved=False`

**Sync Status:**
- ✅ SYNCED: `synced_to_chromadb=True, last_synced` timestamp
- ❌ ERROR: `sync_error` message
- ⏳ PENDING: `synced_to_chromadb=False`

### Configuration Management

#### Global Configuration

1. **Access Configuration:**
   - Navigate to Django Admin → Chatbot Configuration
   - Only one configuration instance allowed

2. **Key Settings:**
   - **Service Control**: Enable/disable, maintenance mode
   - **Rate Limiting**: Daily/hourly limits, message length
   - **ChromaDB**: Max results, similarity threshold
   - **LLM**: Provider, model, max tokens, system prompt
   - **Security**: Scanning, blocking, logging

3. **System Prompt:**
   - Customize AI assistant behavior
   - Define personality and response style
   - Supports multi-line text

### Request Tracking

#### Viewing Requests

1. **List View:**
   - Navigate to Django Admin → Public Chat Requests
   - Filter by status, provider, date
   - Search by request_id, IP, message

2. **Export Data:**
   - Select requests
   - Choose export action (CSV/JSON)
   - Includes all request metadata

#### IP Management

1. **View IP Usage:**
   - Navigate to Django Admin → IP Usage Limits
   - See daily/hourly counts
   - View blocking status

2. **Manual Blocking:**
   - Edit IP Usage Limit record
   - Set `is_blocked=True`
   - Set `blocked_until` timestamp
   - Add `block_reason`

### Analytics

**Key Metrics:**
- Total requests (from PublicChatRequest)
- Success rate (status='success')
- Average response time (response_time_ms)
- ChromaDB usage (chroma_context_used)
- LLM provider distribution (llm_provider_used)
- Top IPs (from IPUsageLimit)

**Export for Analysis:**
- Export requests as CSV/JSON
- Import into analytics tools
- Track trends over time

---

## Integration Points

### LLM Integration

**Provider Support:**
- OpenAI: Full support (including streaming)
- Google Gemini: Full support
- Anthropic Claude: Full support

**Integration Method:**
- Uses `PublicLLMService` class
- System-level API keys only
- No project-specific configuration access
- Safe isolation from main system

**System Prompt:**
- Configurable in Django admin
- Supports multi-line text
- Defines AI assistant behavior

### ChromaDB Integration

**Connection:**
- HTTP client to ChromaDB container
- Fallback to persistent local mode
- Automatic reconnection handling

**Collection:**
- Name: `public_knowledge_base`
- Embedding function: SentenceTransformer
- Metadata: Includes isolation markers

**Sync Process:**
- Management command: `sync_public_knowledge`
- Admin action: "Sync to ChromaDB immediately"
- Automatic on document approval (optional)

### Main System Integration

**Isolation Strategy:**
- Separate database tables
- No foreign key dependencies
- Separate ChromaDB instance
- System-level API keys only

**Shared Resources:**
- Django framework
- Database server (separate tables)
- LLM infrastructure (system-level keys)

**No Impact Areas:**
- Project-specific configurations
- User management
- Project API keys
- Milvus vector search
- Agent orchestration

---

## Troubleshooting

### Common Issues

#### ChromaDB Connection Failed

**Symptoms:**
- `ChromaDB service is not ready`
- `Failed to initialize ChromaDB service`

**Solutions:**
1. Check ChromaDB container is running:
   ```bash
   docker ps | grep chroma_public
   ```

2. Check ChromaDB health:
   ```bash
   curl http://localhost:8001/api/v1/heartbeat
   ```

3. Verify environment variables:
   ```bash
   echo $CHROMADB_HOST
   echo $CHROMADB_PORT
   ```

4. Check network connectivity:
   ```bash
   docker network inspect ai_catalogue_network
   ```

5. Review ChromaDB logs:
   ```bash
   docker logs ai_catalogue_chroma_public
   ```

#### No Search Results

**Symptoms:**
- Empty `sources` array in response
- `chroma_results_found: 0`

**Solutions:**
1. Check documents are synced:
   ```bash
   python manage.py sync_public_knowledge --dry-run
   ```

2. Verify documents are approved:
   - Django Admin → Public Knowledge Documents
   - Filter: `is_approved=True, security_reviewed=True`

3. Check similarity threshold:
   - Django Admin → Chatbot Configuration
   - Lower `similarity_threshold` if too high (default: 0.7)

4. Verify ChromaDB has documents:
   ```python
   from public_chatbot.services import PublicKnowledgeService
   service = PublicKnowledgeService.get_instance()
   stats = service.get_collection_stats()
   print(stats)  # Should show document_count > 0
   ```

#### Rate Limiting Issues

**Symptoms:**
- `429 Too Many Requests`
- `Rate limit exceeded`

**Solutions:**
1. Check IP limits:
   - Django Admin → IP Usage Limits
   - View `daily_request_count`, `hourly_request_count`

2. Adjust limits:
   - Django Admin → Chatbot Configuration
   - Increase `daily_requests_per_ip` or `hourly_requests_per_ip`

3. Unblock IP:
   - Django Admin → IP Usage Limits
   - Edit IP record
   - Set `is_blocked=False`, clear `blocked_until`

#### LLM Errors

**Symptoms:**
- `Unable to generate response`
- `LLM API error`

**Solutions:**
1. Check API keys:
   ```bash
   echo $AICC_CHATBOT_OPENAI_API_KEY
   ```

2. Verify provider availability:
   ```python
   from public_chatbot.llm_integration import PublicLLMService
   service = PublicLLMService()
   print(service.get_available_providers())
   ```

3. Check configuration:
   - Django Admin → Chatbot Configuration
   - Verify `default_llm_provider` and `default_model`

4. Review LLM service logs:
   - Check Django logs for LLM errors
   - Look for API key or quota issues

#### CORS Issues

**Symptoms:**
- `CORS policy blocked`
- `Origin not allowed`

**Solutions:**
1. Check allowed origins:
   - Django Admin → Check middleware configuration
   - Verify origin in `PublicChatbotCORSMiddleware.ALLOWED_ORIGINS`

2. Add origin to whitelist:
   - Edit `public_chatbot/middleware/cors.py`
   - Add origin to `ALLOWED_ORIGINS` list
   - Restart Django server

3. Check middleware order:
   - `settings.py` → `MIDDLEWARE`
   - `PublicChatbotCORSMiddleware` should be first

#### Document Sync Failures

**Symptoms:**
- `sync_error` in document record
- Documents not appearing in search

**Solutions:**
1. Check sync errors:
   - Django Admin → Public Knowledge Documents
   - Filter: Documents with `sync_error` not empty

2. Review error messages:
   - Click on document
   - Check `sync_error` field for details

3. Retry sync:
   - Select documents
   - Choose "Sync to ChromaDB immediately" action

4. Check ChromaDB connection:
   - Verify ChromaDB is running and accessible
   - Check network connectivity

### Debugging Tips

#### Enable Debug Logging

```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'public_chatbot': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

#### Test ChromaDB Connection

```python
from public_chatbot.services import PublicKnowledgeService

service = PublicKnowledgeService.get_instance()
print(f"Ready: {service.is_ready}")
print(f"Stats: {service.get_collection_stats()}")
print(f"Health: {service.health_check()}")
```

#### Test LLM Service

```python
from public_chatbot.llm_integration import PublicLLMService

service = PublicLLMService()
print(f"Available: {service.get_available_providers()}")
print(f"Health: {service.health_check()}")
```

#### Test Document Processing

```python
from public_chatbot.document_processor import DocumentProcessor
from django.core.files.uploadedfile import SimpleUploadedFile

processor = DocumentProcessor()
file = SimpleUploadedFile('test.txt', b'Test content')
result = processor.process_uploaded_files([file], 'test', 'admin')
print(result)
```

### Performance Optimization

#### ChromaDB Performance

1. **Collection Optimization:**
   - Use appropriate chunking strategy
   - Optimize similarity threshold
   - Limit search results

2. **Embedding Optimization:**
   - Use enhanced models for better quality
   - Consider GPU acceleration
   - Batch processing for large documents

#### Django Performance

1. **Database Optimization:**
   - Add indexes for frequent queries
   - Use select_related/prefetch_related
   - Consider connection pooling

2. **Caching:**
   - Cache configuration (ChatbotConfiguration)
   - Cache rate limit checks
   - Consider Redis for distributed caching

---

## Appendix

### File Structure

```
backend/public_chatbot/
├── __init__.py
├── apps.py                    # App configuration
├── models.py                  # Django models
├── views.py                   # API endpoints
├── urls.py                    # URL routing
├── services.py                # ChromaDB service
├── llm_integration.py         # LLM service
├── security.py                # Security validation
├── chunking.py                # Advanced chunking
├── embedding_strategies.py    # Embedding strategies
├── document_processor.py      # File processing
├── forms.py                   # Admin forms
├── signals.py                 # Django signals
├── admin.py                   # Django admin
├── middleware/
│   └── cors.py                # CORS middleware
└── management/
    └── commands/
        ├── sync_public_knowledge.py
        ├── init_sample_knowledge.py
        └── test_bulk_upload.py
```

### Dependencies

**Required:**
- Django 5.2+
- chromadb
- sentence-transformers
- openai (for OpenAI provider)
- google-generativeai (for Gemini provider)
- anthropic (for Claude provider)

**Optional (for document processing):**
- PyPDF2, pdfplumber (PDF)
- python-docx (Word)
- beautifulsoup4 (HTML)
- openpyxl (Excel)
- markdown (Markdown)

### Migration History

1. `0001_initial`: Initial models
2. `0002_add_system_prompt`: System prompt field
3. `0003_add_vector_search_toggle`: Vector search toggle
4. `0004_update_aicc_defaults`: AICC defaults update
5. `0005_chatbotconfiguration_enable_query_rephrasing_and_more`: Query rephrasing feature

### API Versioning

**Current Version:** 1.0

**Endpoints:**
- `/api/public-chatbot/` - Main chat API
- `/api/public-chatbot/stream/` - Streaming API
- `/api/public-chatbot/health/` - Health check

**Future Considerations:**
- Version prefix: `/api/v1/public-chatbot/`
- Backward compatibility
- Deprecation notices

---

## Conclusion

The Public Chatbot is a fully isolated, production-ready system for providing public-facing AI chatbot capabilities. It integrates safely with existing LLM infrastructure while maintaining complete separation from the main AI Catalogue system.

**Key Strengths:**
- Complete isolation from main system
- Advanced chunking and embedding strategies
- Comprehensive security and rate limiting
- Flexible configuration and admin interface
- Production-ready deployment

**Future Enhancements:**
- Multi-language support
- Advanced analytics dashboard
- Custom embedding models
- Enhanced conversation memory
- WebSocket support for real-time updates

---

*Last Updated: January 2025*
*Version: 1.0*
