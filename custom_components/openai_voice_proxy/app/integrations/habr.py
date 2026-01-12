"""Habr.com integration - RSS and HTML parsing"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from urllib.parse import urlencode
import feedparser
import httpx
from bs4 import BeautifulSoup
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limiter import rate_limiter

logger = get_logger(__name__)


class HabrClient:
    """Client for Habr.com search via RSS and HTML"""

    def __init__(self):
        self.base_url = "https://habr.com"
        self.rss_url = "https://habr.com/ru/rss"
        self.search_url = "https://habr.com/ru/search"
        self.user_agent = "Mozilla/5.0 (compatible; HomeAssistantBot/1.0; +https://example.com/bot)"
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    def _check_cache(self, cache_key: str) -> Optional[Any]:
        """Check if cache entry is valid
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached data or None
        """
        if cache_key not in self._cache:
            return None

        timestamp = self._cache_timestamps.get(cache_key)
        if not timestamp:
            return None

        ttl = timedelta(minutes=settings.habr_cache_ttl_minutes)
        if datetime.utcnow() - timestamp > ttl:
            # Cache expired
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None

        logger.debug("Cache hit", cache_key=cache_key)
        return self._cache[cache_key]

    def _set_cache(self, cache_key: str, data: Any):
        """Set cache entry
        
        Args:
            cache_key: Cache key
            data: Data to cache
        """
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = datetime.utcnow()

    async def search_rss(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        hubs: Optional[List[str]] = None,
        days: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search Habr via RSS feed (preferred method)
        
        Args:
            query: Search query
            tags: Filter by tags
            hubs: Filter by hubs
            days: Filter articles from last N days
            limit: Maximum number of results
            
        Returns:
            List of articles
        """
        # Check rate limit
        allowed, wait_time = rate_limiter.check_limit(
            "habr",
            settings.habr_rate_limit_per_minute,
            "default"
        )
        
        if not allowed:
            logger.warning("Habr rate limit exceeded", wait_time=wait_time)
            raise Exception(f"Rate limit exceeded. Wait {wait_time:.1f} seconds.")

        # Build cache key
        cache_key = f"rss_{query}_{tags}_{hubs}_{days}_{limit}"
        cached = self._check_cache(cache_key)
        if cached:
            return cached

        logger.info(
            "Searching Habr via RSS",
            query=query,
            tags=tags,
            hubs=hubs,
            days=days,
        )

        try:
            # Fetch RSS feed
            # Note: Habr RSS might not support direct filtering
            # We'll fetch and filter locally
            response = await self.client.get(
                f"{self.rss_url}/all/",
                headers={"User-Agent": self.user_agent}
            )
            response.raise_for_status()

            # Parse RSS
            feed = feedparser.parse(response.text)
            articles = []

            cutoff_date = None
            if days:
                cutoff_date = datetime.utcnow() - timedelta(days=days)

            for entry in feed.entries[:limit * 2]:  # Fetch extra for filtering
                # Parse published date
                published = None
                if hasattr(entry, "published_parsed"):
                    published = datetime(*entry.published_parsed[:6])

                # Filter by date
                if cutoff_date and published and published < cutoff_date:
                    continue

                # Extract tags/hubs from entry
                entry_tags = []
                if hasattr(entry, "tags"):
                    entry_tags = [tag.term.lower() for tag in entry.tags]

                # Filter by tags
                if tags:
                    tags_lower = [t.lower() for t in tags]
                    if not any(tag in entry_tags for tag in tags_lower):
                        continue

                # Filter by query (simple text search)
                if query:
                    query_lower = query.lower()
                    if query_lower not in entry.title.lower() and \
                       query_lower not in entry.get("summary", "").lower():
                        continue

                article = {
                    "title": entry.title,
                    "link": entry.link,
                    "published": published.isoformat() if published else None,
                    "summary": entry.get("summary", "")[:500],
                    "tags": entry_tags,
                    "author": entry.get("author", "Unknown"),
                }

                articles.append(article)

                if len(articles) >= limit:
                    break

            logger.info("Habr RSS search completed", results=len(articles))

            # Cache results
            self._set_cache(cache_key, articles)

            return articles

        except Exception as e:
            logger.error("Habr RSS search failed", error=str(e))
            raise

    async def search_html(
        self,
        query: str,
        days: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search Habr via HTML scraping (fallback method)
        
        Args:
            query: Search query
            days: Filter articles from last N days
            limit: Maximum number of results
            
        Returns:
            List of articles
        """
        # Check rate limit
        allowed, wait_time = rate_limiter.check_limit(
            "habr",
            settings.habr_rate_limit_per_minute,
            "default"
        )
        
        if not allowed:
            logger.warning("Habr rate limit exceeded", wait_time=wait_time)
            raise Exception(f"Rate limit exceeded. Wait {wait_time:.1f} seconds.")

        # Build cache key
        cache_key = f"html_{query}_{days}_{limit}"
        cached = self._check_cache(cache_key)
        if cached:
            return cached

        logger.info("Searching Habr via HTML", query=query, days=days)

        try:
            # Build search URL
            params = {"q": query, "target_type": "posts"}
            url = f"{self.search_url}/?{urlencode(params)}"

            response = await self.client.get(url)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")
            articles = []

            # Find article elements
            # Note: Habr's HTML structure may change, this is a best-effort approach
            article_elements = soup.find_all("article", class_="tm-articles-list__item")

            for element in article_elements[:limit]:
                try:
                    # Extract title and link
                    title_elem = element.find("a", class_="tm-article-snippet__title-link")
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = self.base_url + title_elem.get("href", "")

                    # Extract date
                    date_elem = element.find("time")
                    published = None
                    if date_elem and date_elem.get("datetime"):
                        published_str = date_elem.get("datetime")
                        try:
                            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                        except:
                            pass

                    # Filter by date
                    if days and published:
                        cutoff = datetime.utcnow() - timedelta(days=days)
                        if published < cutoff:
                            continue

                    # Extract summary
                    summary_elem = element.find("div", class_="tm-article-snippet__lead")
                    summary = summary_elem.get_text(strip=True)[:500] if summary_elem else ""

                    # Extract tags
                    tags = []
                    tag_elements = element.find_all("a", class_="tm-tags-list__link")
                    for tag_elem in tag_elements:
                        tags.append(tag_elem.get_text(strip=True).lower())

                    article = {
                        "title": title,
                        "link": link,
                        "published": published.isoformat() if published else None,
                        "summary": summary,
                        "tags": tags,
                        "author": "Unknown",
                    }

                    articles.append(article)

                except Exception as e:
                    logger.warning("Failed to parse article", error=str(e))
                    continue

            logger.info("Habr HTML search completed", results=len(articles))

            # Cache results
            self._set_cache(cache_key, articles)

            return articles

        except Exception as e:
            logger.error("Habr HTML search failed", error=str(e))
            raise

    async def search(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        hubs: Optional[List[str]] = None,
        days: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Universal search method (tries RSS first, falls back to HTML)
        
        Args:
            query: Search query
            tags: Filter by tags
            hubs: Filter by hubs
            days: Filter articles from last N days
            limit: Maximum number of results
            
        Returns:
            List of articles
        """
        try:
            # Try RSS first
            return await self.search_rss(
                query=query,
                tags=tags,
                hubs=hubs,
                days=days,
                limit=limit,
            )
        except Exception as e:
            logger.warning("RSS search failed, trying HTML", error=str(e))
            
            # Fallback to HTML if query is provided
            if query:
                return await self.search_html(
                    query=query,
                    days=days,
                    limit=limit,
                )
            else:
                raise ValueError("Query required for HTML search")

    def format_for_voice(self, articles: List[Dict[str, Any]], max_articles: int = 3) -> str:
        """Format articles for voice response
        
        Args:
            articles: List of articles
            max_articles: Maximum articles to include
            
        Returns:
            Formatted text for TTS
        """
        if not articles:
            return "К сожалению, статьи по вашему запросу не найдены."

        lines = [f"Найдено статей: {len(articles)}. Вот топ {min(max_articles, len(articles))}:"]

        for i, article in enumerate(articles[:max_articles], 1):
            title = article.get("title", "Без названия")
            date = article.get("published", "")
            if date:
                try:
                    dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                    date_str = dt.strftime("%d %B")
                except:
                    date_str = ""
            else:
                date_str = ""

            line = f"{i}. {title}"
            if date_str:
                line += f" от {date_str}"
            
            lines.append(line)

        return "\n".join(lines)

    def format_for_telegram(self, articles: List[Dict[str, Any]], max_articles: int = 10) -> str:
        """Format articles for Telegram message
        
        Args:
            articles: List of articles
            max_articles: Maximum articles to include
            
        Returns:
            Formatted Markdown text
        """
        if not articles:
            return "Статьи не найдены."

        lines = [f"📚 *Найдено статей на Habr: {len(articles)}*\n"]

        for i, article in enumerate(articles[:max_articles], 1):
            title = article.get("title", "Без названия")
            link = article.get("link", "")
            date = article.get("published", "")
            tags = article.get("tags", [])

            date_str = ""
            if date:
                try:
                    dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                    date_str = dt.strftime("%d.%m.%Y")
                except:
                    pass

            line = f"{i}. [{title}]({link})"
            if date_str:
                line += f" _{date_str}_"
            if tags:
                line += f"\n   🏷 {', '.join(tags[:3])}"

            lines.append(line)

        return "\n\n".join(lines)


# Global client instance
habr_client = HabrClient()


