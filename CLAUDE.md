# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Catalogue (AICC-IntelliDoc) — a full-stack AI document analysis platform. Users upload documents to projects, build visual agent workflows, execute them with LLM providers (OpenAI, Anthropic, Google), and evaluate results. Features include RAG via Milvus vector search (DocAware), web search with Redis caching, workflow deployments with human-in-the-loop, and LLM evaluation metrics (BLEU, ROUGE, BERTScore).

## Tech Stack

- **Backend**: Django 5.2 + Django REST Framework, PostgreSQL 15, Milvus 2.6 (vector DB), Redis 7
- **Frontend**: SvelteKit 2 + Svelte 5, Vite 6, Tailwind CSS, TypeScript, Axios
- **Auth**: JWT (SimpleJWT) with Bearer tokens
- **Realtime**: Django Channels (WebSocket) for workflow execution streaming
- **Infra**: Docker Compose (9 services), Nginx reverse proxy, optional Kubernetes (k8s/)

## Development Commands

### Full Stack (Docker — recommended)
```bash
cp .env.example .env          # Configure API keys and credentials
./scripts/start-dev.sh        # Start all services with hot reload (~8-12 min first run)
docker compose down            # Stop all services
```

### Deployment (after changes are live)
See `scripts/SCRIPTS.md` for the full decision table. Short version:
```bash
./scripts/quick-deploy.sh     # Code-only changes (.py/.svelte/.ts), ~2s downtime
./scripts/rebuild-deploy.sh   # New pip/npm packages or Dockerfile changes, ~10s downtime
./scripts/start-dev.sh        # Fresh infra (docker-compose changes, new DB version)
```

