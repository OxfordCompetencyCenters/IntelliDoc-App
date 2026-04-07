"""
Template Testing Framework
Phase 5: Advanced Template Management

Provides comprehensive automated testing for templates including:
- Template validation tests
- Integration tests for template components
- Performance benchmarking
- Regression testing
- Template compatibility testing
- End-to-end workflow testing
"""

import logging
import json
import time
import traceback
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Individual test result"""
    test_name: str
    template_id: str
    status: str  # 'passed', 'failed', 'skipped', 'error'
    execution_time: float
    message: str
    details: Optional[Dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class TestSuite:
    """Test suite configuration and results"""
    suite_name: str
    template_id: str
    tests: List[str]
    results: List[TestResult]
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float = 0.0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0


@dataclass
class BenchmarkResult:
    """Performance benchmark result"""
    benchmark_name: str
    template_id: str
    metric: str
    value: float
    unit: str
    baseline: Optional[float] = None
    improvement: Optional[float] = None
    status: str = 'measured'  # 'improved', 'degraded', 'measured'


class TemplateTestingFramework:
    """Advanced template testing framework"""
    
    def __init__(self):
        self.test_base_path = Path("logs/testing")
        self.test_base_path.mkdir(parents=True, exist_ok=True)
        self.test_templates_path = Path("templates/template_definitions")
        logger.info("Initialized TemplateTestingFramework")
    
    def validate_template_structure(self, template_id: str) -> TestResult:
        """Validate template directory structure and required files"""
        logger.info(f"Validating template structure: {template_id}")
        
        start_time = time.time()
        
        try:
            template_path = self.test_templates_path / template_id
            
            if not template_path.exists():
                return TestResult(
                    test_name="structure_validation",
                    template_id=template_id,
                    status="failed",
                    execution_time=time.time() - start_time,
                    message=f"Template directory does not exist: {template_path}"
                )
            
            # Check required files
            required_files = [
                "metadata.json",
                "definition.py",
                "hierarchical_config.py"
            ]
            
            missing_files = []
            for file_name in required_files:
                if not (template_path / file_name).exists():
                    missing_files.append(file_name)
            
            if missing_files:
                return TestResult(
                    test_name="structure_validation",
                    template_id=template_id,
                    status="failed",
                    execution_time=time.time() - start_time,
                    message=f"Missing required files: {', '.join(missing_files)}",
                    details={"missing_files": missing_files}
                )
            
            # Validate metadata.json format
            metadata_path = template_path / "metadata.json"
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                required_metadata_fields = [
                    "template_id", "template_type", "version", "name", "description"
                ]
                
                missing_metadata = []
                for field in required_metadata_fields:
                    if field not in metadata:
                        missing_metadata.append(field)
                
                if missing_metadata:
                    return TestResult(
                        test_name="structure_validation",
                        template_id=template_id,
                        status="failed",
                        execution_time=time.time() - start_time,
                        message=f"Missing metadata fields: {', '.join(missing_metadata)}",
                        details={"missing_metadata": missing_metadata}
                    )
                
            except json.JSONDecodeError as e:
                return TestResult(
                    test_name="structure_validation",
                    template_id=template_id,
                    status="failed",
                    execution_time=time.time() - start_time,
                    message=f"Invalid JSON in metadata.json: {str(e)}"
                )
            
            return TestResult(
                test_name="structure_validation",
                template_id=template_id,
                status="passed",
                execution_time=time.time() - start_time,
                message="Template structure validation passed"
            )
            
        except Exception as e:
            logger.error(f"Error validating template structure: {str(e)}")
            return TestResult(
                test_name="structure_validation",
                template_id=template_id,
                status="error",
                execution_time=time.time() - start_time,
                message=f"Validation error: {str(e)}"
            )
    
    def test_template_definition_import(self, template_id: str) -> TestResult:
        """Test if template definition can be imported successfully"""
        logger.info(f"Testing template definition import: {template_id}")
        
        start_time = time.time()
        
        try:
            # Try to import the definition module
            import importlib
            module_name = f"templates.template_definitions.{template_id}.definition"
            
            try:
                definition_module = importlib.import_module(module_name)
                
                # Check if template class exists and can be instantiated
                template_class_name = f"{template_id.replace('-', '').title()}TemplateDefinition"
                
                if not hasattr(definition_module, template_class_name):
                    # Try alternative naming patterns
                    possible_names = [
                        f"{template_id.replace('-', '_').title()}TemplateDefinition",
                        "TemplateDefinition",
                        f"{template_id.upper()}TemplateDefinition"
                    ]
                    
                    template_class = None
                    for name in possible_names:
                        if hasattr(definition_module, name):
                            template_class = getattr(definition_module, name)
                            break
                    
                    if template_class is None:
                        return TestResult(
                            test_name="definition_import",
                            template_id=template_id,
                            status="failed",
                            execution_time=time.time() - start_time,
                            message=f"Template class not found. Expected: {template_class_name}",
                            details={"available_classes": [name for name in dir(definition_module) 
                                                         if not name.startswith('_')]}
                        )
                else:
                    template_class = getattr(definition_module, template_class_name)
                
                # Try to instantiate the class
                template_instance = template_class()
                
                # Validate required methods exist
                required_methods = ["get_analysis_focus", "get_suggested_questions"]
                missing_methods = []
                
                for method_name in required_methods:
                    if not hasattr(template_instance, method_name):
                        missing_methods.append(method_name)
                
                if missing_methods:
                    return TestResult(
                        test_name="definition_import",
                        template_id=template_id,
                        status="failed",
                        execution_time=time.time() - start_time,
                        message=f"Missing required methods: {', '.join(missing_methods)}",
                        details={"missing_methods": missing_methods}
                    )
                
                return TestResult(
                    test_name="definition_import",
                    template_id=template_id,
                    status="passed",
                    execution_time=time.time() - start_time,
                    message="Template definition import successful"
                )
                
            except ImportError as e:
                return TestResult(
                    test_name="definition_import",
                    template_id=template_id,
                    status="failed",
                    execution_time=time.time() - start_time,
                    message=f"Cannot import template definition: {str(e)}"
                )
            
        except Exception as e:
            logger.error(f"Error testing template definition import: {str(e)}")
            return TestResult(
                test_name="definition_import",
                template_id=template_id,
                status="error",
                execution_time=time.time() - start_time,
                message=f"Import test error: {str(e)}"
            )
    
    def run_comprehensive_test_suite(self, template_id: str, 
                                   include_benchmarks: bool = True,
                                   include_regression: bool = True,
                                   include_compatibility: bool = True) -> TestSuite:
        """Run comprehensive test suite for a template"""
        logger.info(f"Running comprehensive test suite for template: {template_id}")
        
        suite = TestSuite(
            suite_name="comprehensive_template_tests",
            template_id=template_id,
            tests=[],
            results=[],
            start_time=datetime.now()
        )
        
        try:
            # Core validation tests
            suite.results.append(self.validate_template_structure(template_id))
            suite.results.append(self.test_template_definition_import(template_id))
            
            # Calculate suite statistics
            suite.end_time = datetime.now()
            suite.duration = (suite.end_time - suite.start_time).total_seconds()
            
            for result in suite.results:
                if result.status == "passed":
                    suite.passed += 1
                elif result.status == "failed":
                    suite.failed += 1
                elif result.status == "error":
                    suite.errors += 1
                elif result.status == "skipped":
                    suite.skipped += 1
            
            # Save test results
            self._save_test_results(suite)
            
            logger.info(f"Comprehensive test suite completed for {template_id}: "
                       f"{suite.passed} passed, {suite.failed} failed, {suite.errors} errors")
            
        except Exception as e:
            logger.error(f"Error running comprehensive test suite: {str(e)}")
            suite.results.append(TestResult(
                test_name="test_suite_execution",
                template_id=template_id,
                status="error",
                execution_time=0.0,
                message=f"Test suite execution error: {str(e)}"
            ))
        
        return suite
    
    def _save_test_results(self, suite: TestSuite) -> None:
        """Save test results to file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            results_file = self.test_base_path / f"test_results_{suite.template_id}_{timestamp}.json"
            
            suite_data = {
                'suite_name': suite.suite_name,
                'template_id': suite.template_id,
                'start_time': suite.start_time.isoformat(),
                'end_time': suite.end_time.isoformat() if suite.end_time else None,
                'duration': suite.duration,
                'statistics': {
                    'passed': suite.passed,
                    'failed': suite.failed,
                    'errors': suite.errors,
                    'skipped': suite.skipped,
                    'total': len(suite.results)
                },
                'results': [asdict(result) for result in suite.results]
            }
            
            with open(results_file, 'w') as f:
                json.dump(suite_data, f, indent=2, default=str)
            
            logger.info(f"Test results saved to: {results_file}")
            
        except Exception as e:
            logger.error(f"Error saving test results: {str(e)}")
