"""
Ollama Management API — manages the Ollama Docker container and models.
Ollama runs in Docker at http://127.0.0.1:11434
"""
import json
import logging
import aiohttp
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)

OLLAMA_URL = 'http://127.0.0.1:11434'

# Vision-capable Ollama models (required for PDF page extraction)
OLLAMA_VISION_MODELS = [
    {'name': 'gemma4:e4b', 'display_name': 'Gemma 4 e4B (Vision)', 'size': '~9GB', 'family': 'Google', 'description': 'Latest Google model with vision support', 'vision': True},
    {'name': 'gemma3:4b', 'display_name': 'Gemma 3 4B (Vision)', 'size': '~3GB', 'family': 'Google', 'description': 'Fast and efficient with vision', 'vision': True},
    {'name': 'llava:7b', 'display_name': 'LLaVA 7B (Vision)', 'size': '~4.7GB', 'family': 'LLaVA', 'description': 'Specialized vision-language model', 'vision': True},
    {'name': 'llava:13b', 'display_name': 'LLaVA 13B (Vision)', 'size': '~8GB', 'family': 'LLaVA', 'description': 'Larger vision-language model', 'vision': True},
    {'name': 'llama3.2-vision:11b', 'display_name': 'Llama 3.2 Vision 11B', 'size': '~7GB', 'family': 'Meta', 'description': 'Meta vision model', 'vision': True},
    {'name': 'minicpm-v:8b', 'display_name': 'MiniCPM-V 8B (Vision)', 'size': '~5GB', 'family': 'OpenBMB', 'description': 'Compact vision model', 'vision': True},
    {'name': 'moondream:1.8b', 'display_name': 'Moondream 1.8B (Vision)', 'size': '~1GB', 'family': 'Moondream', 'description': 'Tiny vision model, very fast', 'vision': True},
]


def _ollama_reachable():
    """Quick sync check if Ollama is reachable."""
    import urllib.request
    try:
        req = urllib.request.urlopen(OLLAMA_URL, timeout=3)
        return True
    except Exception:
        return False


@api_view(['GET'])
@permission_classes([AllowAny])
def ollama_status(request):
    """Check if Ollama is running and return version."""
    try:
        import urllib.request
        resp = urllib.request.urlopen(OLLAMA_URL, timeout=5)
        body = resp.read().decode()
        return Response({
            'status': 'running',
            'url': OLLAMA_URL,
            'response': body.strip(),
        })
    except Exception as e:
        return Response({
            'status': 'unavailable',
            'error': str(e),
            'message': 'Ollama Docker container is not running. Please ensure Docker Desktop is running.',
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def ollama_models(request):
    """List downloaded (local) Ollama models."""
    try:
        import urllib.request
        req = urllib.request.Request(f'{OLLAMA_URL}/api/tags')
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        models = data.get('models', [])

        formatted = []
        for m in models:
            formatted.append({
                'name': m.get('name', ''),
                'display_name': m.get('name', '').split(':')[0].title(),
                'size': m.get('size', 0),
                'size_formatted': _format_size(m.get('size', 0)),
                'modified_at': m.get('modified_at', ''),
                'digest': m.get('digest', ''),
                'parameter_size': m.get('details', {}).get('parameter_size', ''),
                'family': m.get('details', {}).get('family', ''),
                'quantization': m.get('details', {}).get('quantization_level', ''),
                'downloaded': True,
            })

        return Response({
            'models': formatted,
            'count': len(formatted),
        })
    except Exception as e:
        return Response({
            'models': [],
            'count': 0,
            'error': str(e),
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def ollama_library(request):
    """Return curated list of vision-capable models with download status."""
    downloaded = set()
    try:
        import urllib.request as _req
        resp = _req.urlopen(_req.Request(f'{OLLAMA_URL}/api/tags'), timeout=5)
        data = json.loads(resp.read().decode())
        for m in data.get('models', []):
            downloaded.add(m.get('name', ''))
    except Exception:
        pass

    models = []
    for m in OLLAMA_VISION_MODELS:
        models.append({**m, 'downloaded': m['name'] in downloaded})

    return Response({
        'models': models,
        'count': len(models),
        'ollama_available': _ollama_reachable(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def ollama_pull(request):
    """Pull/download a model. Returns streaming progress as JSON lines."""
    model_name = request.data.get('model', '').strip()
    if not model_name:
        return Response({'error': 'model is required'}, status=400)

    def stream_pull():
        import urllib.request
        req = urllib.request.Request(
            f'{OLLAMA_URL}/api/pull',
            data=json.dumps({'name': model_name, 'stream': True}).encode(),
            headers={'Content-Type': 'application/json'},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=3600)  # 1 hour timeout for large models
            for line in resp:
                decoded = line.decode('utf-8').strip()
                if decoded:
                    yield decoded + '\n'
        except Exception as e:
            yield json.dumps({'error': str(e)}) + '\n'

    response = StreamingHttpResponse(stream_pull(), content_type='application/x-ndjson')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@api_view(['DELETE'])
@permission_classes([AllowAny])
def ollama_delete_model(request):
    """Delete a downloaded model."""
    model_name = request.data.get('model', '').strip()
    if not model_name:
        return Response({'error': 'model is required'}, status=400)

    try:
        import urllib.request
        req = urllib.request.Request(
            f'{OLLAMA_URL}/api/delete',
            data=json.dumps({'name': model_name}).encode(),
            headers={'Content-Type': 'application/json'},
            method='DELETE',
        )
        resp = urllib.request.urlopen(req, timeout=30)
        return Response({'status': 'deleted', 'model': model_name})
    except Exception as e:
        return Response({'error': str(e), 'model': model_name}, status=500)


def _format_size(size_bytes):
    """Format bytes to human-readable."""
    if size_bytes == 0:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024.0:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024.0
    return f'{size_bytes:.1f} TB'
