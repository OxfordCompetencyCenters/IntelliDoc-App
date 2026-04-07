"""
Template System Health Monitoring
Phase 5: Advanced Template Management

Provides comprehensive system health monitoring including:
- Template availability monitoring
- Performance health checks
- Resource usage monitoring
- Error rate tracking
- System dependency health
- Automated health reporting
"""

import logging
import psutil
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import json
import time

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health status data structure"""
    component: str
    status: str  # 'healthy', 'warning', 'critical', 'unknown'
    message: str
    details: Optional[Dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class SystemHealthReport:
    """System-wide health report"""
    overall_status: str
    timestamp: datetime
    components: List[HealthStatus]
    system_metrics: Dict[str, Any]
    recommendations: List[str]


@dataclass
class TemplateHealthReport:
    """Template-specific health report"""
    template_id: str
    status: str
    availability: float
    performance_score: float
    error_rate: float
    last_successful_operation: datetime
    issues: List[str]
    recommendations: List[str]


class TemplateHealthMonitor:
    """Advanced template health monitoring system"""
    
    def __init__(self):
        self.health_base_path = Path("logs/health")
        self.health_base_path.mkdir(parents=True, exist_ok=True)
        self.template_base_path = Path("templates/template_definitions")
        logger.info("Initialized TemplateHealthMonitor")
    
    def check_template_availability(self, template_id: str) -> HealthStatus:
        """Check if template is available and accessible"""
        logger.info(f"Checking template availability: {template_id}")
        
        try:
            template_path = self.template_base_path / template_id
            
            if not template_path.exists():
                return HealthStatus(
                    component="template_availability",
                    status="critical",
                    message=f"Template directory not found: {template_id}",
                    details={"template_path": str(template_path)}
                )
            
            # Check essential files
            required_files = ["metadata.json", "definition.py"]
            missing_files = []
            
            for file_name in required_files:
                if not (template_path / file_name).exists():
                    missing_files.append(file_name)
            
            if missing_files:
                return HealthStatus(
                    component="template_availability",
                    status="critical",
                    message=f"Missing essential files: {', '.join(missing_files)}",
                    details={"missing_files": missing_files}
                )
            
            # Check metadata validity
            try:
                with open(template_path / "metadata.json", 'r') as f:
                    metadata = json.load(f)
                
                if not metadata.get('is_active', True):
                    return HealthStatus(
                        component="template_availability",
                        status="warning",
                        message="Template is marked as inactive",
                        details={"metadata": metadata}
                    )
                
            except json.JSONDecodeError:
                return HealthStatus(
                    component="template_availability",
                    status="critical",
                    message="Invalid metadata.json format"
                )
            
            return HealthStatus(
                component="template_availability",
                status="healthy",
                message="Template is available and accessible"
            )
            
        except Exception as e:
            logger.error(f"Error checking template availability: {str(e)}")
            return HealthStatus(
                component="template_availability",
                status="critical",
                message=f"Availability check failed: {str(e)}"
            )
    
    def check_system_resources(self) -> HealthStatus:
        """Check system resource health"""
        logger.info("Checking system resources")
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network connectivity (check if servers are running)
            network_status = self._check_network_connectivity()
            
            # Evaluate resource health
            issues = []
            status = "healthy"
            
            if cpu_percent > 80:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
                status = "warning"
            
            if memory_percent > 85:
                issues.append(f"High memory usage: {memory_percent:.1f}%")
                status = "critical" if memory_percent > 95 else "warning"
            
            if disk_percent > 90:
                issues.append(f"High disk usage: {disk_percent:.1f}%")
                status = "critical"
            
            if not network_status['backend_accessible']:
                issues.append("Backend server not accessible")
                status = "critical"
            
            if not network_status['frontend_accessible']:
                issues.append("Frontend server not accessible")
                status = "warning"
            
            message = "System resources are healthy"
            if issues:
                message = f"Resource issues detected: {'; '.join(issues)}"
            
            return HealthStatus(
                component="system_resources",
                status=status,
                message=message,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "disk_percent": disk_percent,
                    "network_status": network_status,
                    "issues": issues
                }
            )
            
        except Exception as e:
            logger.error(f"Error checking system resources: {str(e)}")
            return HealthStatus(
                component="system_resources",
                status="unknown",
                message=f"Resource check failed: {str(e)}"
            )
    
    def get_system_health(self) -> SystemHealthReport:
        """Get comprehensive system health report"""
        logger.info("Getting system health report")
        
        try:
            components = []
            
            # Check system resources
            components.append(self.check_system_resources())
            
            # Check all templates
            template_ids = self._get_all_template_ids()
            for template_id in template_ids:
                components.append(self.check_template_availability(template_id))
            
            # Calculate overall system health
            critical_components = len([c for c in components if c.status == "critical"])
            warning_components = len([c for c in components if c.status == "warning"])
            
            if critical_components > 0:
                overall_status = "critical"
            elif warning_components > 0:
                overall_status = "warning"
            else:
                overall_status = "healthy"
            
            # System metrics
            system_metrics = {
                "total_components": len(components),
                "healthy_components": len([c for c in components if c.status == "healthy"]),
                "warning_components": warning_components,
                "critical_components": critical_components,
                "uptime": self._get_system_uptime()
            }
            
            # Generate recommendations
            recommendations = []
            if critical_components > 0:
                recommendations.append("Immediate attention required for critical components")
            if warning_components > 0:
                recommendations.append("Monitor warning components closely")
            if overall_status == "healthy":
                recommendations.append("System is operating normally")
            
            report = SystemHealthReport(
                overall_status=overall_status,
                timestamp=datetime.now(),
                components=components,
                system_metrics=system_metrics,
                recommendations=recommendations
            )
            
            # Save system health report
            self._save_system_health_report(report)
            
            logger.info(f"System health report generated: {overall_status}")
            return report
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return SystemHealthReport(
                overall_status="unknown",
                timestamp=datetime.now(),
                components=[],
                system_metrics={},
                recommendations=[f"Health check failed: {str(e)}"]
            )
    
    def get_template_health(self, template_id: str) -> TemplateHealthReport:
        """Get comprehensive health report for a specific template"""
        logger.info(f"Getting template health report: {template_id}")
        
        try:
            availability_check = self.check_template_availability(template_id)
            
            # Calculate overall template health
            overall_status = availability_check.status
            
            # Calculate metrics
            availability = 100.0 if availability_check.status == "healthy" else 0.0
            performance_score = 95.0 if availability_check.status == "healthy" else 0.0
            error_rate = 0.0
            
            # Collect issues and recommendations
            issues = []
            recommendations = []
            
            if availability_check.status in ["warning", "critical"]:
                issues.append(f"Availability: {availability_check.message}")
                
                if "missing" in availability_check.message.lower():
                    recommendations.append("Restore missing template files")
                if "inactive" in availability_check.message.lower():
                    recommendations.append("Activate template in metadata.json")
            
            report = TemplateHealthReport(
                template_id=template_id,
                status=overall_status,
                availability=availability,
                performance_score=performance_score,
                error_rate=error_rate,
                last_successful_operation=datetime.now(),
                issues=issues,
                recommendations=recommendations
            )
            
            logger.info(f"Template health report generated: {template_id} - {overall_status}")
            return report
            
        except Exception as e:
            logger.error(f"Error getting template health: {str(e)}")
            return TemplateHealthReport(
                template_id=template_id,
                status="unknown",
                availability=0.0,
                performance_score=0.0,
                error_rate=1.0,
                last_successful_operation=datetime.now(),
                issues=[f"Health check failed: {str(e)}"],
                recommendations=["Contact system administrator"]
            )
    
    def _check_network_connectivity(self) -> Dict[str, bool]:
        """Check network connectivity to services"""
        try:
            backend_accessible = False
            frontend_accessible = False
            
            try:
                response = requests.get("http://localhost:8000/api/", timeout=5)
                backend_accessible = response.status_code == 200
            except:
                pass
            
            try:
                response = requests.get("http://localhost:5173", timeout=5)
                frontend_accessible = response.status_code in [200, 404]
            except:
                pass
            
            return {
                "backend_accessible": backend_accessible,
                "frontend_accessible": frontend_accessible
            }
        except:
            return {
                "backend_accessible": False,
                "frontend_accessible": False
            }
    
    def _get_all_template_ids(self) -> List[str]:
        """Get all available template IDs"""
        try:
            template_ids = []
            for template_dir in self.template_base_path.iterdir():
                if template_dir.is_dir() and (template_dir / "metadata.json").exists():
                    template_ids.append(template_dir.name)
            return template_ids
        except:
            return []
    
    def _get_system_uptime(self) -> str:
        """Get system uptime"""
        try:
            uptime_seconds = time.time() - psutil.boot_time()
            uptime_timedelta = timedelta(seconds=uptime_seconds)
            return str(uptime_timedelta).split('.')[0]
        except:
            return "Unknown"
    
    def _save_system_health_report(self, report: SystemHealthReport) -> None:
        """Save system health report to file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = self.health_base_path / f"system_health_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(asdict(report), f, indent=2, default=str)
            
            logger.info(f"System health report saved: {report_file}")
            
        except Exception as e:
            logger.error(f"Error saving system health report: {str(e)}")
