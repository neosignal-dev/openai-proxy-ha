"""Enhanced Perplexity client with enforced recency policies"""

from typing import Dict, Any, Optional, List
import httpx
import time
from app.services.search.policies import (
    recency_policy,
    pre_classifier,
    SearchCategory,
    RecencyRequirement,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limiter import rate_limiter

logger = get_logger(__name__)


class RecencyFilter(str):
    """Recency filter values for Perplexity API"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class EnhancedPerplexityClient:
    """
    Enhanced Perplexity client with enforced recency policies.
    
    Features:
    - Pre-classification for fast categorization
    - Enforced recency policies (LLM cannot override)
    - Automatic policy application
    - Policy violation detection and correction
    - Detailed logging and auditing
    """

    def __init__(self):
        self.api_key = settings.perplexity_api_key
        self.model = settings.perplexity_model
        self.base_url = "https://api.perplexity.ai"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self.cache: Dict[str, Dict[str, Any]] = {}

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def search(
        self,
        query: str,
        category: Optional[SearchCategory] = None,
        requested_recency_days: Optional[int] = None,
        override_reason: Optional[str] = None,
        use_cache: bool = True,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """
        Perform search with enforced recency policy
        
        Args:
            query: Search query
            category: Optional explicit category
            requested_recency_days: Requested recency (may be overridden)
            override_reason: Reason for policy override
            use_cache: Use cached results if available
            max_results: Maximum results
            
        Returns:
            Search results with policy metadata
        """
        start_time = time.time()

        # Check rate limit
        allowed, wait_time = rate_limiter.check_limit(
            "perplexity",
            settings.perplexity_rate_limit_per_minute,
            "default"
        )
        
        if not allowed:
            logger.warning("Rate limit exceeded", wait_time=wait_time)
            raise Exception(f"Rate limit exceeded. Wait {wait_time:.1f} seconds.")

        # Step 1: Pre-classify if not provided
        if category is None:
            category = pre_classifier.classify(query)

        logger.info(
            "Search initiated",
            query=query[:100],
            category=category.value,
            requested_days=requested_recency_days,
        )

        # Step 2: Enforce recency policy
        policy_decision = recency_policy.enforce_recency(
            category=category,
            requested_days=requested_recency_days,
        )

        # Step 3: Validate override if provided
        if override_reason and requested_recency_days:
            if recency_policy.validate_override(
                category=category,
                override_days=requested_recency_days,
                reason=override_reason,
            ):
                policy_decision["recency_days"] = requested_recency_days
                policy_decision["override_applied"] = True
                policy_decision["override_reason"] = override_reason

        # Step 4: Convert days to filter
        recency_filter = self._days_to_filter(policy_decision["recency_days"])

        # Step 5: Check cache
        cache_key = f"{query}:{category.value}:{recency_filter}"
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached["timestamp"] < settings.perplexity_cache_ttl_minutes * 60:
                logger.info("Using cached result", query=query[:50])
                cached["from_cache"] = True
                return cached

        # Step 6: Perform search
        try:
            search_result = await self._perform_search(
                query=query,
                recency_filter=recency_filter,
                max_results=max_results,
            )

            # Add policy metadata
            search_result.update({
                "policy": policy_decision,
                "category": category.value,
                "query": query,
                "from_cache": False,
                "timestamp": time.time(),
            })

            # Cache result
            if use_cache:
                self.cache[cache_key] = search_result

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Search completed",
                query=query[:50],
                category=category.value,
                recency_days=policy_decision["recency_days"],
                sources_count=len(search_result.get("sources", [])),
                duration_ms=duration_ms,
            )

            return search_result

        except Exception as e:
            logger.error("Search failed", query=query[:50], error=str(e))
            raise

    async def _perform_search(
        self,
        query: str,
        recency_filter: Optional[str],
        max_results: int,
    ) -> Dict[str, Any]:
        """Perform actual Perplexity API call"""
        
        # Build request
        search_params = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — помощник по поиску информации. "
                        "Отвечай кратко, по делу, на русском языке. "
                        "Всегда указывай источники."
                    ),
                },
                {
                    "role": "user",
                    "content": query,
                },
            ],
            "max_tokens": 1000,
            "temperature": 0.2,
            "top_p": 0.9,
            "return_citations": True,
            "return_images": False,
        }

        # Add recency filter if present
        if recency_filter:
            search_params["search_recency_filter"] = recency_filter

        # Perform request
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=search_params,
        )
        response.raise_for_status()
        result = response.json()

        # Extract answer and citations
        choices = result.get("choices", [])
        if not choices:
            return {
                "answer": "Информация не найдена.",
                "sources": [],
            }

        answer = choices[0].get("message", {}).get("content", "")
        citations = result.get("citations", [])

        return {
            "answer": answer,
            "sources": citations[:max_results],
            "usage": result.get("usage", {}),
        }

    @staticmethod
    def _days_to_filter(days: Optional[int]) -> Optional[str]:
        """Convert days to Perplexity recency filter"""
        if days is None:
            return None

        if days <= 1:
            return RecencyFilter.DAY
        elif days <= 7:
            return RecencyFilter.WEEK
        elif days <= 30:
            return RecencyFilter.MONTH
        elif days <= 365:
            return RecencyFilter.YEAR
        else:
            return None

    async def explain_policy(
        self,
        query: str,
        category: Optional[SearchCategory] = None,
    ) -> Dict[str, Any]:
        """
        Explain which policy will be applied
        
        Args:
            query: Search query
            category: Optional category
            
        Returns:
            Policy explanation
        """
        if category is None:
            category = pre_classifier.classify(query)

        policy = recency_policy.get_policy(category)
        policy_decision = recency_policy.enforce_recency(category)

        return {
            "query": query,
            "category": category.value,
            "requirement": policy["requirement"],
            "max_days": policy["max_days"],
            "preferred_days": policy["preferred_days"],
            "reason": policy["reason"],
            "will_use_recency": policy_decision["recency_days"],
            "can_override": policy["requirement"] in [
                RecencyRequirement.RECOMMENDED,
                RecencyRequirement.OPTIONAL,
            ],
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = time.time()
        ttl_seconds = settings.perplexity_cache_ttl_minutes * 60

        valid_entries = 0
        expired_entries = 0

        for cached in self.cache.values():
            if current_time - cached["timestamp"] < ttl_seconds:
                valid_entries += 1
            else:
                expired_entries += 1

        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "ttl_minutes": settings.perplexity_cache_ttl_minutes,
        }

    def clear_cache(self, expired_only: bool = False):
        """Clear search cache"""
        if not expired_only:
            self.cache.clear()
            logger.info("Cache cleared completely")
            return

        # Clear only expired entries
        current_time = time.time()
        ttl_seconds = settings.perplexity_cache_ttl_minutes * 60

        expired_keys = [
            key for key, cached in self.cache.items()
            if current_time - cached["timestamp"] >= ttl_seconds
        ]

        for key in expired_keys:
            del self.cache[key]

        logger.info("Expired cache entries cleared", count=len(expired_keys))

    async def health_check(self) -> Dict[str, Any]:
        """Check client health"""
        try:
            # Simple test query
            result = await self.search(
                query="test",
                use_cache=False,
                max_results=1,
            )
            return {
                "healthy": True,
                "model": self.model,
                "cache_entries": len(self.cache),
            }
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {
                "healthy": False,
                "error": str(e),
            }


# Global instance
enhanced_perplexity_client = EnhancedPerplexityClient()
