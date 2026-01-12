"""Rate limiting implementation"""

import time
from typing import Dict, Tuple
from collections import deque
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate_per_minute: int):
        """Initialize rate limiter
        
        Args:
            rate_per_minute: Maximum requests per minute
        """
        self.rate_per_minute = rate_per_minute
        self.requests: deque = deque()

    def is_allowed(self, identifier: str = "default") -> Tuple[bool, float]:
        """Check if request is allowed
        
        Args:
            identifier: Unique identifier for rate limiting (e.g., user_id, IP)
            
        Returns:
            Tuple of (allowed, wait_time_seconds)
        """
        now = time.time()
        minute_ago = now - 60

        # Remove old requests
        while self.requests and self.requests[0] < minute_ago:
            self.requests.popleft()

        # Check if under limit
        if len(self.requests) < self.rate_per_minute:
            self.requests.append(now)
            return True, 0.0

        # Calculate wait time
        oldest_request = self.requests[0]
        wait_time = 60 - (now - oldest_request)
        return False, max(0, wait_time)


class RateLimiterManager:
    """Manage multiple rate limiters"""

    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {}

    def get_limiter(self, name: str, rate_per_minute: int) -> RateLimiter:
        """Get or create rate limiter
        
        Args:
            name: Limiter name
            rate_per_minute: Rate limit
            
        Returns:
            RateLimiter instance
        """
        if name not in self.limiters:
            self.limiters[name] = RateLimiter(rate_per_minute)
        return self.limiters[name]

    def check_limit(self, name: str, rate_per_minute: int, identifier: str = "default") -> Tuple[bool, float]:
        """Check rate limit
        
        Args:
            name: Limiter name
            rate_per_minute: Rate limit
            identifier: Request identifier
            
        Returns:
            Tuple of (allowed, wait_time)
        """
        limiter = self.get_limiter(name, rate_per_minute)
        return limiter.is_allowed(identifier)


# Global rate limiter manager
rate_limiter = RateLimiterManager()


