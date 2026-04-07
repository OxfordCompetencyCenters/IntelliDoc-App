"""
Django management command to download the embedding model
Usage: python manage.py download_embedder_model
"""
from django.core.management.base import BaseCommand
from pathlib import Path
import time

class Command(BaseCommand):
    help = 'Download the sentence transformer model for embeddings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force download even if model exists',
        )
        parser.add_argument(
            '--model',
            type=str,
            default='all-MiniLM-L6-v2',
            help='Model name to download (default: all-MiniLM-L6-v2)',
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 AICC IntelliDoc - Model Download Command")
        self.stdout.write("=" * 50)
        
        model_name = options['model']
        force_download = options['force']
        
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            self.stdout.write(f"📦 Model: {model_name}")
            
            # Set up cache directory
            cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            model_cache_path = cache_dir / model_name.replace('/', '_')
            
            # Check if already exists
            if model_cache_path.exists() and any(model_cache_path.iterdir()) and not force_download:
                self.stdout.write(self.style.SUCCESS("✅ Model already cached!"))
                
                # Test the model
                try:
                    model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
                    test_embedding = model.encode("test")
                    self.stdout.write(self.style.SUCCESS(f"✅ Model test successful! Dimension: {len(test_embedding)}"))
                    return
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"⚠️  Cached model failed test: {e}"))
                    self.stdout.write("🔄 Will attempt fresh download...")
            
            # Download with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.stdout.write(f"📥 Download attempt {attempt + 1}/{max_retries}...")
                    
                    if attempt > 0:
                        wait_time = (2 ** attempt) * 10
                        self.stdout.write(f"⏳ Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                    
                    # Download the model
                    model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
                    
                    # Test the model
                    test_embedding = model.encode("test")
                    
                    self.stdout.write(self.style.SUCCESS("✅ Download successful!"))
                    self.stdout.write(f"📊 Model dimension: {len(test_embedding)}")
                    self.stdout.write(f"💾 Cached at: {model_cache_path}")
                    
                    # Update vector search system
                    self.stdout.write("🔄 Updating vector search system...")
                    from vector_search.embeddings import get_embedder_instance
                    # Reset the singleton to use the new model
                    import vector_search.embeddings as emb_module
                    emb_module._embedder_instance = None
                    emb_module.USE_OFFLINE_MODE = False
                    
                    # Test the new instance
                    embedder = get_embedder_instance()
                    if embedder.model is not None:
                        self.stdout.write(self.style.SUCCESS("✅ Vector search system updated!"))
                    else:
                        self.stdout.write(self.style.WARNING("⚠️  Vector search still in fallback mode"))
                    
                    return
                    
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "rate" in error_msg.lower():
                        self.stdout.write(self.style.WARNING(f"⚠️  Rate limiting: {e}"))
                        if attempt < max_retries - 1:
                            self.stdout.write("🔄 Will retry after delay...")
                        else:
                            self.stdout.write(self.style.ERROR("❌ Rate limiting persists"))
                    else:
                        self.stdout.write(self.style.ERROR(f"❌ Download failed: {e}"))
                    
                    if attempt == max_retries - 1:
                        self.stdout.write("\n💡 Suggestions:")
                        self.stdout.write("   • Wait a few hours for rate limiting to clear")
                        self.stdout.write("   • Try downloading during off-peak hours")
                        self.stdout.write("   • Check your internet connection")
                        raise e
            
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ Required packages not installed: {e}"))
            self.stdout.write("💡 Install with: pip install sentence-transformers torch")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Command failed: {e}"))
            raise e
