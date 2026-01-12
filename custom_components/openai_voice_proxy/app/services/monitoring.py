"""Prometheus monitoring and metrics"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from app.core.logging import get_logger
from app import __version__

logger = get_logger(__name__)


# Application info
app_info = Info("openai_proxy_ha", "OpenAI Proxy for Home Assistant")
app_info.info({"version": __version__})


# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)


# Command processing metrics
commands_processed_total = Counter(
    "commands_processed_total",
    "Total commands processed",
    ["intent", "status"],
)

command_processing_duration_seconds = Histogram(
    "command_processing_duration_seconds",
    "Command processing duration in seconds",
    ["intent"],
)


# Home Assistant integration metrics
ha_api_calls_total = Counter(
    "ha_api_calls_total",
    "Total Home Assistant API calls",
    ["domain", "service", "status"],
)

ha_api_call_duration_seconds = Histogram(
    "ha_api_call_duration_seconds",
    "Home Assistant API call duration in seconds",
    ["domain", "service"],
)


# OpenAI API metrics
openai_api_calls_total = Counter(
    "openai_api_calls_total",
    "Total OpenAI API calls",
    ["model", "api_type", "status"],
)

openai_api_call_duration_seconds = Histogram(
    "openai_api_call_duration_seconds",
    "OpenAI API call duration in seconds",
    ["model", "api_type"],
)

openai_tokens_used_total = Counter(
    "openai_tokens_used_total",
    "Total OpenAI tokens used",
    ["model", "token_type"],
)


# Perplexity API metrics
perplexity_searches_total = Counter(
    "perplexity_searches_total",
    "Total Perplexity searches",
    ["category", "status"],
)

perplexity_search_duration_seconds = Histogram(
    "perplexity_search_duration_seconds",
    "Perplexity search duration in seconds",
    ["category"],
)


# Habr search metrics
habr_searches_total = Counter(
    "habr_searches_total",
    "Total Habr searches",
    ["method", "status"],
)

habr_search_duration_seconds = Histogram(
    "habr_search_duration_seconds",
    "Habr search duration in seconds",
    ["method"],
)


# Memory metrics
memory_operations_total = Counter(
    "memory_operations_total",
    "Total memory operations",
    ["operation", "memory_type"],
)

memory_search_results = Histogram(
    "memory_search_results",
    "Number of results from memory search",
    ["memory_type"],
)


# Active connections
active_websocket_connections = Gauge(
    "active_websocket_connections",
    "Number of active WebSocket connections",
)


# System health
system_health = Gauge(
    "system_health",
    "System health status (1 = healthy, 0 = unhealthy)",
)

database_health = Gauge(
    "database_health",
    "Database health status (1 = healthy, 0 = unhealthy)",
)


# Telegram metrics
telegram_messages_sent_total = Counter(
    "telegram_messages_sent_total",
    "Total Telegram messages sent",
    ["message_type", "status"],
)


class MetricsCollector:
    """Collector for application metrics"""

    @staticmethod
    def record_http_request(method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def record_command(intent: str, status: str, duration: float):
        """Record command processing metrics"""
        commands_processed_total.labels(intent=intent, status=status).inc()
        command_processing_duration_seconds.labels(intent=intent).observe(duration)

    @staticmethod
    def record_ha_call(domain: str, service: str, status: str, duration: float):
        """Record Home Assistant API call metrics"""
        ha_api_calls_total.labels(domain=domain, service=service, status=status).inc()
        ha_api_call_duration_seconds.labels(domain=domain, service=service).observe(duration)

    @staticmethod
    def record_openai_call(
        model: str,
        api_type: str,  # chat, tts, embedding, realtime
        status: str,
        duration: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ):
        """Record OpenAI API call metrics"""
        openai_api_calls_total.labels(model=model, api_type=api_type, status=status).inc()
        openai_api_call_duration_seconds.labels(model=model, api_type=api_type).observe(duration)
        
        if prompt_tokens:
            openai_tokens_used_total.labels(model=model, token_type="prompt").inc(prompt_tokens)
        if completion_tokens:
            openai_tokens_used_total.labels(model=model, token_type="completion").inc(completion_tokens)

    @staticmethod
    def record_perplexity_search(category: str, status: str, duration: float):
        """Record Perplexity search metrics"""
        perplexity_searches_total.labels(category=category, status=status).inc()
        perplexity_search_duration_seconds.labels(category=category).observe(duration)

    @staticmethod
    def record_habr_search(method: str, status: str, duration: float):
        """Record Habr search metrics"""
        habr_searches_total.labels(method=method, status=status).inc()
        habr_search_duration_seconds.labels(method=method).observe(duration)

    @staticmethod
    def record_memory_operation(operation: str, memory_type: str, results_count: int = 0):
        """Record memory operation metrics"""
        memory_operations_total.labels(operation=operation, memory_type=memory_type).inc()
        if results_count > 0:
            memory_search_results.labels(memory_type=memory_type).observe(results_count)

    @staticmethod
    def record_telegram_message(message_type: str, status: str):
        """Record Telegram message metrics"""
        telegram_messages_sent_total.labels(message_type=message_type, status=status).inc()

    @staticmethod
    def set_websocket_connections(count: int):
        """Set active WebSocket connections count"""
        active_websocket_connections.set(count)

    @staticmethod
    def set_system_health(healthy: bool):
        """Set system health status"""
        system_health.set(1 if healthy else 0)

    @staticmethod
    def set_database_health(healthy: bool):
        """Set database health status"""
        database_health.set(1 if healthy else 0)


def get_metrics() -> bytes:
    """Get Prometheus metrics
    
    Returns:
        Metrics in Prometheus format
    """
    return generate_latest()


def get_content_type() -> str:
    """Get metrics content type
    
    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST


# Global metrics collector
metrics = MetricsCollector()


