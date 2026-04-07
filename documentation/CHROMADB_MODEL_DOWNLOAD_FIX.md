# ChromaDB HuggingFace Timeout Fix

## Problem

Multiple services were trying to download the `all-MiniLM-L6-v2` model from HuggingFace during initialization, causing timeout errors:

1. **ChromaDB's `SentenceTransformerEmbeddingFunction`** (for public chatbot)
2. **DocAware Embedding Service** (for workflow agents with document awareness)

Error example:
```
ReadTimeoutError: HTTPSConnectionPool(host='huggingface.co', port=443): Read timed out. (read timeout=10)
```

The model would eventually load after retries, but this caused:
- Delays during workflow execution
- Warning messages in logs
- Potential failures if network is slow

## Solution Implemented

### 1. Automatic Model Pre-download on Startup

The model is now automatically downloaded during container startup via the `setup_container_data` management command. This ensures the model is cached locally before ChromaDB tries to use it.

**Location**: `backend/users/management/commands/setup_container_data.py`

**What it does**:
- Checks if model is already cached
- Downloads model if not cached (with 5-minute timeout)
- Verifies the downloaded model works
- Caches model at `~/.cache/torch/sentence_transformers/all-MiniLM-L6-v2`

### 2. Environment Variables for Timeout

Added HuggingFace timeout configuration to `docker-compose.yml`:

```yaml
HF_HUB_DOWNLOAD_TIMEOUT: "300"  # 5 minutes
HF_HUB_CACHE: "/home/appuser/.cache/huggingface"
```

### 3. Enhanced ChromaDB Initialization

Updated `backend/public_chatbot/services.py` to:
- Set timeout environment variable before initialization
- Check if model is cached before attempting download
- Provide better logging about cache status
- Fall back gracefully if download fails

### 4. Enhanced DocAware Embedding Service

Updated `backend/agent_orchestration/docaware/embedding_service.py` to:
- Set timeout environment variable before initialization
- Check if model is cached first (same approach as main system)
- Use cached model if available
- Provide better logging about cache status

## How It Works

### Startup Sequence

When you run `./scripts/start-dev.sh`, the backend container will:

1. Run migrations
2. **Run `setup_container_data`** which:
   - Checks for cached model
   - Downloads if missing (with 5-minute timeout)
   - Verifies the model works
3. Start Django server
4. ChromaDB service initializes and uses the cached model

### Model Cache Location

The model is cached at:
- **Host**: `~/.cache/torch/sentence_transformers/all-MiniLM-L6-v2`
- **Container**: `/home/appuser/.cache/torch/sentence_transformers/all-MiniLM-L6-v2`

Since the backend code is mounted as a volume in development mode, the cache persists between container restarts.

## Manual Model Download (Optional)

If you want to manually download the model before starting the container:

```bash
# Enter the backend container
docker exec -it ai_catalogue_backend bash

# Run the download command
python manage.py download_embedder_model --model all-MiniLM-L6-v2
```

Or use the existing management command:

```bash
docker exec ai_catalogue_backend python manage.py download_embedder_model
```

## Verification

After startup, check the logs to verify the model was downloaded:

```bash
docker logs ai_catalogue_backend | grep -E "(CHROMA|embedding|model)"
```

You should see:
```
✅ Embedding model downloaded and verified (dimension: 384)
✅ CHROMA: Found cached model at ..., using cached version
✅ CHROMA: Using SentenceTransformer embeddings
```

## Troubleshooting

### If Model Download Still Times Out

1. **Check internet connection** in the container:
   ```bash
   docker exec ai_catalogue_backend curl -I https://huggingface.co
   ```

2. **Increase timeout** in `docker-compose.yml`:
   ```yaml
   HF_HUB_DOWNLOAD_TIMEOUT: "600"  # 10 minutes
   ```

3. **Download manually** using the management command (see above)

4. **Check cache directory**:
   ```bash
   docker exec ai_catalogue_backend ls -la ~/.cache/torch/sentence_transformers/
   ```

### If Model Download Fails

The system will:
- Log a warning but continue startup
- ChromaDB will attempt to download on first use
- If that also fails, it will fall back to default embeddings (less accurate)

## Benefits

1. **No more timeout errors**: Model is pre-downloaded during startup
2. **Faster initialization**: ChromaDB uses cached model immediately
3. **Better reliability**: Model is verified before use
4. **Automatic**: No manual intervention needed
5. **Persistent cache**: Model stays cached between restarts

## Files Modified

1. `backend/users/management/commands/setup_container_data.py` - Added model download step
2. `docker-compose.yml` - Added HuggingFace timeout environment variables
3. `backend/public_chatbot/services.py` - Enhanced ChromaDB initialization with cache checking
4. `backend/agent_orchestration/docaware/embedding_service.py` - Enhanced DocAware initialization with cache checking

## Next Steps

1. Restart your containers:
   ```bash
   ./scripts/start-dev.sh
   ```

2. Monitor the logs during startup to see the model download:
   ```bash
   docker logs -f ai_catalogue_backend
   ```

3. Verify ChromaDB is working:
   ```bash
   docker logs ai_catalogue_backend | grep "CHROMA"
   ```

The model will be downloaded automatically on first startup, and subsequent startups will use the cached version.
