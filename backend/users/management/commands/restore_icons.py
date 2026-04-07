"""
Django management command to restore dashboard icons
Usage: python manage.py restore_icons
"""

from django.core.management.base import BaseCommand
from users.models import DashboardIcon


class Command(BaseCommand):
    help = 'Restore dashboard icons including AICC-IntelliDoc and LLM Evaluation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing icons before creating new ones',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🎨 Restoring Dashboard Icons')
        )
        
        # Clear existing icons if requested
        if options['clear']:
            existing_count = DashboardIcon.objects.count()
            if existing_count > 0:
                DashboardIcon.objects.all().delete()
                self.stdout.write(f'🗑️  Cleared {existing_count} existing icons')

        icons_data = [
            {
                'name': 'AICC-IntelliDoc',
                'description': 'Advanced AI agent orchestration with document analysis and hierarchical processing',
                'icon_class': 'fa-sitemap',
                'color': 'oxford-blue',
                'route': '/features/intellidoc',  # Project creation page with template selection
                'order': 1,
                'is_active': True,
            },
            {
                'name': 'LLM Evaluation',
                'description': 'Compare responses from multiple LLM providers side-by-side',
                'icon_class': 'fa-balance-scale',
                'color': 'emerald',
                'route': '/features/llm-eval',
                'order': 2,
                'is_active': True,
            },
            {
                'name': 'Medical Analysis',
                'description': 'Specialized medical document analysis and processing',
                'icon_class': 'fa-stethoscope',
                'color': 'medical-blue',
                'route': '/features/medical',
                'order': 3,
                'is_active': True,
            },
            {
                'name': 'Legal Documents',
                'description': 'Legal document analysis and case law research',
                'icon_class': 'fa-gavel',
                'color': 'legal-gold',
                'route': '/features/legal',
                'order': 4,
                'is_active': True,
            },
            {
                'name': 'Historical Research',
                'description': 'Historical document analysis and research tools',
                'icon_class': 'fa-landmark',
                'color': 'history-brown',
                'route': '/features/history',
                'order': 5,
                'is_active': True,
            },
            {
                'name': 'Universal Projects',
                'description': 'Universal project management interface for all templates',
                'icon_class': 'fa-project-diagram',
                'color': 'universal-purple',
                'route': '/projects',  # Projects list/management page
                'order': 6,
                'is_active': True,
            }
        ]

        created_count = 0
        updated_count = 0

        for icon_data in icons_data:
            icon, created = DashboardIcon.objects.get_or_create(
                name=icon_data['name'],
                defaults=icon_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    f"✅ Created: {icon.name} ({icon.icon_class}) - {icon.color}"
                )
            else:
                # Update existing icon
                for key, value in icon_data.items():
                    setattr(icon, key, value)
                icon.save()
                updated_count += 1
                self.stdout.write(
                    f"🔄 Updated: {icon.name} ({icon.icon_class}) - {icon.color}"
                )

        # Summary
        total_icons = DashboardIcon.objects.count()
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'🎯 Summary:'))
        self.stdout.write(f'   📊 Icons created: {created_count}')
        self.stdout.write(f'   🔄 Icons updated: {updated_count}')
        self.stdout.write(f'   🎨 Total icons in database: {total_icons}')
        
        # Show key icons
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🔍 Key Icons:'))
        
        try:
            aicc_icon = DashboardIcon.objects.get(name='AICC-IntelliDoc')
            self.stdout.write(f'   🔹 AICC-IntelliDoc: {aicc_icon.icon_class} -> {aicc_icon.route}')
        except DashboardIcon.DoesNotExist:
            self.stdout.write(self.style.ERROR('   ❌ AICC-IntelliDoc: NOT FOUND'))
            
        try:
            llm_icon = DashboardIcon.objects.get(name='LLM Evaluation')
            self.stdout.write(f'   🔹 LLM Evaluation: {llm_icon.icon_class} -> {llm_icon.route}')
        except DashboardIcon.DoesNotExist:
            self.stdout.write(self.style.ERROR('   ❌ LLM Evaluation: NOT FOUND'))

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('✅ Dashboard icons restoration completed!')
        )
        self.stdout.write('💡 Visit your dashboard to see the restored icons')
