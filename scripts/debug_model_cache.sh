#!/bin/bash

# Debug script for SentenceTransformer model cache issues
# This script helps diagnose why the model is not being found in cache

echo "🔍 Debugging SentenceTransformer Model Cache Issues"
echo "=================================================="
echo ""

# 1. Check if model cache directory exists
echo "1️⃣ Checking model cache directory..."
echo "-----------------------------------"
docker exec ai_catalogue_backend bash -c "ls -la ~/.cache/torch/sentence_transformers/ 2>/dev/null || echo '❌ Cache directory does not exist'"
echo ""

# 2. Check for the specific model
echo "2️⃣ Checking for all-MiniLM-L6-v2 model..."
echo "----------------------------------------"
docker exec ai_catalogue_backend bash -c "ls -la ~/.cache/torch/sentence_transformers/all-MiniLM-L6-v2 2>/dev/null || echo '❌ Model directory does not exist'"
echo ""

# 3. Check if model files exist
echo "3️⃣ Checking model files..."
echo "-------------------------"
docker exec ai_catalogue_backend bash -c "if [ -d ~/.cache/torch/sentence_transformers/all-MiniLM-L6-v2 ]; then find ~/.cache/torch/sentence_transformers/all-MiniLM-L6-v2 -type f | head -10; else echo '❌ Model directory not found'; fi"
echo ""

# 4. Check environment variables
echo "4️⃣ Checking HuggingFace environment variables..."
echo "------------------------------------------------"
docker exec ai_catalogue_backend bash -c "env | grep -E 'HF_|HUGGING' || echo '❌ No HuggingFace environment variables found'"
echo ""

# 5. Check setup_container_data logs
echo "5️⃣ Checking setup_container_data execution logs..."
echo "-------------------------------------------------"
docker logs ai_catalogue_backend 2>&1 | grep -E "(embedding|model|setup_container|Setting up embedding)" | tail -20
echo ""

# 6. Check recent embedding service logs
echo "6️⃣ Checking recent embedding service logs..."
echo "---------------------------------------------"
docker logs ai_catalogue_backend 2>&1 | grep -E "(EMBEDDING|📊 EMBEDDING|📥 EMBEDDING|✅ EMBEDDING|❌ EMBEDDING)" | tail -30
echo ""

# 7. Check Python cache location
echo "7️⃣ Checking Python cache location..."
echo "------------------------------------"
docker exec ai_catalogue_backend python -c "from pathlib import Path; import os; cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'; print(f'Cache dir: {cache_dir}'); print(f'Exists: {cache_dir.exists()}'); print(f'Model path: {cache_dir / \"all-MiniLM-L6-v2\"}'); print(f'Model exists: {(cache_dir / \"all-MiniLM-L6-v2\").exists()}'); print(f'HF timeout: {os.environ.get(\"HF_HUB_DOWNLOAD_TIMEOUT\", \"NOT SET\")}')"
echo ""

# 8. Test model loading directly
echo "8️⃣ Testing model loading directly..."
echo "-----------------------------------"
docker exec ai_catalogue_backend python -c "
import os
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')
from pathlib import Path
from sentence_transformers import SentenceTransformer

cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
model_cache_path = cache_dir / 'all-MiniLM-L6-v2'

print(f'Cache dir: {cache_dir}')
print(f'Cache exists: {cache_dir.exists()}')
print(f'Model path: {model_cache_path}')
print(f'Model exists: {model_cache_path.exists()}')
if model_cache_path.exists():
    print(f'Model has files: {bool(list(model_cache_path.iterdir()))}')

print(f'HF timeout: {os.environ.get(\"HF_HUB_DOWNLOAD_TIMEOUT\", \"NOT SET\")}')

try:
    if model_cache_path.exists() and any(model_cache_path.iterdir()):
        print('✅ Loading from cache...')
        model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder=str(cache_dir))
    else:
        print('📥 Model not in cache, will download...')
        model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder=str(cache_dir))
    print('✅ Model loaded successfully!')
    test_emb = model.encode('test')
    print(f'✅ Test embedding dimension: {len(test_emb)}')
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
"
echo ""

# 9. Check if setup_container_data ran
echo "9️⃣ Checking if setup_container_data command exists..."
echo "-----------------------------------------------------"
docker exec ai_catalogue_backend python manage.py help setup_container_data 2>&1 | head -5
echo ""

# 10. Check container startup command
echo "🔟 Checking container startup command..."
echo "---------------------------------------"
docker inspect ai_catalogue_backend --format='{{.Config.Cmd}}' 2>/dev/null || echo "Could not get container command"
echo ""

echo "=================================================="
echo "✅ Debug information collected!"
echo ""
echo "💡 Next steps:"
echo "   1. If model cache doesn't exist, run: docker exec ai_catalogue_backend python manage.py download_embedder_model"
echo "   2. If HF timeout is not set, check docker-compose.yml environment variables"
echo "   3. If setup_container_data didn't run, check container startup logs"