### Backend (standalone)
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
python manage.py setup_container_data   # Initialize demo data
```

### Frontend
```bash
cd frontend/my-sveltekit-app
npm install
npm run dev          # Dev server on http://localhost:5173
npm run build        # Production build
npm run check        # svelte-check type checking
npm run lint         # ESLint
```

### Database Migrations
```bash
cd backend
python manage.py makemigrations <app_name>
python manage.py migrate
```

## Architecture

### Backend Django Apps (backend/)
- **core/** — Settings, URL routing, WSGI/ASGI config. All API routes defined in `core/urls.py`.
- **users/** — Custom User model (`AUTH_USER_MODEL = 'users.User'`)
- **api/** — Core REST views, serializers, `UniversalProjectViewSet` (the unified project CRUD interface at `/api/projects/`)
- **agent_orchestration/** — The main orchestration engine:
  - `workflow_executor.py` — Executes workflow graphs node-by-node
  - `chat_manager.py` — LLM interaction and message handling
  - `consumers.py` — WebSocket consumers for streaming
  - `deployment_executor.py` — Production deployment execution with session persistence
  - `docaware/` — DocAware RAG: `service.py` (orchestrator), `search_methods.py` (semantic/hybrid/contextual search against Milvus)
  - `websearch_handler.py` / `websearch/cache_service.py` — External web search with Redis caching
  - `llm_urls.py`, `workflow_urls.py`, `deployment_urls.py` — App-level URL routing
- **vector_search/** — Milvus integration, document indexing and search
- **llm_eval/** — LLM comparison framework with providers in `providers/` (claude, openai, gemini)
- **templates/** — Project template system with dynamic URL registration
- **project_api_keys/** — Encrypted per-project API key storage (Fernet)
- **mcp_servers/** — Model Context Protocol server integration
- **public_chatbot/** — Isolated public-facing chatbot (separate CORS middleware)

### Frontend (frontend/my-sveltekit-app/src/)
- **routes/** — SvelteKit pages: `features/intellidoc/` (main project UI), `features/llm-eval/`, `admin/`, `login/`
- **lib/components/** — Svelte 5 components: `WorkflowDesigner.svelte` (visual graph editor), `AgentOrchestrationInterface.svelte` (execution UI), `NodePropertiesPanel.svelte`, `LLMConfigurationPanel.svelte`
- **lib/services/** — API clients: `cleanUniversalApi.ts` (unified API client), `workflowWebSocket.ts` (WebSocket), `docAwareService.ts`, `llmConfigService.ts`, `llm-api.ts`
- **lib/stores/** — Svelte stores for state management
- **lib/types.ts** — Shared TypeScript type definitions

### API Structure
All APIs are under `/api/`. Key endpoints:
- `/api/projects/` — Universal project CRUD (UniversalProjectViewSet)
- `/api/projects/{id}/workflows/` — Workflow CRUD and execution
- `/api/projects/{id}/workflows/{id}/execute/` — Trigger workflow run
- `/api/projects/{id}/process_documents/` — Document processing/indexing
- `/api/projects/{id}/search/` — Vector search
- `/api/agent-orchestration/` — DocAware and orchestration APIs
- `/api/llm/` — Multi-provider LLM configuration
- `/api/project-api-keys/` — Per-project API key management
- `/api/public-chatbot/` — Public chatbot (isolated)
- `/api/workflow-deploy/{project_id}/` — Public deployment endpoints (no auth required)
- `/api/mcp-servers/` — MCP server integration
- `/api/templates/discover/`, `/api/templates/endpoints/`, `/api/templates/refresh/` — Dynamic template URL registration

### Data Flow
1. Documents uploaded → backend processes and indexes in Milvus (vector embeddings via `all-MiniLM-L6-v2`, 384 dims)
2. User designs workflow in WorkflowDesigner → JSON graph saved via API
3. Workflow executed → `workflow_executor.py` runs nodes sequentially, calling LLM providers with optional DocAware context retrieval and web search
4. Results streamed to frontend via WebSocket or returned via polling

### Docker Services (docker-compose.yml)
postgres, redis, etcd, minio, milvus, chromadb, backend, frontend, nginx — all on `ai_catalogue_network` (172.20.0.0/16)

## Key Patterns

- **Vite dev proxy**: Frontend proxies `/api` requests to backend (`vite.config.ts`). Set `BACKEND_URL` env var to change the target.
- **Custom User model**: Always reference `users.User`, never `auth.User`.
- **Project-scoped resources**: Workflows, documents, API keys are all scoped under a project UUID. URLs follow `/api/projects/{project_id}/...` nesting.
- **Encryption**: API keys stored with Fernet encryption. Keys come from `API_KEY_ENCRYPTION_KEY` and `PROJECT_API_KEY_ENCRYPTION_KEY` env vars.
- **CORS**: Three layers — `PublicChatbotCORSMiddleware`, `WorkflowDeploymentCORSMiddleware`, then `corsheaders.CorsMiddleware`. Order matters in `settings.py` MIDDLEWARE. Custom CORS middleware must come before `corsheaders.CorsMiddleware`.
- **Embedding model**: SentenceTransformers `all-MiniLM-L6-v2` (384-dim vectors). Configured in `settings.py`.
- **WebSocket rooms**: `AgentOrchestrationConsumer` uses project-scoped channel groups (`agent_orchestration_{project_id}`). Key message types: `workflow_connected` (handshake), `ping`/`pong` (keep-alive), `human_input_response` (human-in-the-loop), `execution_control` (pause/cancel).
- **Dynamic template URLs**: The `templates/` app registers project-type-specific URL patterns at runtime via `include_template_urls()`. If a template's URLs fail to load, `core/urls.py` has a hardcoded JSON fallback for AICC-IntelliDoc.
- **Tests**: No formal test framework configured. Some Django management commands exist for testing specific features (e.g., `test_bulk_upload`, `test_phase1_backend`, `test_milvus_algorithms`).

## Environment Variables

Copy `.env.example` to `.env`. Critical variables: `DB_*` (PostgreSQL), `MILVUS_*`, `DJANGO_SECRET_KEY`, `API_KEY_ENCRYPTION_KEY`, `PROJECT_API_KEY_ENCRYPTION_KEY`, LLM API keys (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`.

Runtime env vars set automatically in code (no `.env` needed): `TOKENIZERS_PARALLELISM=false` (prevents HuggingFace warnings), `PYTORCH_ENABLE_MPS_FALLBACK=1` (Mac M1/M2 GPU fallback), `HF_HUB_DOWNLOAD_TIMEOUT=300` (prevents model download timeouts).
