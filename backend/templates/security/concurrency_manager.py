import os
import time
import threading
import uuid
from contextlib import contextmanager
from typing import Dict, List, Optional, Set
from pathlib import Path
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

# Import the models from the main models file
from ..models import TemplateOperation, TemplateOperationType, TemplateOperationStatus

class TemplateOperationLock:
    """Distributed locking mechanism for template operations"""
    
    LOCK_TIMEOUT = 300  # 5 minutes
    LOCK_PREFIX = 'template_operation_lock_'
    
    def __init__(self, lock_key: str):
        self.lock_key = lock_key
        self.cache_key = f"{self.LOCK_PREFIX}{lock_key}"
        self.lock_id = str(uuid.uuid4())
        self.acquired = False
    
    def acquire(self, blocking: bool = True, timeout: float = None) -> bool:
        """Acquire distributed lock"""
        if timeout is None:
            timeout = self.LOCK_TIMEOUT
        
        start_time = time.time()
        
        while True:
            # Try to acquire lock
            if cache.add(self.cache_key, self.lock_id, timeout=self.LOCK_TIMEOUT):
                self.acquired = True
                logger.debug(f"Acquired lock: {self.lock_key}")
                return True
            
            # Check if we own the lock
            current_lock = cache.get(self.cache_key)
            if current_lock == self.lock_id:
                self.acquired = True
                return True
            
            # Non-blocking mode
            if not blocking:
                return False
            
            # Check timeout
            if time.time() - start_time > timeout:
                logger.warning(f"Lock acquisition timeout: {self.lock_key}")
                return False
            
            # Wait and retry
            time.sleep(0.1)
    
    def release(self):
        """Release distributed lock"""
        if self.acquired:
            # Only release if we own the lock
            current_lock = cache.get(self.cache_key)
            if current_lock == self.lock_id:
                cache.delete(self.cache_key)
                logger.debug(f"Released lock: {self.lock_key}")
            
            self.acquired = False
    
    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self.lock_key}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

class TemplateOperationManager:
    """Manages template operations with concurrency control"""
    
    @classmethod
    def start_operation(cls, operation_type: str, template_id: str, user, details: Dict = None) -> TemplateOperation:
        """Start a new template operation"""
        operation = TemplateOperation.objects.create(
            operation_type=operation_type,
            template_id=template_id,
            user=user,
            details=details or {},
            lock_key=f"{operation_type}:{template_id}"
        )
        
        operation.status = TemplateOperationStatus.RUNNING
        operation.save()
        
        logger.info(f"Started operation {operation.operation_id}: {operation_type} on {template_id}")
        return operation
    
    @classmethod
    def finish_operation(cls, operation: TemplateOperation, success: bool = True, 
                        result: Dict = None, error_message: str = None):
        """Finish a template operation"""
        operation.mark_completed(result=result, error_message=error_message)
        
        if success:
            logger.info(f"Completed operation {operation.operation_id}: {operation.operation_type}")
        else:
            logger.error(f"Failed operation {operation.operation_id}: {error_message}")
    
    @classmethod
    def get_active_operations(cls, template_id: str = None) -> List[TemplateOperation]:
        """Get currently active operations"""
        queryset = TemplateOperation.objects.filter(
            status__in=[TemplateOperationStatus.PENDING, TemplateOperationStatus.RUNNING]
        )
        
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        
        return list(queryset)
    
    @classmethod
    def check_for_conflicts(cls, operation_type: str, template_id: str, user) -> List[str]:
        """Check for conflicting operations"""
        conflicts = []
        
        # Get active operations for this template
        active_ops = cls.get_active_operations(template_id)
        
        for op in active_ops:
            if op.operation_type == operation_type and op.user != user:
                conflicts.append(f"Another {operation_type} operation is in progress by {op.user.email}")
            elif op.operation_type == TemplateOperationType.DELETE:
                conflicts.append(f"Template is being deleted by {op.user.email}")
        
        return conflicts
    
    @classmethod
    def cancel_operation(cls, operation_id: str, user) -> bool:
        """Cancel an operation"""
        try:
            operation = TemplateOperation.objects.get(operation_id=operation_id, user=user)
            
            if operation.status in [TemplateOperationStatus.PENDING, TemplateOperationStatus.RUNNING]:
                operation.status = TemplateOperationStatus.CANCELLED
                operation.completed_at = timezone.now()
                operation.save()
                
                logger.info(f"Cancelled operation {operation_id}")
                return True
            
            return False
            
        except TemplateOperation.DoesNotExist:
            return False
    
    @classmethod
    def cleanup_stale_operations(cls, max_age_hours: int = 24):
        """Clean up stale operations"""
        cutoff_time = timezone.now() - timezone.timedelta(hours=max_age_hours)
        
        # Mark old running operations as failed
        stale_ops = TemplateOperation.objects.filter(
            status__in=[TemplateOperationStatus.PENDING, TemplateOperationStatus.RUNNING],
            started_at__lt=cutoff_time
        )
        
        for op in stale_ops:
            op.status = TemplateOperationStatus.FAILED
            op.error_message = f"Operation timed out after {max_age_hours} hours"
            op.completed_at = timezone.now()
            op.save()
        
        logger.info(f"Cleaned up {stale_ops.count()} stale operations")
    
    @classmethod
    @contextmanager
    def template_operation(cls, operation_type: str, template_id: str, user, details: Dict = None):
        """Context manager for template operations"""
        operation = None
        lock = None
        
        try:
            # Check for conflicts
            conflicts = cls.check_for_conflicts(operation_type, template_id, user)
            if conflicts:
                raise ValueError(f"Conflicting operations: {', '.join(conflicts)}")
            
            # Acquire distributed lock
            lock_key = f"{operation_type}:{template_id}"
            lock = TemplateOperationLock(lock_key)
            if not lock.acquire(blocking=False):
                raise RuntimeError(f"Could not acquire lock for {operation_type} on {template_id}")
            
            # Start operation
            operation = cls.start_operation(operation_type, template_id, user, details)
            
            yield operation
            
            # Mark as successful
            cls.finish_operation(operation, success=True)
            
        except Exception as e:
            if operation:
                cls.finish_operation(operation, success=False, error_message=str(e))
            raise
        finally:
            if lock:
                lock.release()

