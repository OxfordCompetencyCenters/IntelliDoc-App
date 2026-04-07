"""
Template Analytics System
Phase 5: Advanced Template Management

Provides comprehensive analytics and monitoring for templates including:
- Usage statistics and patterns
- Performance monitoring
- User behavior analysis
- Template popularity metrics
- Project success metrics
- Performance optimization insights
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, Counter
import statistics
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class TemplateUsageMetrics:
    """Template usage metrics data structure"""
    template_id: str
    total_projects: int
    active_projects: int
    completed_projects: int
    total_documents_processed: int
    total_processing_time: float
    average_project_duration: float
    success_rate: float
    user_satisfaction_score: float
    last_used: datetime
    created_date: datetime


@dataclass
class PerformanceMetrics:
    """Template performance metrics"""
    template_id: str
    average_processing_time: float
    median_processing_time: float
    min_processing_time: float
    max_processing_time: float
    total_api_calls: int
    error_rate: float
    memory_usage_avg: float
    cpu_usage_avg: float
    disk_usage: int


@dataclass
class UserBehaviorMetrics:
    """User behavior analytics for templates"""
    template_id: str
    bounce_rate: float
    session_duration_avg: float
    pages_per_session: float
    feature_usage: Dict[str, int]
    most_used_features: List[str]
    least_used_features: List[str]
    user_feedback: List[Dict]


@dataclass
class PopularityMetrics:
    """Template popularity and trend metrics"""
    template_id: str
    rank: int
    total_rank: int
    popularity_score: float
    trend_direction: str  # 'increasing', 'stable', 'decreasing'
    growth_rate: float
    category_rank: int
    similar_templates: List[str]


class TemplateAnalyticsService:
    """Advanced template analytics service"""
    
    def __init__(self):
        self.analytics_base_path = Path("logs/analytics")
        self.analytics_base_path.mkdir(parents=True, exist_ok=True)
        logger.info("Initialized TemplateAnalyticsService")
    
    def track_template_usage(self, template_id: str, action: str, 
                           metadata: Optional[Dict] = None) -> None:
        """Track template usage event"""
        logger.info(f"Tracking template usage: {template_id} - {action}")
        
        try:
            usage_event = {
                'template_id': template_id,
                'action': action,
                'timestamp': datetime.now().isoformat(),
                'metadata': metadata or {}
            }
            
            # Save to daily usage log
            date_str = datetime.now().strftime('%Y-%m-%d')
            usage_log_path = self.analytics_base_path / f"usage_{date_str}.json"
            
            # Load existing events
            if usage_log_path.exists():
                with open(usage_log_path, 'r') as f:
                    events = json.load(f)
            else:
                events = []
            
            events.append(usage_event)
            
            # Save updated events
            with open(usage_log_path, 'w') as f:
                json.dump(events, f, indent=2)
            
            logger.info(f"Template usage tracked successfully")
            
        except Exception as e:
            logger.error(f"Error tracking template usage: {str(e)}")
            raise
    
    def get_template_usage_metrics(self, template_id: str, 
                                 days: int = 30) -> TemplateUsageMetrics:
        """Get comprehensive usage metrics for a template"""
        logger.info(f"Getting usage metrics for template: {template_id} (last {days} days)")
        
        try:
            # Collect usage events from the specified period
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            usage_events = self._get_usage_events(template_id, start_date, end_date)
            
            # Calculate metrics
            total_projects = len(set(event.get('metadata', {}).get('project_id') 
                                   for event in usage_events 
                                   if event.get('metadata', {}).get('project_id')))
            
            active_projects = len(set(event.get('metadata', {}).get('project_id') 
                                    for event in usage_events 
                                    if event.get('action') in ['project_access', 'document_upload']
                                    and event.get('metadata', {}).get('project_id')))
            
            completed_projects = len(set(event.get('metadata', {}).get('project_id') 
                                       for event in usage_events 
                                       if event.get('action') == 'project_completed'
                                       and event.get('metadata', {}).get('project_id')))
            
            total_documents = sum(event.get('metadata', {}).get('document_count', 0) 
                                for event in usage_events 
                                if event.get('action') == 'document_upload')
            
            processing_times = [event.get('metadata', {}).get('processing_time', 0) 
                              for event in usage_events 
                              if event.get('action') == 'document_processed' 
                              and event.get('metadata', {}).get('processing_time')]
            
            total_processing_time = sum(processing_times)
            average_project_duration = statistics.mean(processing_times) if processing_times else 0
            
            # Calculate success rate
            successful_events = len([e for e in usage_events if e.get('metadata', {}).get('success', True)])
            success_rate = successful_events / len(usage_events) if usage_events else 0
            
            # Get user satisfaction (placeholder - would integrate with feedback system)
            user_satisfaction_score = 4.2  # Default value
            
            # Get creation date
            created_date = min(datetime.fromisoformat(event['timestamp']) 
                             for event in usage_events) if usage_events else datetime.now()
            
            # Get last used date
            last_used = max(datetime.fromisoformat(event['timestamp']) 
                          for event in usage_events) if usage_events else datetime.now()
            
            metrics = TemplateUsageMetrics(
                template_id=template_id,
                total_projects=total_projects,
                active_projects=active_projects,
                completed_projects=completed_projects,
                total_documents_processed=total_documents,
                total_processing_time=total_processing_time,
                average_project_duration=average_project_duration,
                success_rate=success_rate,
                user_satisfaction_score=user_satisfaction_score,
                last_used=last_used,
                created_date=created_date
            )
            
            logger.info(f"Usage metrics calculated successfully for {template_id}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting template usage metrics: {str(e)}")
            raise
    
    def get_performance_metrics(self, template_id: str, days: int = 30) -> PerformanceMetrics:
        """Get performance metrics for a template"""
        logger.info(f"Getting performance metrics for template: {template_id}")
        
        try:
            # Collect performance events
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            performance_events = self._get_performance_events(template_id, start_date, end_date)
            
            # Calculate performance metrics
            processing_times = [event.get('processing_time', 0) 
                              for event in performance_events 
                              if event.get('processing_time')]
            
            if processing_times:
                avg_processing_time = statistics.mean(processing_times)
                median_processing_time = statistics.median(processing_times)
                min_processing_time = min(processing_times)
                max_processing_time = max(processing_times)
            else:
                avg_processing_time = median_processing_time = min_processing_time = max_processing_time = 0
            
            total_api_calls = len([e for e in performance_events if e.get('type') == 'api_call'])
            
            error_events = len([e for e in performance_events if e.get('error', False)])
            error_rate = error_events / len(performance_events) if performance_events else 0
            
            # Resource usage metrics (placeholder values - would integrate with monitoring)
            memory_usage_avg = 128.5  # MB
            cpu_usage_avg = 15.2      # %
            disk_usage = 1024         # MB
            
            metrics = PerformanceMetrics(
                template_id=template_id,
                average_processing_time=avg_processing_time,
                median_processing_time=median_processing_time,
                min_processing_time=min_processing_time,
                max_processing_time=max_processing_time,
                total_api_calls=total_api_calls,
                error_rate=error_rate,
                memory_usage_avg=memory_usage_avg,
                cpu_usage_avg=cpu_usage_avg,
                disk_usage=disk_usage
            )
            
            logger.info(f"Performance metrics calculated successfully for {template_id}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            raise
    
    def get_user_behavior_metrics(self, template_id: str, days: int = 30) -> UserBehaviorMetrics:
        """Get user behavior metrics for a template"""
        logger.info(f"Getting user behavior metrics for template: {template_id}")
        
        try:
            # Collect user behavior events
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            behavior_events = self._get_behavior_events(template_id, start_date, end_date)
            
            # Calculate behavior metrics
            sessions = defaultdict(list)
            for event in behavior_events:
                session_id = event.get('metadata', {}).get('session_id')
                if session_id:
                    sessions[session_id].append(event)
            
            # Bounce rate (sessions with only one event)
            bounce_sessions = len([s for s in sessions.values() if len(s) == 1])
            bounce_rate = bounce_sessions / len(sessions) if sessions else 0
            
            # Session duration
            session_durations = []
            for session_events in sessions.values():
                if len(session_events) > 1:
                    start_time = min(datetime.fromisoformat(e['timestamp']) for e in session_events)
                    end_time = max(datetime.fromisoformat(e['timestamp']) for e in session_events)
                    duration = (end_time - start_time).total_seconds()
                    session_durations.append(duration)
            
            session_duration_avg = statistics.mean(session_durations) if session_durations else 0
            
            # Pages per session
            pages_per_session = statistics.mean([len(s) for s in sessions.values()]) if sessions else 0
            
            # Feature usage
            feature_usage = Counter()
            for event in behavior_events:
                feature = event.get('metadata', {}).get('feature')
                if feature:
                    feature_usage[feature] += 1
            
            most_used_features = [feature for feature, _ in feature_usage.most_common(5)]
            least_used_features = [feature for feature, _ in feature_usage.most_common()[-5:]]
            
            # User feedback (placeholder)
            user_feedback = []
            
            metrics = UserBehaviorMetrics(
                template_id=template_id,
                bounce_rate=bounce_rate,
                session_duration_avg=session_duration_avg,
                pages_per_session=pages_per_session,
                feature_usage=dict(feature_usage),
                most_used_features=most_used_features,
                least_used_features=least_used_features,
                user_feedback=user_feedback
            )
            
            logger.info(f"User behavior metrics calculated successfully for {template_id}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting user behavior metrics: {str(e)}")
            raise
    
    def get_popularity_metrics(self, template_id: str) -> PopularityMetrics:
        """Get popularity metrics for a template"""
        logger.info(f"Getting popularity metrics for template: {template_id}")
        
        try:
            # Get all templates for comparison
            all_templates = self._get_all_template_ids()
            
            # Calculate popularity scores
            template_scores = {}
            for tid in all_templates:
                usage_metrics = self.get_template_usage_metrics(tid, days=30)
                
                # Popularity algorithm (weighted score)
                score = (
                    usage_metrics.total_projects * 0.3 +
                    usage_metrics.active_projects * 0.4 +
                    usage_metrics.success_rate * 100 * 0.2 +
                    usage_metrics.user_satisfaction_score * 20 * 0.1
                )
                template_scores[tid] = score
            
            # Sort by popularity
            sorted_templates = sorted(template_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Find rank for this template
            rank = next((i + 1 for i, (tid, _) in enumerate(sorted_templates) if tid == template_id), 
                       len(sorted_templates))
            
            total_rank = len(sorted_templates)
            popularity_score = template_scores.get(template_id, 0)
            
            # Calculate trend (simplified - would use historical data)
            trend_direction = "stable"  # Placeholder
            growth_rate = 0.05  # 5% growth placeholder
            
            # Category rank (placeholder)
            category_rank = rank
            
            # Similar templates (placeholder)
            similar_templates = []
            
            metrics = PopularityMetrics(
                template_id=template_id,
                rank=rank,
                total_rank=total_rank,
                popularity_score=popularity_score,
                trend_direction=trend_direction,
                growth_rate=growth_rate,
                category_rank=category_rank,
                similar_templates=similar_templates
            )
            
            logger.info(f"Popularity metrics calculated successfully for {template_id}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting popularity metrics: {str(e)}")
            raise
    
    def generate_analytics_report(self, template_id: str, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive analytics report for a template"""
        logger.info(f"Generating analytics report for template: {template_id}")
        
        try:
            usage_metrics = self.get_template_usage_metrics(template_id, days)
            performance_metrics = self.get_performance_metrics(template_id, days)
            behavior_metrics = self.get_user_behavior_metrics(template_id, days)
            popularity_metrics = self.get_popularity_metrics(template_id)
            
            report = {
                'template_id': template_id,
                'report_date': datetime.now().isoformat(),
                'period_days': days,
                'usage_metrics': asdict(usage_metrics),
                'performance_metrics': asdict(performance_metrics),
                'behavior_metrics': asdict(behavior_metrics),
                'popularity_metrics': asdict(popularity_metrics),
                'insights': self._generate_insights(usage_metrics, performance_metrics, 
                                                   behavior_metrics, popularity_metrics)
            }
            
            # Save report
            report_path = self.analytics_base_path / f"report_{template_id}_{datetime.now().strftime('%Y%m%d')}.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Analytics report generated successfully: {report_path}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating analytics report: {str(e)}")
            raise
    
    def _get_usage_events(self, template_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get usage events for a template within date range"""
        events = []
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            usage_log_path = self.analytics_base_path / f"usage_{date_str}.json"
            
            if usage_log_path.exists():
                try:
                    with open(usage_log_path, 'r') as f:
                        daily_events = json.load(f)
                    
                    # Filter events for this template
                    template_events = [e for e in daily_events if e.get('template_id') == template_id]
                    events.extend(template_events)
                    
                except Exception as e:
                    logger.warning(f"Error reading usage log {usage_log_path}: {str(e)}")
            
            current_date += timedelta(days=1)
        
        return events
    
    def _get_performance_events(self, template_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get performance events for a template"""
        # Placeholder - would integrate with actual performance monitoring
        return [
            {
                'template_id': template_id,
                'type': 'api_call',
                'processing_time': 1.5,
                'timestamp': datetime.now().isoformat(),
                'error': False
            }
        ]
    
    def _get_behavior_events(self, template_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get user behavior events for a template"""
        # Placeholder - would integrate with user behavior tracking
        return [
            {
                'template_id': template_id,
                'action': 'page_view',
                'timestamp': datetime.now().isoformat(),
                'metadata': {
                    'session_id': 'session_123',
                    'feature': 'document_upload'
                }
            }
        ]
    
    def _get_all_template_ids(self) -> List[str]:
        """Get all available template IDs"""
        # Placeholder - would get from actual template discovery
        return ['aicc-intellidoc', 'legal', 'medical', 'history']
    
    def _generate_insights(self, usage_metrics: TemplateUsageMetrics, 
                          performance_metrics: PerformanceMetrics,
                          behavior_metrics: UserBehaviorMetrics, 
                          popularity_metrics: PopularityMetrics) -> List[str]:
        """Generate insights based on metrics"""
        insights = []
        
        # Usage insights
        if usage_metrics.success_rate > 0.9:
            insights.append("High success rate indicates excellent template reliability")
        elif usage_metrics.success_rate < 0.7:
            insights.append("Low success rate suggests template needs improvement")
        
        # Performance insights
        if performance_metrics.error_rate > 0.1:
            insights.append("High error rate may indicate performance issues")
        
        if performance_metrics.average_processing_time > 30:
            insights.append("Long processing times may affect user experience")
        
        # Behavior insights
        if behavior_metrics.bounce_rate > 0.5:
            insights.append("High bounce rate suggests users are not finding value quickly")
        
        # Popularity insights
        if popularity_metrics.rank <= 3:
            insights.append("Template is performing very well in popularity rankings")
        elif popularity_metrics.rank > popularity_metrics.total_rank * 0.8:
            insights.append("Template has low popularity and may need promotion")
        
        return insights
