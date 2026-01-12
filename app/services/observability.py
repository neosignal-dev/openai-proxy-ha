"""Enhanced observability - metrics, audit logging, tracing"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from app.core.database import ActionLog, async_session_maker
from app.core.logging import get_logger

logger = get_logger(__name__)


class EnhancedMetrics:
    """
    Enhanced Prometheus metrics for voice-first assistant.
    
    Metrics categories:
    - HTTP requests
    - Pipeline processing
    - Agent operations
    - Memory operations
    - Search operations
    - TTS operations
    - Realtime WebSocket
    - System health
    """

    def __init__(self):
        # HTTP metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"],
        )

        # Pipeline metrics
        self.pipeline_requests_total = Counter(
            "pipeline_requests_total",
            "Total pipeline requests",
            ["intent", "status"],
        )
        self.pipeline_duration = Histogram(
            "pipeline_duration_seconds",
            "Pipeline processing duration",
            ["intent"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
        )
        self.pipeline_steps_duration = Histogram(
            "pipeline_step_duration_seconds",
            "Individual pipeline step duration",
            ["step"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
        )

        # Agent metrics
        self.agent_requests_total = Counter(
            "agent_requests_total",
            "Total agent requests",
            ["agent_type", "status"],
        )
        self.agent_tokens_used = Counter(
            "agent_tokens_used_total",
            "Total tokens used by agents",
            ["agent_type", "model"],
        )
        self.agent_latency = Histogram(
            "agent_latency_seconds",
            "Agent processing latency",
            ["agent_type"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
        )

        # Memory metrics
        self.memory_operations_total = Counter(
            "memory_operations_total",
            "Total memory operations",
            ["operation", "storage"],  # operation: add/search/delete, storage: short/long
        )
        self.memory_search_duration = Histogram(
            "memory_search_duration_seconds",
            "Memory search duration",
            ["storage"],
        )
        self.memory_size_gauge = Gauge(
            "memory_entries_total",
            "Current memory entries",
            ["user_id", "storage"],
        )

        # Search metrics
        self.search_requests_total = Counter(
            "search_requests_total",
            "Total search requests",
            ["provider", "category", "status"],
        )
        self.search_duration = Histogram(
            "search_duration_seconds",
            "Search duration",
            ["provider", "category"],
            buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
        )
        self.search_policy_enforced = Counter(
            "search_policy_enforced_total",
            "Times search policy was enforced",
            ["category", "reason"],
        )

        # TTS metrics
        self.tts_requests_total = Counter(
            "tts_requests_total",
            "Total TTS requests",
            ["voice", "format", "status"],
        )
        self.tts_duration = Histogram(
            "tts_duration_seconds",
            "TTS synthesis duration",
            ["voice"],
        )
        self.tts_characters_total = Counter(
            "tts_characters_total",
            "Total characters synthesized",
            ["voice"],
        )

        # Realtime WebSocket metrics
        self.websocket_connections_active = Gauge(
            "websocket_connections_active",
            "Active WebSocket connections",
        )
        self.websocket_messages_total = Counter(
            "websocket_messages_total",
            "Total WebSocket messages",
            ["direction", "type"],  # direction: inbound/outbound
        )
        self.websocket_audio_duration = Histogram(
            "websocket_audio_duration_seconds",
            "WebSocket audio chunk duration",
        )

        # Home Assistant metrics
        self.ha_service_calls_total = Counter(
            "ha_service_calls_total",
            "Total HA service calls",
            ["domain", "service", "status"],
        )
        self.ha_service_duration = Histogram(
            "ha_service_duration_seconds",
            "HA service call duration",
            ["domain", "service"],
        )

        # System health
        self.system_health = Gauge(
            "system_health",
            "System health status (1=healthy, 0=unhealthy)",
        )
        self.component_health = Gauge(
            "component_health",
            "Component health status",
            ["component"],
        )

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
    ):
        """Record HTTP request metrics"""
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status,
        ).inc()
        
        self.http_request_duration.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

    def record_pipeline(
        self,
        intent: str,
        status: str,
        duration: float,
        step_durations: Optional[Dict[str, float]] = None,
    ):
        """Record pipeline metrics"""
        self.pipeline_requests_total.labels(
            intent=intent,
            status=status,
        ).inc()
        
        self.pipeline_duration.labels(
            intent=intent,
        ).observe(duration)

        if step_durations:
            for step, step_duration in step_durations.items():
                self.pipeline_steps_duration.labels(
                    step=step,
                ).observe(step_duration)

    def record_agent(
        self,
        agent_type: str,
        status: str,
        latency: float,
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
    ):
        """Record agent metrics"""
        self.agent_requests_total.labels(
            agent_type=agent_type,
            status=status,
        ).inc()
        
        self.agent_latency.labels(
            agent_type=agent_type,
        ).observe(latency)

        if tokens_used and model:
            self.agent_tokens_used.labels(
                agent_type=agent_type,
                model=model,
            ).inc(tokens_used)

    def record_memory_operation(
        self,
        operation: str,
        storage: str,
        duration: Optional[float] = None,
    ):
        """Record memory operation metrics"""
        self.memory_operations_total.labels(
            operation=operation,
            storage=storage,
        ).inc()

        if duration:
            self.memory_search_duration.labels(
                storage=storage,
            ).observe(duration)

    def record_search(
        self,
        provider: str,
        category: str,
        status: str,
        duration: float,
        policy_enforced: bool = False,
        enforcement_reason: Optional[str] = None,
    ):
        """Record search metrics"""
        self.search_requests_total.labels(
            provider=provider,
            category=category,
            status=status,
        ).inc()
        
        self.search_duration.labels(
            provider=provider,
            category=category,
        ).observe(duration)

        if policy_enforced and enforcement_reason:
            self.search_policy_enforced.labels(
                category=category,
                reason=enforcement_reason,
            ).inc()

    def record_tts(
        self,
        voice: str,
        format: str,
        status: str,
        duration: float,
        characters: int,
    ):
        """Record TTS metrics"""
        self.tts_requests_total.labels(
            voice=voice,
            format=format,
            status=status,
        ).inc()
        
        self.tts_duration.labels(
            voice=voice,
        ).observe(duration)
        
        self.tts_characters_total.labels(
            voice=voice,
        ).inc(characters)

    def record_websocket_message(
        self,
        direction: str,
        message_type: str,
    ):
        """Record WebSocket message"""
        self.websocket_messages_total.labels(
            direction=direction,
            type=message_type,
        ).inc()

    def set_websocket_connections(self, count: int):
        """Set active WebSocket connections"""
        self.websocket_connections_active.set(count)

    def record_ha_service_call(
        self,
        domain: str,
        service: str,
        status: str,
        duration: float,
    ):
        """Record HA service call metrics"""
        self.ha_service_calls_total.labels(
            domain=domain,
            service=service,
            status=status,
        ).inc()
        
        self.ha_service_duration.labels(
            domain=domain,
            service=service,
        ).observe(duration)

    def set_component_health(self, component: str, healthy: bool):
        """Set component health"""
        self.component_health.labels(
            component=component,
        ).set(1 if healthy else 0)

    def set_system_health(self, healthy: bool):
        """Set overall system health"""
        self.system_health.set(1 if healthy else 0)


class AuditLogger:
    """
    Structured audit logging for security and compliance.
    
    Logs:
    - All user commands and actions
    - Policy enforcements
    - Permission checks
    - Failures and errors
    """

    @staticmethod
    async def log_command(
        user_id: str,
        command: str,
        intent: str,
        actions: list,
        confirmed: bool,
        executed: bool,
        success: bool,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log command execution to audit database"""
        try:
            async with async_session_maker() as session:
                log_entry = ActionLog(
                    user_id=user_id,
                    intent=intent,
                    actions=actions,
                    confirmed=confirmed,
                    executed=executed,
                    success=success,
                    error=error,
                )
                session.add(log_entry)
                await session.commit()

            logger.info(
                "Audit: command executed",
                user_id=user_id,
                intent=intent,
                confirmed=confirmed,
                success=success,
                **( metadata or {}),
            )

        except Exception as e:
            logger.error("Failed to log audit entry", error=str(e))

    @staticmethod
    def log_policy_enforcement(
        event_type: str,
        user_id: str,
        action: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log policy enforcement"""
        logger.warning(
            f"Audit: policy enforced - {event_type}",
            user_id=user_id,
            action=action,
            reason=reason,
            details=details or {},
        )

    @staticmethod
    def log_security_event(
        event_type: str,
        user_id: str,
        severity: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log security event"""
        logger.warning(
            f"Audit: security event - {event_type}",
            user_id=user_id,
            severity=severity,
            description=description,
            details=details or {},
        )


# Global instances
enhanced_metrics = EnhancedMetrics()
audit_logger = AuditLogger()


def get_metrics() -> bytes:
    """Get Prometheus metrics"""
    return generate_latest()


def get_content_type() -> str:
    """Get Prometheus content type"""
    return CONTENT_TYPE_LATEST
