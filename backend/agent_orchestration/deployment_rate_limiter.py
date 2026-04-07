"""
Workflow Deployment Rate Limiter
Per-domain rate limiting for workflow deployments
"""
import logging
from typing import Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from .models import WorkflowDeployment, WorkflowAllowedOrigin

logger = logging.getLogger('workflow_deployment')


class WorkflowDeploymentRateLimiter:
    """
    Rate limiter for workflow deployments
    Tracks requests per domain/origin with configurable limits
    """
    
    def __init__(self):
        """Initialize the rate limiter"""
        self.cache_prefix = 'workflow_deployment_rate_limit'
        logger.info("🚦 RATE LIMITER: Initialized")
    
    def check_rate_limit(
        self,
        deployment: WorkflowDeployment,
        origin: str
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is within rate limit for the given origin
        
        Args:
            deployment: WorkflowDeployment instance
            origin: Request origin (domain)
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
            - is_allowed: True if request is allowed, False if rate limited
            - retry_after_seconds: Seconds until next request allowed (None if allowed)
        """
        try:
            # Get rate limit for this origin
            rate_limit = self._get_rate_limit_for_origin(deployment, origin)
            
            if rate_limit is None:
                # No rate limit configured, allow request
                logger.debug(f"✅ RATE LIMIT: No limit configured for {origin}, allowing request")
                return True, None
            
            # Get cache key for this origin + deployment
            cache_key = self._get_cache_key(deployment.id, origin)
            
            # Get current request count for this minute
            current_minute = timezone.now().replace(second=0, microsecond=0)
            minute_key = f"{cache_key}:{current_minute.isoformat()}"
            
            # Get current count
            current_count = cache.get(minute_key, 0)
            
            if current_count >= rate_limit:
                # Rate limit exceeded
                # Calculate retry after (seconds until next minute)
                next_minute = current_minute + timedelta(minutes=1)
                retry_after = int((next_minute - timezone.now()).total_seconds())
                retry_after = max(1, retry_after)  # At least 1 second
                
                logger.warning(f"🚫 RATE LIMIT: Exceeded for {origin} (deployment {deployment.id}): {current_count}/{rate_limit}")
                return False, retry_after
            
            # Increment counter
            cache.set(minute_key, current_count + 1, timeout=120)  # 2 minute timeout (covers current + next minute)
            
            logger.debug(f"✅ RATE LIMIT: Allowed for {origin} (deployment {deployment.id}): {current_count + 1}/{rate_limit}")
            return True, None
            
        except Exception as e:
            logger.error(f"❌ RATE LIMIT: Error checking rate limit: {e}", exc_info=True)
            # On error, allow request (fail open)
            return True, None
    
    def _get_rate_limit_for_origin(
        self,
        deployment: WorkflowDeployment,
        origin: str
    ) -> Optional[int]:
        """
        Get rate limit for a specific origin
        
        Args:
            deployment: WorkflowDeployment instance
            origin: Request origin
            
        Returns:
            Rate limit per minute, or None if no limit
        """
        try:
            # Try to find origin-specific rate limit
            allowed_origin = WorkflowAllowedOrigin.objects.filter(
                deployment=deployment,
                origin=origin,
                is_active=True
            ).first()
            
            if allowed_origin:
                return allowed_origin.rate_limit_per_minute
            
            # Fallback to deployment default
            return deployment.rate_limit_per_minute
            
        except Exception as e:
            logger.error(f"❌ RATE LIMIT: Error getting rate limit for origin: {e}", exc_info=True)
            # Fallback to deployment default
            return deployment.rate_limit_per_minute
    
    def _get_cache_key(self, deployment_id: int, origin: str) -> str:
        """
        Generate cache key for rate limiting
        
        Args:
            deployment_id: Deployment ID
            origin: Request origin
            
        Returns:
            Cache key string
        """
        # Normalize origin for cache key (remove protocol, lowercase)
        normalized_origin = origin.lower().strip()
        if normalized_origin.startswith('http://'):
            normalized_origin = normalized_origin[7:]
        elif normalized_origin.startswith('https://'):
            normalized_origin = normalized_origin[8:]
        
        return f"{self.cache_prefix}:{deployment_id}:{normalized_origin}"
    
    def get_rate_limit_info(
        self,
        deployment: WorkflowDeployment,
        origin: str
    ) -> dict:
        """
        Get rate limit information for an origin
        
        Args:
            deployment: WorkflowDeployment instance
            origin: Request origin
            
        Returns:
            Dict with rate limit information
        """
        rate_limit = self._get_rate_limit_for_origin(deployment, origin)
        cache_key = self._get_cache_key(deployment.id, origin)
        current_minute = timezone.now().replace(second=0, microsecond=0)
        minute_key = f"{cache_key}:{current_minute.isoformat()}"
        current_count = cache.get(minute_key, 0)
        
        return {
            'rate_limit_per_minute': rate_limit,
            'current_count': current_count,
            'remaining': max(0, rate_limit - current_count) if rate_limit else None,
            'reset_at': (current_minute + timedelta(minutes=1)).isoformat()
        }

