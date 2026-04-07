"""
Django management command to setup all required container data
Usage: python manage.py setup_container_data
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from users.models import DashboardIcon
import logging
import os

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Setup all required container data including dashboard icons for cloud deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-recreate',
            action='store_true',
            help='Force recreate all data even if it exists',
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Only verify existing data without creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Setting up container data for AI Catalogue')
        )
        self.stdout.write('=' * 60)
        
        success = True
        
        # Verify-only mode
        if options['verify_only']:
            return self.verify_data_only()
        
        # Pre-download embedding model for ChromaDB (prevents timeout errors)
        if not self.setup_embedding_model():
            self.stdout.write(
                self.style.WARNING('⚠️  Embedding model setup failed, but continuing...')
            )
            # Don't fail the entire setup if model download fails
        
        # Setup dashboard icons
        if not self.setup_dashboard_icons(options['force_recreate']):
            success = False
        
        # Verify all critical data
        if not self.verify_critical_data():
            success = False
            
        # Final status
        self.stdout.write('=' * 60)
        if success:
            self.stdout.write(
                self.style.SUCCESS('🎉 Container data setup completed successfully!')
            )
            self.stdout.write(
                self.style.SUCCESS('💡 AI Catalogue is ready for use')
            )
            self.show_access_info()
        else:
            self.stdout.write(
                self.style.ERROR('❌ Container data setup completed with errors!')
            )
            self.stdout.write(
                self.style.WARNING('⚠️  Some functionality may not work correctly')
            )
            return
    
    def setup_dashboard_icons(self, force_recreate=False):
        """Setup dashboard icons"""
        try:
            self.stdout.write('🎨 Setting up dashboard icons...')
            
            current_count = DashboardIcon.objects.count()
            self.stdout.write(f'📊 Current dashboard icons: {current_count}')
            
            if current_count == 0 or force_recreate:
                if force_recreate and current_count > 0:
                    self.stdout.write('🔄 Force recreating dashboard icons...')
                    call_command('restore_icons', '--clear')
                else:
                    self.stdout.write('🎨 Creating dashboard icons...')
                    call_command('restore_icons')
                
                final_count = DashboardIcon.objects.count()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Dashboard icons setup completed: {final_count} icons')
                )
            else:
                self.stdout.write('ℹ️  Dashboard icons already exist')
                # Show existing icons briefly
                icons = DashboardIcon.objects.filter(is_active=True).order_by('order')
                self.stdout.write(f'📋 Active icons: {", ".join([icon.name for icon in icons])}')
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Dashboard icons setup failed: {e}')
            )
            return False
    
    def verify_critical_data(self):
        """Verify that critical application data is set up"""
        try:
            self.stdout.write('🔍 Verifying critical application data...')
            
            # Check dashboard icons
            icon_count = DashboardIcon.objects.count()
            active_icon_count = DashboardIcon.objects.filter(is_active=True).count()
            
            if icon_count == 0:
                self.stdout.write(
                    self.style.ERROR('❌ No dashboard icons found!')
                )
                return False
            
            # Check for key icons
            required_icons = ['AICC-IntelliDoc', 'LLM Evaluation']
            missing_icons = []
            
            for icon_name in required_icons:
                if not DashboardIcon.objects.filter(name=icon_name, is_active=True).exists():
                    missing_icons.append(icon_name)
            
            if missing_icons:
                self.stdout.write(
                    self.style.ERROR(f'❌ Required icons missing: {", ".join(missing_icons)}')
                )
                return False
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Data verification passed: {active_icon_count}/{icon_count} active icons')
            )
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Data verification failed: {e}')
            )
            return False
    
    def verify_data_only(self):
        """Only verify existing data without creating anything"""
        self.stdout.write('🔍 Verifying existing container data...')
        
        if self.verify_critical_data():
            self.stdout.write(
                self.style.SUCCESS('✅ All critical data verified successfully!')
            )
        else:
            self.stdout.write(
                self.style.ERROR('❌ Data verification failed!')
            )
            self.stdout.write(
                self.style.WARNING('💡 Run without --verify-only to setup missing data')
            )
    
    def setup_embedding_model(self):
        """Pre-download SentenceTransformer model to prevent timeout errors"""
        try:
            self.stdout.write('📦 Setting up embedding model for ChromaDB...')
            
            # Check if sentence-transformers is available
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                self.stdout.write(
                    self.style.WARNING('⚠️  sentence-transformers not available, skipping model download')
                )
                return True  # Not a critical failure
            
            # Set HuggingFace timeout environment variable
            os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')  # 5 minutes
            
            from pathlib import Path
            # Use full model name with organization for proper cache detection
            model_name = 'sentence-transformers/all-MiniLM-L6-v2'
            cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
            
            # Check for both old and new HuggingFace cache formats
            # Old format: sentence-transformers_all-MiniLM-L6-v2
            # New format: models--sentence-transformers--all-MiniLM-L6-v2
            old_format_path = cache_dir / model_name.replace('/', '_')
            new_format_path = cache_dir / f"models--{model_name.replace('/', '--')}"
            
            model_cached = False
            if old_format_path.exists() and any(old_format_path.iterdir()):
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Embedding model already cached (old format) at {old_format_path}')
                )
                model_cached = True
            elif new_format_path.exists() and any(new_format_path.iterdir()):
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Embedding model already cached (new format) at {new_format_path}')
                )
                model_cached = True
            
            if model_cached:
                # Test the cached model
                try:
                    model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
                    test_embedding = model.encode("test", convert_to_numpy=True)
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Cached model verified (dimension: {len(test_embedding)})')
                    )
                    return True
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Cached model test failed: {e}, will re-download...')
                    )
            
            # Set timeout environment variables for HuggingFace
            os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')
            os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT_S', '300')
            os.environ.setdefault('REQUESTS_TIMEOUT', '300')
            
            # Download the model with increased timeout
            self.stdout.write(f'📥 Downloading embedding model: {model_name}...')
            self.stdout.write('   ⏳ This may take a few minutes on first run...')
            self.stdout.write(f'   ⏱️  Using timeout: {os.environ.get("HF_HUB_DOWNLOAD_TIMEOUT", "NOT SET")} seconds')
            
            try:
                model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
                test_embedding = model.encode("test", convert_to_numpy=True)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Embedding model downloaded and verified (dimension: {len(test_embedding)})')
                )
                # Check which format was used
                if new_format_path.exists():
                    self.stdout.write(f'💾 Model cached at: {new_format_path}')
                else:
                    self.stdout.write(f'💾 Model cached at: {old_format_path}')
                return True
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to download embedding model: {e}')
                )
                self.stdout.write(
                    self.style.WARNING('⚠️  ChromaDB will attempt to download on first use (may timeout)')
                )
                return False
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Embedding model setup error: {e}')
            )
            return False
    
    def show_access_info(self):
        """Show access information for the application"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🌐 Access Information:'))
        self.stdout.write('   📱 Frontend (Dev): http://localhost:5173')
        self.stdout.write('   📱 Frontend (Prod): http://localhost:3000') 
        self.stdout.write('   🔧 Backend API: http://localhost:8000')
        self.stdout.write('   👤 Admin Panel: http://localhost:8000/admin/')
        self.stdout.write('')
        self.stdout.write('💡 Use your superuser credentials to access the admin panel')
        self.stdout.write('🎯 Visit the dashboard to see all available AI tools and features')