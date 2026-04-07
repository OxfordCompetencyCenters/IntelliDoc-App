# Collection name fix command - removed for Electron desktop version.
# This was used to fix Milvus collection naming issues.
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Legacy command (Milvus replaced with ChromaDB)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('This command is no longer applicable (Milvus replaced with ChromaDB).'))
