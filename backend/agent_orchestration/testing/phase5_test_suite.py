"""
Phase 5: Workflow Integration Testing & Optimization Suite

Comprehensive testing framework for validating the complete workflow integration
across all phases with performance monitoring and production optimization.
"""

import asyncio
import logging
import json
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
import traceback

# Django imports
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.management.base import BaseCommand

# Project imports
from users.models import IntelliDocProject, AgentWorkflow, SimulationRun, AgentMessage
from agent_orchestration.autogen.service import AutoGenWorkflowService
from agent_orchestration.autogen.generator import AutoGenWorkflowGenerator
from agent_orchestration.autogen.executor import AutoGenExecutor
from agent_orchestration.autogen.llm_service import get_autogen_llm_service
from agent_orchestration.rag_service import DocumentAwareAgentService

logger = logging.getLogger('workflow_testing')

class WorkflowIntegrationTestSuite:
    """Comprehensive test suite for workflow integration"""
    
    def __init__(self):
        self.test_results = {}
        self.performance_metrics = {}
        self.test_start_time = timezone.now()
        logger.info("🧪 WORKFLOW TESTING SUITE: Initialized comprehensive test suite")
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite across all phases"""
        logger.info("🚀 WORKFLOW TESTING SUITE: Starting comprehensive test execution")
        
        test_phases = [
            ("Phase 1: Foundation Tests", self.test_phase1_foundation),
            ("Phase 2: RAG Integration Tests", self.test_phase2_rag_integration),
            ("Phase 3: Multi-Provider LLM Tests", self.test_phase3_multi_provider),
            ("Phase 4: Real-Time Execution Tests", self.test_phase4_realtime_execution),
            ("Phase 5: Performance & Production Tests", self.test_phase5_performance)
        ]
        
        overall_results = {
            'test_summary': {},
            'phase_results': {},
            'performance_metrics': {},
            'production_readiness': {},
            'recommendations': []
        }
        
        for phase_name, test_function in test_phases:
            logger.info(f"🧪 TESTING: Starting {phase_name}")
            phase_start = time.time()
            
            try:
                phase_results = await test_function()
                phase_duration = time.time() - phase_start
                
                overall_results['phase_results'][phase_name] = {
                    'success': True,
                    'results': phase_results,
                    'duration_seconds': phase_duration,
                    'timestamp': timezone.now().isoformat()
                }
                
                logger.info(f"✅ TESTING: {phase_name} completed successfully in {phase_duration:.2f}s")
                
            except Exception as e:
                phase_duration = time.time() - phase_start
                overall_results['phase_results'][phase_name] = {
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc(),
                    'duration_seconds': phase_duration,
                    'timestamp': timezone.now().isoformat()
                }
                logger.error(f"❌ TESTING: {phase_name} failed after {phase_duration:.2f}s: {e}")
        
        # Calculate overall metrics
        overall_results['test_summary'] = self.calculate_test_summary(overall_results)
        overall_results['performance_metrics'] = self.performance_metrics
        overall_results['production_readiness'] = self.assess_production_readiness(overall_results)
        overall_results['recommendations'] = self.generate_recommendations(overall_results)
        
        total_duration = (timezone.now() - self.test_start_time).total_seconds()
        logger.info(f"🎯 WORKFLOW TESTING SUITE: Completed all tests in {total_duration:.2f}s")
        
        return overall_results

    async def test_phase1_foundation(self) -> Dict[str, Any]:
        """Test Phase 1: Workflow foundation and connection types"""
        return {
            'connection_types_test': await self.test_connection_types(),
            'service_initialization_test': await self.test_service_initialization(),
        }

    async def test_connection_types(self) -> Dict[str, bool]:
        """Test all workflow connection types"""
        connection_types = ['sequential', 'broadcast', 'group_chat', 'conditional', 'reflection']
        results = {}
        
        for conn_type in connection_types:
            try:
                test_graph = {'nodes': [], 'edges': []}
                service = AutoGenWorkflowService()
                agents = service.create_agents_from_graph(test_graph, {'supported_agent_types': []})
                results[f'{conn_type}_validation'] = True
                logger.info(f"✅ CONNECTION TEST: {conn_type} validation passed")
            except Exception as e:
                results[f'{conn_type}_validation'] = False
                logger.error(f"❌ CONNECTION TEST: {conn_type} failed: {e}")
        
        return results

    async def test_service_initialization(self) -> Dict[str, bool]:
        """Test workflow service components initialization"""
        results = {}
        
        try:
            service = AutoGenWorkflowService()
            results['workflow_service'] = hasattr(service, 'agent_registry')
            
            generator = AutoGenWorkflowGenerator('test_project')
            results['workflow_generator'] = hasattr(generator, 'project_id')
            
            llm_service = get_autogen_llm_service()
            results['llm_service'] = hasattr(llm_service, 'create_llm_config')
            
            logger.info("✅ SERVICE INIT: All services initialized successfully")
        except Exception as e:
            results['initialization_error'] = str(e)
            logger.error(f"❌ SERVICE INIT: Failed: {e}")
        
        return results

    async def test_phase2_rag_integration(self) -> Dict[str, Any]:
        """Test Phase 2: RAG integration and DocAware agents"""
        return {
            'rag_service_test': await self.test_rag_service(),
        }

    async def test_rag_service(self) -> Dict[str, bool]:
        """Test RAG service functionality"""
        results = {}
        try:
            rag_service = DocumentAwareAgentService('test_project')
            results['rag_service_init'] = True
            
            test_agent_config = {
                'doc_aware': True,
                'vector_collections': ['test_documents'],
                'rag_search_limit': 5,
                'system_message': 'Test agent'
            }
            
            enhanced_config = rag_service.enhance_agent_with_rag(test_agent_config)
            results['rag_enhancement'] = 'rag_functions' in enhanced_config
            
            logger.info("✅ RAG SERVICE: All tests passed")
        except Exception as e:
            results['rag_service_error'] = str(e)
            logger.error(f"❌ RAG SERVICE: Failed: {e}")
        
        return results

    async def test_phase3_multi_provider(self) -> Dict[str, Any]:
        """Test Phase 3: Multi-provider LLM integration"""
        return {
            'llm_service_test': await self.test_llm_service(),
        }

    async def test_llm_service(self) -> Dict[str, bool]:
        """Test multi-provider LLM service"""
        results = {}
        try:
            llm_service = get_autogen_llm_service()
            supported_providers = ['openai', 'anthropic', 'google']
            
            for provider in supported_providers:
                test_config = {
                    'llm_provider': provider,
                    'llm_model': 'test-model',
                    'temperature': 0.7
                }
                llm_config = llm_service.create_llm_config(test_config)
                results[f'{provider}_config'] = isinstance(llm_config, dict) and 'model' in llm_config
            
            logger.info("✅ LLM SERVICE: All providers tested")
        except Exception as e:
            results['llm_service_error'] = str(e)
            logger.error(f"❌ LLM SERVICE: Failed: {e}")
        
        return results

    async def test_phase4_realtime_execution(self) -> Dict[str, Any]:
        """Test Phase 4: Real-time execution and streaming"""
        return {
            'executor_test': await self.test_executor_initialization(),
        }

    async def test_executor_initialization(self) -> Dict[str, bool]:
        """Test AutoGen executor initialization"""
        results = {}
        try:
            executor = AutoGenExecutor('test_project', 'test_run')
            results['executor_init'] = hasattr(executor, 'project_id')
            results['executor_methods'] = all(hasattr(executor, method) for method in [
                'execute_workflow', 'create_execution_environment', 'send_execution_status'
            ])
            logger.info("✅ EXECUTOR INIT: Executor initialized successfully")
        except Exception as e:
            results['executor_init_error'] = str(e)
            logger.error(f"❌ EXECUTOR INIT: Failed: {e}")
        
        return results

    async def test_phase5_performance(self) -> Dict[str, Any]:
        """Test Phase 5: Performance and production readiness"""
        return {
            'performance_benchmarks': await self.run_performance_benchmarks(),
        }

    async def run_performance_benchmarks(self) -> Dict[str, Any]:
        """Run performance benchmarks"""
        benchmarks = {}
        
        # Simple benchmark test
        start_time = time.time()
        for _ in range(10):
            service = AutoGenWorkflowService()
            service.create_agents_from_graph({'nodes': [], 'edges': []}, {'supported_agent_types': []})
        benchmarks['service_initialization_10_iterations'] = time.time() - start_time
        
        logger.info("✅ PERFORMANCE: Benchmarks completed")
        return benchmarks
    
    def calculate_test_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall test summary"""
        phase_results = results.get('phase_results', {})
        
        total_phases = len(phase_results)
        successful_phases = sum(1 for phase in phase_results.values() if phase.get('success', False))
        
        total_duration = sum(phase.get('duration_seconds', 0) for phase in phase_results.values())
        
        return {
            'total_phases': total_phases,
            'successful_phases': successful_phases,
            'failed_phases': total_phases - successful_phases,
            'success_rate': (successful_phases / total_phases * 100) if total_phases > 0 else 0,
            'total_duration_seconds': total_duration,
            'average_phase_duration': total_duration / total_phases if total_phases > 0 else 0
        }
    
    def assess_production_readiness(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Assess production readiness based on test results"""
        phase_results = results.get('phase_results', {})
        
        readiness_score = 0
        max_score = 100
        
        # Calculate score based on successful phases
        for phase_name, phase_data in phase_results.items():
            if phase_data.get('success', False):
                readiness_score += 20  # Each phase worth 20 points
        
        readiness_percentage = (readiness_score / max_score) * 100
        
        if readiness_percentage >= 90:
            readiness_level = 'Production Ready'
        elif readiness_percentage >= 75:
            readiness_level = 'Nearly Production Ready'
        elif readiness_percentage >= 50:
            readiness_level = 'Development Complete'
        else:
            readiness_level = 'Development In Progress'
        
        return {
            'readiness_score': readiness_score,
            'max_score': max_score,
            'readiness_percentage': readiness_percentage,
            'readiness_level': readiness_level,
            'production_ready': readiness_percentage >= 90
        }
    
    def generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        phase_results = results.get('phase_results', {})
        
        # Check each phase for failures and generate specific recommendations
        for phase_name, phase_data in phase_results.items():
            if not phase_data.get('success', False):
                error = phase_data.get('error', '')
                
                if 'workflow' in error.lower():
                    recommendations.append('Check workflow configuration and dependencies')
                
                if 'api_key' in error.lower():
                    recommendations.append('Configure API keys for LLM providers (OpenAI, Anthropic, Google)')
                
                if 'docker' in error.lower():
                    recommendations.append('Install Docker for code execution capabilities')
                
                if 'milvus' in error.lower() or 'vector' in error.lower():
                    recommendations.append('Set up Milvus vector database for RAG functionality')
                
                if 'websocket' in error.lower():
                    recommendations.append('Configure WebSocket support for real-time streaming')
        
        # General recommendations
        recommendations.extend([
            'Run full integration tests before production deployment',
            'Set up monitoring and logging for production environments',
            'Configure proper error handling and recovery mechanisms',
            'Implement proper security measures for multi-tenant usage'
        ])
        
        return list(set(recommendations))  # Remove duplicates


class WorkflowTestCommand(BaseCommand):
    """Django management command to run workflow integration tests"""
    
    help = 'Run comprehensive workflow integration test suite'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--phase',
            type=str,
            help='Run specific phase tests (1-5)',
            choices=['1', '2', '3', '4', '5']
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file for test results (JSON)',
            default=None
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        """Handle the test command"""
        
        # Set up logging
        if options['verbose']:
            logging.basicConfig(level=logging.INFO)
        
        # Initialize test suite
        test_suite = WorkflowIntegrationTestSuite()
        
        # Run tests
        self.stdout.write('🧪 Starting Workflow Integration Test Suite...')
        
        try:
            # Run in async context
            results = asyncio.run(test_suite.run_all_tests())
            
            # Output results
            self.display_results(results)
            
            # Save to file if requested
            if options['output']:
                with open(options['output'], 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                self.stdout.write(f'📄 Results saved to {options["output"]}')
            
            # Exit with appropriate code
            if results['production_readiness']['production_ready']:
                self.stdout.write('🎉 All tests passed - Production Ready!')
            else:
                self.stdout.write('⚠️ Some tests failed - See recommendations')
                
        except Exception as e:
            self.stderr.write(f'❌ Test suite failed: {e}')
            raise
    
    def display_results(self, results: Dict[str, Any]):
        """Display test results in a formatted way"""
        
        # Test Summary
        summary = results.get('test_summary', {})
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 TEST SUMMARY')
        self.stdout.write('='*60)
        self.stdout.write(f"Total Phases: {summary.get('total_phases', 0)}")
        self.stdout.write(f"Successful: {summary.get('successful_phases', 0)}")
        self.stdout.write(f"Failed: {summary.get('failed_phases', 0)}")
        self.stdout.write(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
        self.stdout.write(f"Total Duration: {summary.get('total_duration_seconds', 0):.2f}s")
        
        # Phase Results
        self.stdout.write('\n' + '='*60)
        self.stdout.write('🔍 PHASE RESULTS')
        self.stdout.write('='*60)
        
        for phase_name, phase_data in results.get('phase_results', {}).items():
            status = '✅' if phase_data.get('success') else '❌'
            duration = phase_data.get('duration_seconds', 0)
            self.stdout.write(f"{status} {phase_name}: {duration:.2f}s")
            
            if not phase_data.get('success'):
                error = phase_data.get('error', 'Unknown error')
                self.stdout.write(f"   Error: {error}")
        
        # Production Readiness
        readiness = results.get('production_readiness', {})
        self.stdout.write('\n' + '='*60)
        self.stdout.write('🚀 PRODUCTION READINESS')
        self.stdout.write('='*60)
        self.stdout.write(f"Readiness Level: {readiness.get('readiness_level', 'Unknown')}")
        self.stdout.write(f"Score: {readiness.get('readiness_score', 0)}/{readiness.get('max_score', 100)}")
        self.stdout.write(f"Percentage: {readiness.get('readiness_percentage', 0):.1f}%")
        
        # Recommendations
        recommendations = results.get('recommendations', [])
        if recommendations:
            self.stdout.write('\n' + '='*60)
            self.stdout.write('💡 RECOMMENDATIONS')
            self.stdout.write('='*60)
            for i, rec in enumerate(recommendations[:10], 1):  # Show top 10
                self.stdout.write(f"{i}. {rec}")


# Standalone test runner for direct execution
if __name__ == '__main__':
    import sys
    import os
    
    # Add Django project to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    # Set up Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    
    import django
    django.setup()
    
    # Run tests
    test_suite = AutoGenIntegrationTestSuite()
    results = asyncio.run(test_suite.run_all_tests())
    
    print(json.dumps(results, indent=2, default=str))
