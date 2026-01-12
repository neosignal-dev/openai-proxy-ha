"""Perplexity API integration for web search"""

from typing import Optional, List, Dict, Any
from enum import Enum
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limiter import rate_limiter

logger = get_logger(__name__)


class RecencyFilter(str, Enum):
    """Recency filter options for Perplexity search"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class SearchCategory(str, Enum):
    """Search category types"""
    NEWS = "news"
    TECH = "tech"
    HOWTO = "howto"
    HARDWARE = "hardware"
    TRANSPORT = "transport"
    HISTORICAL = "historical"
    GENERAL = "general"


# Recency policies by category
RECENCY_POLICY = {
    SearchCategory.NEWS: {"days": 7, "filter": RecencyFilter.WEEK},
    SearchCategory.TECH: {"days": 7, "filter": RecencyFilter.WEEK},
    SearchCategory.HOWTO: {"days": 90, "filter": RecencyFilter.MONTH},
    SearchCategory.HARDWARE: {"days": 60, "filter": RecencyFilter.MONTH},
    SearchCategory.TRANSPORT: {"days": 1, "filter": RecencyFilter.DAY},
    SearchCategory.HISTORICAL: {"days": None, "filter": None},  # No recency
    SearchCategory.GENERAL: {"days": 7, "filter": RecencyFilter.WEEK},
}


# Domain filters by category
DOMAIN_FILTERS = {
    SearchCategory.NEWS: {
        "include": ["news", "habr.com", "medium.com"],
        "exclude": [],
    },
    SearchCategory.TECH: {
        "include": ["habr.com", "github.com", "docs.*", "stackoverflow.com"],
        "exclude": [],
    },
    SearchCategory.HOWTO: {
        "include": ["*.com", "*.ru"],
        "exclude": ["social.*"],
    },
    SearchCategory.HARDWARE: {
        "include": ["habr.com", "github.com", "*.docs.*", "espressif.com"],
        "exclude": [],
    },
    SearchCategory.TRANSPORT: {
        "include": ["rzd.ru", "tutu.ru", "yandex.ru"],
        "exclude": [],
    },
}


class PerplexityClient:
    """Client for Perplexity Search API"""

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

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    def _determine_category(self, query: str) -> SearchCategory:
        """Determine search category from query
        
        Args:
            query: Search query
            
        Returns:
            Search category
        """
        query_lower = query.lower()

        # Keywords for each category
        if any(kw in query_lower for kw in ["новости", "сегодня", "вчера", "news", "latest"]):
            return SearchCategory.NEWS
        elif any(kw in query_lower for kw in ["esp32", "arduino", "raspberry pi", "железо"]):
            return SearchCategory.HARDWARE
        elif any(kw in query_lower for kw in ["как сделать", "how to", "инструкция", "tutorial"]):
            return SearchCategory.HOWTO
        elif any(kw in query_lower for kw in ["поезд", "электричка", "расписание", "транспорт"]):
            return SearchCategory.TRANSPORT
        elif any(kw in query_lower for kw in ["история", "historical", "когда был", "в каком году"]):
            return SearchCategory.HISTORICAL
        elif any(kw in query_lower for kw in ["технология", "программирование", "ai", "ml", "tech"]):
            return SearchCategory.TECH

        return SearchCategory.GENERAL

    def _get_recency_config(
        self,
        category: SearchCategory,
        override_days: Optional[int] = None
    ) -> Optional[str]:
        """Get recency configuration for category
        
        Args:
            category: Search category
            override_days: Optional override for recency days
            
        Returns:
            Recency filter or None
        """
        policy = RECENCY_POLICY.get(category, RECENCY_POLICY[SearchCategory.GENERAL])
        
        if override_days is not None:
            if override_days <= 1:
                return RecencyFilter.DAY
            elif override_days <= 7:
                return RecencyFilter.WEEK
            elif override_days <= 30:
                return RecencyFilter.MONTH
            elif override_days <= 365:
                return RecencyFilter.YEAR
            else:
                return None

        return policy.get("filter")

    def _get_domain_filters(self, category: SearchCategory) -> Dict[str, List[str]]:
        """Get domain filters for category
        
        Args:
            category: Search category
            
        Returns:
            Dictionary with include/exclude domains
        """
        return DOMAIN_FILTERS.get(category, {"include": [], "exclude": []})

    async def search(
        self,
        query: str,
        recency_days: Optional[int] = None,
        category: Optional[SearchCategory] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Perform web search via Perplexity API
        
        Args:
            query: Search query
            recency_days: Optional recency filter in days
            category: Optional search category
            include_domains: Optional domains to include
            exclude_domains: Optional domains to exclude
            max_results: Maximum number of results
            
        Returns:
            Search results with sources
        """
        # Check rate limit
        allowed, wait_time = rate_limiter.check_limit(
            "perplexity",
            settings.perplexity_rate_limit_per_minute,
            "default"
        )
        
        if not allowed:
            logger.warning("Perplexity rate limit exceeded", wait_time=wait_time)
            raise Exception(f"Rate limit exceeded. Wait {wait_time:.1f} seconds.")

        # Determine category if not provided
        if category is None:
            category = self._determine_category(query)

        logger.info(
            "Performing Perplexity search",
            query=query,
            category=category.value,
            recency_days=recency_days,
        )

        # Get recency filter
        recency_filter = self._get_recency_config(category, recency_days)

        # Get domain filters
        domain_config = self._get_domain_filters(category)
        final_include = include_domains or domain_config.get("include", [])
        final_exclude = exclude_domains or domain_config.get("exclude", [])

        # Build search parameters
        search_params: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — помощник по поиску информации. "
                        "Отвечай кратко, по делу, на русском языке. "
                        "Всегда указывай источники."
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.2,
            "top_p": 0.9,
            "return_citations": True,
            "return_images": False,
            "search_recency_filter": recency_filter if recency_filter else None,
        }

        # Add domain filters if specified
        if final_include:
            search_params["search_domain_filter"] = final_include

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=search_params,
            )
            response.raise_for_status()
            result = response.json()

            # Extract answer and citations
            choices = result.get("choices", [])
            if not choices:
                logger.warning("No results from Perplexity", query=query)
                return {
                    "answer": "Информация не найдена.",
                    "sources": [],
                    "category": category.value,
                    "recency": recency_filter,
                }

            answer = choices[0].get("message", {}).get("content", "")
            citations = result.get("citations", [])

            logger.info(
                "Perplexity search completed",
                query=query,
                answer_length=len(answer),
                citations_count=len(citations),
            )

            return {
                "answer": answer,
                "sources": citations[:max_results],
                "category": category.value,
                "recency": recency_filter,
                "query": query,
            }

        except httpx.HTTPStatusError as e:
            logger.error(
                "Perplexity API error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise

        except Exception as e:
            logger.error("Perplexity search failed", error=str(e))
            raise

    async def explain_search_config(
        self,
        query: str,
        category: Optional[SearchCategory] = None
    ) -> Dict[str, Any]:
        """Explain search configuration that would be used
        
        Args:
            query: Search query
            category: Optional category override
            
        Returns:
            Configuration explanation
        """
        if category is None:
            category = self._determine_category(query)

        recency_filter = self._get_recency_config(category)
        domain_config = self._get_domain_filters(category)

        explanation = {
            "query": query,
            "category": category.value,
            "recency_filter": recency_filter,
            "recency_reason": self._explain_recency(category),
            "domain_filters": domain_config,
        }

        return explanation

    def _explain_recency(self, category: SearchCategory) -> str:
        """Explain why specific recency is used
        
        Args:
            category: Search category
            
        Returns:
            Explanation text
        """
        explanations = {
            SearchCategory.NEWS: "Новости требуют актуальной информации (до 7 дней)",
            SearchCategory.TECH: "Технологии быстро меняются (до 7 дней)",
            SearchCategory.HOWTO: "Инструкции остаются актуальными дольше (до 3 месяцев)",
            SearchCategory.HARDWARE: "Документация по железу обновляется реже (до 2 месяцев)",
            SearchCategory.TRANSPORT: "Расписания требуют свежей информации (до 1 дня)",
            SearchCategory.HISTORICAL: "Исторические факты не требуют актуальности",
            SearchCategory.GENERAL: "Общий поиск с умеренной актуальностью (до 7 дней)",
        }
        
        return explanations.get(category, "Стандартная актуальность")


# Global client instance
perplexity_client = PerplexityClient()


