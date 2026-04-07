"""
Upload Progress Tracking for Bulk Document Upload
Simple progress tracking using Django cache or session storage
"""
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('public_chatbot.upload')


class UploadProgressTracker:
    """
    Track progress of bulk upload operations
    """
    
    def __init__(self, session_key: str = None):
        self.session_key = session_key or str(uuid.uuid4())
        self.cache_prefix = f"upload_progress_{self.session_key}"
        self.timeout = 3600  # 1 hour timeout
    
    def start_upload(self, total_files: int, user_id: str = None) -> str:
        """
        Start tracking an upload session
        
        Args:
            total_files: Total number of files to process
            user_id: Optional user identifier
            
        Returns:
            Session key for tracking
        """
        progress_data = {
            'session_key': self.session_key,
            'status': 'started',
            'total_files': total_files,
            'processed_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'current_file': None,
            'current_stage': 'initializing',
            'error_messages': [],
            'warning_messages': [],
            'start_time': timezone.now().isoformat(),
            'last_update': timezone.now().isoformat(),
            'user_id': user_id,
            'percentage': 0.0
        }
        
        cache.set(self.cache_prefix, progress_data, self.timeout)
        logger.info(f"📊 PROGRESS: Started upload tracking for {total_files} files (session: {self.session_key})")
        
        return self.session_key
    
    def update_progress(self, 
                       current_file: str = None,
                       stage: str = None,
                       processed_count: int = None,
                       successful_count: int = None,
                       failed_count: int = None,
                       error_message: str = None,
                       warning_message: str = None) -> bool:
        """
        Update progress information
        
        Args:
            current_file: Name of currently processing file
            stage: Current processing stage
            processed_count: Total files processed so far
            successful_count: Successfully processed files
            failed_count: Failed files
            error_message: Error message to add
            warning_message: Warning message to add
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            progress_data = cache.get(self.cache_prefix)
            if not progress_data:
                logger.warning(f"📊 PROGRESS: No progress data found for session {self.session_key}")
                return False
            
            # Update fields if provided
            if current_file is not None:
                progress_data['current_file'] = current_file
            
            if stage is not None:
                progress_data['current_stage'] = stage
            
            if processed_count is not None:
                progress_data['processed_files'] = processed_count
            
            if successful_count is not None:
                progress_data['successful_files'] = successful_count
            
            if failed_count is not None:
                progress_data['failed_files'] = failed_count
            
            if error_message:
                progress_data['error_messages'].append({
                    'timestamp': timezone.now().isoformat(),
                    'message': error_message
                })
            
            if warning_message:
                progress_data['warning_messages'].append({
                    'timestamp': timezone.now().isoformat(),
                    'message': warning_message
                })
            
            # Calculate percentage
            total_files = progress_data['total_files']
            if total_files > 0:
                progress_data['percentage'] = (progress_data['processed_files'] / total_files) * 100
            
            # Update timestamp
            progress_data['last_update'] = timezone.now().isoformat()
            
            # Update cache
            cache.set(self.cache_prefix, progress_data, self.timeout)
            
            return True
            
        except Exception as e:
            logger.error(f"📊 PROGRESS: Error updating progress for {self.session_key}: {e}")
            return False
    
    def complete_upload(self, final_status: str = 'completed', summary: Dict[str, Any] = None):
        """
        Mark upload as completed
        
        Args:
            final_status: Final status (completed, failed, cancelled)
            summary: Final summary information
        """
        try:
            progress_data = cache.get(self.cache_prefix)
            if not progress_data:
                return
            
            progress_data['status'] = final_status
            progress_data['current_stage'] = 'finished'
            progress_data['end_time'] = timezone.now().isoformat()
            progress_data['percentage'] = 100.0
            
            if summary:
                progress_data['summary'] = summary
            
            # Calculate duration
            start_time = datetime.fromisoformat(progress_data['start_time'].replace('Z', '+00:00'))
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            progress_data['duration_seconds'] = duration
            
            # Keep completed progress for longer
            extended_timeout = 7200  # 2 hours
            cache.set(self.cache_prefix, progress_data, extended_timeout)
            
            logger.info(f"📊 PROGRESS: Completed upload tracking for session {self.session_key} in {duration:.1f}s")
            
        except Exception as e:
            logger.error(f"📊 PROGRESS: Error completing progress for {self.session_key}: {e}")
    
    def get_progress(self) -> Optional[Dict[str, Any]]:
        """
        Get current progress information
        
        Returns:
            Progress data dictionary or None if not found
        """
        try:
            progress_data = cache.get(self.cache_prefix)
            if progress_data:
                # Add time remaining estimate
                if progress_data['percentage'] > 0 and progress_data['status'] != 'completed':
                    start_time = datetime.fromisoformat(progress_data['start_time'].replace('Z', '+00:00'))
                    elapsed = (timezone.now() - start_time).total_seconds()
                    if progress_data['percentage'] < 100:
                        estimated_total = elapsed * (100 / progress_data['percentage'])
                        remaining = max(0, estimated_total - elapsed)
                        progress_data['estimated_remaining_seconds'] = remaining
            
            return progress_data
            
        except Exception as e:
            logger.error(f"📊 PROGRESS: Error getting progress for {self.session_key}: {e}")
            return None
    
    def cancel_upload(self, reason: str = "User cancelled"):
        """Cancel upload operation"""
        self.complete_upload('cancelled', {'cancel_reason': reason})
    
    def cleanup_old_progress(self, max_age_hours: int = 24):
        """
        Clean up old progress tracking data
        This should be called periodically (e.g., via cron job)
        """
        # Note: This is a simplified cleanup - in production you'd want
        # a more sophisticated approach with proper cache key management
        logger.info(f"📊 PROGRESS: Cleanup not implemented for cache-based storage")
    
    @classmethod
    def get_user_uploads(cls, user_id: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent upload sessions for a user
        
        Note: This is limited with cache-based storage
        In production, consider using database storage for this feature
        """
        # This would require a more sophisticated storage mechanism
        # For now, return empty list
        logger.info(f"📊 PROGRESS: User upload history not available with cache storage")
        return []


class UploadProgressMixin:
    """
    Mixin for views that need upload progress tracking
    """
    
    def get_progress_tracker(self, request) -> UploadProgressTracker:
        """Get or create progress tracker for request"""
        session_key = request.session.get('upload_session_key')
        if not session_key:
            tracker = UploadProgressTracker()
            request.session['upload_session_key'] = tracker.session_key
        else:
            tracker = UploadProgressTracker(session_key)
        
        return tracker
    
    def track_file_processing(self, tracker: UploadProgressTracker, filename: str, stage: str):
        """Helper to track individual file processing"""
        tracker.update_progress(
            current_file=filename,
            stage=f"Processing {filename}: {stage}"
        )


# Simple progress tracking decorator
def track_upload_progress(total_files_key: str = 'total_files'):
    """
    Decorator to automatically track upload progress
    
    Args:
        total_files_key: Key in kwargs to get total files count
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract total files count
            total_files = kwargs.get(total_files_key, 0)
            
            # Create tracker
            tracker = UploadProgressTracker()
            session_key = tracker.start_upload(total_files)
            
            try:
                # Add tracker to kwargs
                kwargs['progress_tracker'] = tracker
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Mark as completed
                tracker.complete_upload('completed')
                
                return result
                
            except Exception as e:
                # Mark as failed
                tracker.complete_upload('failed', {'error': str(e)})
                raise
        
        return wrapper
    return decorator