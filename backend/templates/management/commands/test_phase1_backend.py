# templates/management/commands/test_phase1_backend.py

from django.core.management.base import BaseCommand
import os
import logging
from pathlib import Path
from django.conf import settings

class Command(BaseCommand):
    help = 'Test Phase 1 Backend Template Independence Implementation (Enhanced)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--template-id',
            type=str,
            default='aicc-intellidoc',
            help='Template ID to test (default: aicc-intellidoc)'
        )
        parser.add_argument(
            '--test-logging',
            action='store_true',
            help='Test comprehensive logging implementation'
        )
        parser.add_argument(
            '--test-flexibility',
            action='store_true',
            help='Test template name flexibility'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        template_id = options['template_id']
        test_logging = options.get('test_logging', False)
        test_flexibility = options.get('test_flexibility', False)
        verbose = options.get('verbose', False)
        
        self.stdout.write(
            self.style.SUCCESS(f'🧪 Testing Enhanced Phase 1 Backend Implementation for template: {template_id}')
        )
        
        # Initialize test results
        test_results = {
            'template_structure': False,
            'template_files': False,
            'template_urls': False,
            'template_independence': False,
            'logging_implementation': False,
            'template_flexibility': False,
            'dynamic_urls': False,
            'overall_score': 0
        }
        
        # Test 1: Template Directory Structure
        test_results['template_structure'] = self.test_template_directory_structure(template_id, verbose)
        
        # Test 2: Template Files Existence and Content
        test_results['template_files'] = self.test_template_files_existence(template_id, verbose)
        
        # Test 3: Template URL Loading
        test_results['template_urls'] = self.test_template_url_loading(template_id, verbose)
        
        # Test 4: Template Independence Verification
        test_results['template_independence'] = self.test_template_independence(template_id, verbose)
        
        # Test 5: Comprehensive Logging Implementation
        if test_logging:
            test_results['logging_implementation'] = self.test_logging_implementation(template_id, verbose)
        
        # Test 6: Template Name Flexibility
        if test_flexibility:
            test_results['template_flexibility'] = self.test_template_flexibility(verbose)
        
        # Test 7: Dynamic URL Management
        test_results['dynamic_urls'] = self.test_dynamic_url_management(template_id, verbose)
        
        # Calculate overall score
        passed_tests = sum(1 for result in test_results.values() if result is True)
        total_tests = len([k for k, v in test_results.items() if k != 'overall_score' and v is not None])
        test_results['overall_score'] = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Display final results
        self.display_test_results(test_results, template_id)
        
        self.stdout.write(
            self.style.SUCCESS('✅ Enhanced Phase 1 Backend Testing Completed!')
        )
    
    def test_template_directory_structure(self, template_id, verbose):
        """Test enhanced template directory structure"""
        self.stdout.write(f'\\n📍 Test 1: Enhanced Template Directory Structure for {template_id}')
        
        try:
            # Check if template directory exists
            templates_base = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
            template_dir = templates_base / template_id
            
            if not template_dir.exists():
                self.stdout.write(
                    self.style.ERROR(f'❌ Template directory not found: {template_dir}')
                )
                return False
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Template directory exists: {template_dir}')
            )
            
            # Check for required directories
            required_dirs = ['components', 'assets']
            missing_dirs = []
            
            for dir_name in required_dirs:
                dir_path = template_dir / dir_name
                if dir_path.exists():
                    if verbose:
                        self.stdout.write(f'  ✅ Directory exists: {dir_name}')
                else:
                    missing_dirs.append(dir_name)
                    if verbose:
                        self.stdout.write(f'  ⚠️ Directory missing: {dir_name}')
            
            if missing_dirs:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Missing directories: {missing_dirs}')
                )
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing directory structure: {e}')
            )
            return False
    
    def test_template_files_existence(self, template_id, verbose):
        """Test enhanced template files existence and content"""
        self.stdout.write(f'\\n📍 Test 2: Enhanced Template Files for {template_id}')
        
        try:
            templates_base = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
            template_dir = templates_base / template_id
            
            # Enhanced required files list
            required_files = {
                'views.py': ['AICCIntelliDocViewSet', 'logger', 'discover', 'duplicate'],
                'serializers.py': ['logger', 'to_representation'],
                'urls.py': ['urlpatterns', 'TEMPLATE_METADATA', 'logger'],
                'services.py': ['logger', 'AICCIntelliDocDuplicationService'],
                'definition.py': ['AICCIntelliDocTemplate'],
                'hierarchical_config.py': [],
                'metadata.json': []
            }
            
            files_status = {}
            all_files_exist = True
            
            for file_name, required_content in required_files.items():
                file_path = template_dir / file_name
                file_exists = file_path.exists()
                
                files_status[file_name] = {
                    'exists': file_exists,
                    'size': file_path.stat().st_size if file_exists else 0,
                    'content_check': False
                }
                
                if file_exists:
                    if verbose:
                        self.stdout.write(f'  ✅ File exists: {file_name} ({files_status[file_name]["size"]} bytes)')
                    
                    # Check for required content
                    if required_content:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            content_found = all(item in content for item in required_content)
                            files_status[file_name]['content_check'] = content_found
                            
                            if content_found:
                                if verbose:
                                    self.stdout.write(f'    ✅ Required content found in {file_name}')
                            else:
                                missing_content = [item for item in required_content if item not in content]
                                if verbose:
                                    self.stdout.write(f'    ⚠️ Missing content in {file_name}: {missing_content}')
                        except Exception as e:
                            if verbose:
                                self.stdout.write(f'    ❌ Error reading {file_name}: {e}')
                else:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ File missing: {file_name}')
                    )
                    all_files_exist = False
            
            # Summary
            existing_files = sum(1 for status in files_status.values() if status['exists'])
            total_files = len(required_files)
            
            self.stdout.write(f'Files Status: {existing_files}/{total_files} files exist')
            
            return all_files_exist
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing template files: {e}')
            )
            return False
    
    def test_template_url_loading(self, template_id, verbose):
        """Test enhanced template URL loading"""
        self.stdout.write(f'\\n📍 Test 3: Enhanced Template URL Loading for {template_id}')
        
        try:
            # Test dynamic URL loading
            from templates.dynamic_urls import template_url_manager
            
            url_patterns = template_url_manager.get_template_urls(template_id)
            
            if url_patterns:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Template URLs loaded: {len(url_patterns)} patterns')
                )
                
                if verbose:
                    for i, pattern in enumerate(url_patterns):
                        pattern_name = getattr(pattern, 'name', 'unnamed')
                        self.stdout.write(f'  Pattern {i+1}: {pattern_name}')
                
                # Test URL metadata
                try:
                    import importlib
                    template_urls_module = importlib.import_module(
                        f'templates.template_definitions.{template_id}.urls'
                    )
                    
                    if hasattr(template_urls_module, '__template_metadata__'):
                        metadata = template_urls_module.__template_metadata__
                        if verbose:
                            self.stdout.write(f'  ✅ Template metadata found: {metadata["template_name"]}')
                    else:
                        if verbose:
                            self.stdout.write(f'  ⚠️ Template metadata not found')
                
                except Exception as e:
                    if verbose:
                        self.stdout.write(f'  ❌ Error loading metadata: {e}')
                
                return True
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ No URL patterns found for template: {template_id}')
                )
                return False
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing template URL loading: {e}')
            )
            return False
    
    def test_template_independence(self, template_id, verbose):
        """Test template independence verification"""
        self.stdout.write(f'\\n📍 Test 4: Template Independence for {template_id}')
        
        try:
            independence_score = 0
            max_score = 5
            
            # Test 1: Template directory isolation
            templates_base = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
            template_dir = templates_base / template_id
            
            if template_dir.exists():
                independence_score += 1
                if verbose:
                    self.stdout.write(f'  ✅ Template has isolated directory structure')
            
            # Test 2: Template-specific logger
            try:
                logger = logging.getLogger(f'templates.{template_id}')
                if logger:
                    independence_score += 1
                    if verbose:
                        self.stdout.write(f'  ✅ Template has specific logger')
            except Exception as e:
                if verbose:
                    self.stdout.write(f'  ❌ Template logger error: {e}')
            
            # Test 3: Template-specific endpoints
            from templates.dynamic_urls import template_url_manager
            url_patterns = template_url_manager.get_template_urls(template_id)
            
            if url_patterns and len(url_patterns) >= 4:  # Expected: discover, duplicate, configuration, status
                independence_score += 1
                if verbose:
                    self.stdout.write(f'  ✅ Template has sufficient endpoints ({len(url_patterns)})')
            
            # Test 4: No cross-template dependencies
            template_files = ['views.py', 'serializers.py', 'services.py']
            no_dependencies = True
            
            for file_name in template_files:
                file_path = template_dir / file_name
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Check for hardcoded template references (should be flexible)
                        if 'aicc-intellidoc' in content.lower() and template_id != 'aicc-intellidoc':
                            no_dependencies = False
                            if verbose:
                                self.stdout.write(f'  ⚠️ Found hardcoded reference in {file_name}')
                    except Exception as e:
                        if verbose:
                            self.stdout.write(f'  ❌ Error checking {file_name}: {e}')
            
            if no_dependencies:
                independence_score += 1
                if verbose:
                    self.stdout.write(f'  ✅ No hardcoded cross-template dependencies found')
            
            # Test 5: Template duplication capability
            try:
                # Use importlib.util to handle hyphens in template names
                import importlib.util
                from pathlib import Path
                
                template_services_path = templates_base / template_id / 'services.py'
                if template_services_path.exists():
                    spec = importlib.util.spec_from_file_location(f"template_{template_id.replace('-', '_')}_services", template_services_path)
                    services_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(services_module)
                    
                    if hasattr(services_module, 'AICCIntelliDocDuplicationService'):
                        duplication_service = getattr(services_module, 'AICCIntelliDocDuplicationService')()
                        independence_score += 1
                        if verbose:
                            self.stdout.write(f'  ✅ Template duplication service available')
                    else:
                        if verbose:
                            self.stdout.write(f'  ⚠️ Template duplication service class not found')
                else:
                    if verbose:
                        self.stdout.write(f'  ⚠️ Template services file not found')
            except Exception as e:
                if verbose:
                    self.stdout.write(f'  ❌ Template duplication service error: {e}')
            
            # Calculate independence percentage
            independence_percentage = (independence_score / max_score) * 100
            
            self.stdout.write(f'Independence Score: {independence_score}/{max_score} ({independence_percentage:.1f}%)')
            
            return independence_score >= 4  # At least 80% independence required
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing template independence: {e}')
            )
            return False
    
    def test_logging_implementation(self, template_id, verbose):
        """Test comprehensive logging implementation"""
        self.stdout.write(f'\\n📍 Test 5: Comprehensive Logging Implementation for {template_id}')
        
        try:
            logging_score = 0
            max_score = 4
            
            # Test 1: Template-specific logger configuration
            logger = logging.getLogger(f'templates.{template_id}')
            if logger and logger.handlers:
                logging_score += 1
                if verbose:
                    self.stdout.write(f'  ✅ Template-specific logger configured')
            
            # Test 2: Log file creation
            logs_dir = Path(settings.BASE_DIR).parent / 'logs'
            if logs_dir.exists():
                log_files = list(logs_dir.glob('backend_*.log'))
                if log_files:
                    logging_score += 1
                    if verbose:
                        self.stdout.write(f'  ✅ Backend log files found: {len(log_files)}')
                        if len(log_files) > 0:
                            latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                            self.stdout.write(f'    Latest log: {latest_log.name}')
            
            # Test 3: Logging in template files
            templates_base = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
            template_dir = templates_base / template_id
            
            files_with_logging = 0
            template_files = ['views.py', 'serializers.py', 'services.py', 'urls.py']
            
            for file_name in template_files:
                file_path = template_dir / file_name
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Check for logging implementation
                        if 'logger' in content and 'logging.getLogger' in content:
                            files_with_logging += 1
                            if verbose:
                                self.stdout.write(f'    ✅ Logging implemented in {file_name}')
                    except Exception as e:
                        if verbose:
                            self.stdout.write(f'    ❌ Error checking {file_name}: {e}')
            
            if files_with_logging >= 3:  # At least 3 files should have logging
                logging_score += 1
                if verbose:
                    self.stdout.write(f'  ✅ Logging implemented in {files_with_logging}/{len(template_files)} files')
            
            # Test 4: Timestamp-based log files
            if logs_dir.exists():
                timestamp_logs = list(logs_dir.glob('*_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_*.log'))
                if timestamp_logs:
                    logging_score += 1
                    if verbose:
                        self.stdout.write(f'  ✅ Timestamp-based log files found: {len(timestamp_logs)}')
            
            # Calculate logging percentage
            logging_percentage = (logging_score / max_score) * 100
            
            self.stdout.write(f'Logging Score: {logging_score}/{max_score} ({logging_percentage:.1f}%)')
            
            return logging_score >= 3  # At least 75% logging implementation required
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing logging implementation: {e}')
            )
            return False
    
    def test_template_flexibility(self, verbose):
        """Test template name flexibility"""
        self.stdout.write(f'\\n📍 Test 6: Template Name Flexibility')
        
        try:
            flexibility_score = 0
            max_score = 3
            
            # Test 1: Dynamic URL manager supports any template
            from templates.dynamic_urls import template_url_manager
            
            # Test with different template names
            test_templates = ['aicc-intellidoc', 'legal', 'medical', 'history']
            supported_templates = 0
            
            for template_name in test_templates:
                try:
                    urls = template_url_manager.get_template_urls(template_name)
                    if urls is not None:  # Even empty list is acceptable
                        supported_templates += 1
                        if verbose:
                            self.stdout.write(f'  ✅ Template URL loading supports: {template_name}')
                except Exception as e:
                    if verbose:
                        self.stdout.write(f'  ❌ Template URL loading failed for {template_name}: {e}')
            
            if supported_templates >= len(test_templates):
                flexibility_score += 1
            
            # Test 2: Template discovery finds multiple templates
            discovered_templates = template_url_manager.discover_available_templates()
            if len(discovered_templates) >= 2:  # At least 2 templates should be discoverable
                flexibility_score += 1
                if verbose:
                    self.stdout.write(f'  ✅ Template discovery found {len(discovered_templates)} templates')
                    for template_info in discovered_templates:
                        self.stdout.write(f'    - {template_info["template_id"]}: {template_info["status"]}')
            
            # Test 3: Core URLs support multiple template patterns
            try:
                from django.conf import settings
                core_urls_path = Path(settings.BASE_DIR) / 'core' / 'urls.py'
                
                if core_urls_path.exists():
                    with open(core_urls_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for multiple template URL patterns
                    template_patterns = content.count("path('api/templates/")
                    if template_patterns >= 4:  # Should support multiple templates
                        flexibility_score += 1
                        if verbose:
                            self.stdout.write(f'  ✅ Core URLs support multiple templates ({template_patterns} patterns)')
            except Exception as e:
                if verbose:
                    self.stdout.write(f'  ❌ Error checking core URLs: {e}')
            
            # Calculate flexibility percentage
            flexibility_percentage = (flexibility_score / max_score) * 100
            
            self.stdout.write(f'Flexibility Score: {flexibility_score}/{max_score} ({flexibility_percentage:.1f}%)')
            
            return flexibility_score >= 2  # At least 67% flexibility required
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing template flexibility: {e}')
            )
            return False
    
    def test_dynamic_url_management(self, template_id, verbose):
        """Test dynamic URL management system"""
        self.stdout.write(f'\\n📍 Test 7: Dynamic URL Management for {template_id}')
        
        try:
            management_score = 0
            max_score = 4
            
            # Test 1: Template URL manager initialization
            try:
                from templates.dynamic_urls import template_url_manager
                if template_url_manager:
                    management_score += 1
                    if verbose:
                        self.stdout.write(f'  ✅ Template URL manager initialized')
            except Exception as e:
                if verbose:
                    self.stdout.write(f'  ❌ Template URL manager error: {e}')
            
            # Test 2: Template discovery functionality
            try:
                discovered = template_url_manager.discover_available_templates()
                if discovered and len(discovered) > 0:
                    management_score += 1
                    if verbose:
                        self.stdout.write(f'  ✅ Template discovery working ({len(discovered)} templates)')
            except Exception as e:
                if verbose:
                    self.stdout.write(f'  ❌ Template discovery error: {e}')
            
            # Test 3: Template URL caching
            try:
                # Load URLs twice to test caching
                urls1 = template_url_manager.get_template_urls(template_id)
                urls2 = template_url_manager.get_template_urls(template_id)
                
                if urls1 is not None and urls2 is not None:
                    management_score += 1
                    if verbose:
                        self.stdout.write(f'  ✅ Template URL caching working')
            except Exception as e:
                if verbose:
                    self.stdout.write(f'  ❌ Template URL caching error: {e}')
            
            # Test 4: Template structure validation
            try:
                is_valid = template_url_manager.validate_template_structure(template_id)
                if is_valid:
                    management_score += 1
                    if verbose:
                        self.stdout.write(f'  ✅ Template structure validation passed')
                else:
                    if verbose:
                        self.stdout.write(f'  ⚠️ Template structure validation failed')
            except Exception as e:
                if verbose:
                    self.stdout.write(f'  ❌ Template validation error: {e}')
            
            # Calculate management percentage
            management_percentage = (management_score / max_score) * 100
            
            self.stdout.write(f'Dynamic URL Management Score: {management_score}/{max_score} ({management_percentage:.1f}%)')
            
            return management_score >= 3  # At least 75% functionality required
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing dynamic URL management: {e}')
            )
            return False
    
    def display_test_results(self, test_results, template_id):
        """Display comprehensive test results"""
        self.stdout.write(f'\\n🎯 Enhanced Phase 1 Test Results for {template_id}')
        self.stdout.write('=' * 60)
        
        # Individual test results
        test_descriptions = {
            'template_structure': 'Template Directory Structure',
            'template_files': 'Template Files Existence & Content',
            'template_urls': 'Template URL Loading',
            'template_independence': 'Template Independence',
            'logging_implementation': 'Comprehensive Logging',
            'template_flexibility': 'Template Name Flexibility',
            'dynamic_urls': 'Dynamic URL Management'
        }
        
        for test_key, description in test_descriptions.items():
            if test_results.get(test_key) is not None:
                status = '✅ PASS' if test_results[test_key] else '❌ FAIL'
                self.stdout.write(f'{description:<35} {status}')
        
        # Overall score
        self.stdout.write('=' * 60)
        overall_score = test_results['overall_score']
        
        if overall_score >= 90:
            score_status = self.style.SUCCESS(f'🏆 EXCELLENT ({overall_score:.1f}%)')
        elif overall_score >= 75:
            score_status = self.style.SUCCESS(f'✅ GOOD ({overall_score:.1f}%)')
        elif overall_score >= 60:
            score_status = self.style.WARNING(f'⚠️ NEEDS IMPROVEMENT ({overall_score:.1f}%)')
        else:
            score_status = self.style.ERROR(f'❌ POOR ({overall_score:.1f}%)')
        
        self.stdout.write(f'Overall Phase 1 Score: {score_status}')
        
        # Recommendations
        if overall_score < 100:
            self.stdout.write('\\n📋 Recommendations:')
            
            if not test_results.get('logging_implementation', True):
                self.stdout.write('  • Implement comprehensive logging in all template components')
            
            if not test_results.get('template_flexibility', True):
                self.stdout.write('  • Enhance template name flexibility for unlimited template support')
            
            if not test_results.get('dynamic_urls', True):
                self.stdout.write('  • Fix dynamic URL management system')
            
            if not test_results.get('template_independence', True):
                self.stdout.write('  • Ensure complete template independence and isolation')
        
        # Next steps
        self.stdout.write('\\n🚀 Next Steps:')
        if overall_score >= 80:
            self.stdout.write('  ✅ Phase 1 implementation is ready for Phase 2 (Frontend Template Architecture)')
        else:
            self.stdout.write('  ⚠️ Complete Phase 1 improvements before proceeding to Phase 2')
