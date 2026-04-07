"""
Quick fix script for the testxav project collection name mismatch.
Run via: python manage.py fix_testxav_collection
"""
from django.core.management.base import BaseCommand
from users.models import IntelliDocProject, ProjectVectorCollection

class Command(BaseCommand):
    help = 'Fix collection name for testxav project (b2d02e08-c494-4c42-8502-32154124dabe)'

    def handle(self, *args, **options):
        project_id = 'b2d02e08-c494-4c42-8502-32154124dabe'
        actual_milvus_name = 'testxav_b2d02e08_c494_4c42_8502_32154124dabe'
        
        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
            self.stdout.write(f'📋 Project: {project.name} ({project_id})')
            
            if not hasattr(project, 'vector_collection'):
                self.stdout.write(self.style.ERROR('❌ No ProjectVectorCollection record found'))
                return
            
            collection = project.vector_collection
            old_name = collection.collection_name
            
            self.stdout.write(f'   Old name: {old_name}')
            self.stdout.write(f'   New name: {actual_milvus_name}')
            
            if old_name == actual_milvus_name:
                self.stdout.write(self.style.SUCCESS('✅ Collection name already correct'))
                return
            
            collection.collection_name = actual_milvus_name
            collection.save()
            
            self.stdout.write(self.style.SUCCESS(f'✅ Updated collection_name from "{old_name}" to "{actual_milvus_name}"'))
            self.stdout.write(self.style.SUCCESS('✅ Fix complete! Content filters should now work.'))
            
        except IntelliDocProject.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Project not found: {project_id}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())

