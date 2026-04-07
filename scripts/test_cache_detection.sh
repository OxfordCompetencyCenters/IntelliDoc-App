#!/bin/bash

# Test if the new cache detection logic will work

echo "🧪 Testing Cache Detection Logic"
echo "=================================="
echo ""

echo "1️⃣ Checking cache directory structure..."
echo "----------------------------------------"
docker exec ai_catalogue_backend python -c "
from pathlib import Path

cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
model_name = 'all-MiniLM-L6-v2'

# Old format
old_format_path = cache_dir / model_name.replace('/', '_')
# New format  
new_format_path = cache_dir / f\"models--{model_name.replace('/', '--')}\"

print(f'Cache dir: {cache_dir}')
print(f'Old format path: {old_format_path}')
print(f'New format path: {new_format_path}')
print(f'')
print(f'Old format exists: {old_format_path.exists()}')
if old_format_path.exists():
    print(f'Old format has files: {bool(list(old_format_path.iterdir()))}')
print(f'New format exists: {new_format_path.exists()}')
if new_format_path.exists():
    files = list(new_format_path.iterdir())
    print(f'New format has files: {bool(files)}')
    print(f'New format file count: {len(files)}')
    if files:
        print(f'Sample files: {[f.name for f in files[:5]]}')
"
echo ""

echo "2️⃣ Testing if SentenceTransformer can find the cached model..."
echo "------------------------------------------------------------"
docker exec -e HF_HUB_DOWNLOAD_TIMEOUT=300 ai_catalogue_backend python -c "
import os
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT_S', '300')
os.environ.setdefault('REQUESTS_TIMEOUT', '300')

from pathlib import Path
from sentence_transformers import SentenceTransformer
import time

cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
model_name = 'all-MiniLM-L6-v2'

old_format_path = cache_dir / model_name.replace('/', '_')
new_format_path = cache_dir / f\"models--{model_name.replace('/', '--')}\"

print(f'Testing model loading...')
print(f'Timeout env vars:')
print(f'  HF_HUB_DOWNLOAD_TIMEOUT: {os.environ.get(\"HF_HUB_DOWNLOAD_TIMEOUT\", \"NOT SET\")}')
print(f'  HF_HUB_DOWNLOAD_TIMEOUT_S: {os.environ.get(\"HF_HUB_DOWNLOAD_TIMEOUT_S\", \"NOT SET\")}')
print(f'  REQUESTS_TIMEOUT: {os.environ.get(\"REQUESTS_TIMEOUT\", \"NOT SET\")}')
print(f'')

start_time = time.time()
try:
    # Try loading - SentenceTransformer should find it in cache
    model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
    load_time = time.time() - start_time
    
    # Test encoding
    test_emb = model.encode('test')
    
    print(f'✅ Model loaded successfully in {load_time:.2f}s')
    print(f'✅ Embedding dimension: {len(test_emb)}')
    print(f'✅ Model found in cache (no download needed)')
    
except Exception as e:
    load_time = time.time() - start_time
    print(f'❌ Error after {load_time:.2f}s: {e}')
    import traceback
    traceback.print_exc()
"
echo ""

echo "3️⃣ Checking huggingface_hub timeout configuration..."
echo "-----------------------------------------------------"
docker exec ai_catalogue_backend python -c "
try:
    import huggingface_hub
    print(f'huggingface_hub version: {huggingface_hub.__version__}')
    
    # Check if we can configure timeout
    from huggingface_hub import file_download
    print(f'file_download module: {file_download}')
    
    # Check default timeout
    import inspect
    if hasattr(file_download, 'hf_hub_download'):
        sig = inspect.signature(file_download.hf_hub_download)
        print(f'hf_hub_download signature: {sig}')
        if 'timeout' in sig.parameters:
            print(f'✅ hf_hub_download supports timeout parameter')
        else:
            print(f'⚠️  hf_hub_download does NOT support timeout parameter')
except Exception as e:
    print(f'Could not check huggingface_hub: {e}')
"
echo ""

echo "=================================="
echo "✅ Test completed!"
echo ""
echo "💡 What to look for:"
echo "   - If 'New format exists: True' and 'New format has files: True', cache detection will work"
echo "   - If model loads in < 5 seconds, it's using cache (not downloading)"
echo "   - If timeout errors appear, we need to configure huggingface_hub differently"