class TemplateOperationMonitor:
    """Monitor template operations and provide statistics"""
    
    @classmethod
    def get_operation_stats(cls, hours: int = 24) -> Dict:
        """Get operation statistics for the last N hours"""
        from django.db import models
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        operations = TemplateOperation.objects.filter(started_at__gte=cutoff_time)
        
        stats = {
            'total_operations': operations.count(),
            'by_type': {},
            'by_status': {},
            'by_user': {},
            'average_duration': 0,
            'success_rate': 0
        }
        
        # Group by type
        for op_type in TemplateOperationType.choices:
            count = operations.filter(operation_type=op_type[0]).count()
            stats['by_type'][op_type[1]] = count
        
        # Group by status
        for status in TemplateOperationStatus.choices:
            count = operations.filter(status=status[0]).count()
            stats['by_status'][status[1]] = count
        
        # Group by user
        user_stats = operations.values('user__email').annotate(count=models.Count('id'))
        for user_stat in user_stats:
            stats['by_user'][user_stat['user__email']] = user_stat['count']
        
        # Calculate averages
        completed_ops = operations.filter(status=TemplateOperationStatus.COMPLETED)
        if completed_ops.exists():
            durations = completed_ops.values_list('duration_seconds', flat=True)
            stats['average_duration'] = sum(durations) / len(durations)
        
        # Calculate success rate
        if operations.exists():
            success_count = operations.filter(status=TemplateOperationStatus.COMPLETED).count()
            stats['success_rate'] = (success_count / operations.count()) * 100
        
        return stats
    
    @classmethod
    def get_template_activity(cls, template_id: str, hours: int = 24) -> Dict:
        """Get activity for a specific template"""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        operations = TemplateOperation.objects.filter(
            template_id=template_id,
            started_at__gte=cutoff_time
        )
        
        return {
            'template_id': template_id,
            'total_operations': operations.count(),
            'recent_operations': [
                {
                    'type': op.operation_type,
                    'status': op.status,
                    'user': op.user.email,
                    'started_at': op.started_at,
                    'duration': op.duration_seconds
                }
                for op in operations.order_by('-started_at')[:10]
            ]
        }
    
    @classmethod
    def get_active_locks(cls) -> List[Dict]:
        """Get information about active locks"""
        # This would need to be implemented based on your cache backend
        # For now, return empty list
        return []
