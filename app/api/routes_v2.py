"""Updated API routes with new architecture"""

import time
import json
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from app.api.schemas import (
    CommandRequest, CommandResponse,
    ConfirmRequest, ConfirmResponse,
    SearchRequest, SearchResponse,
    HabrSearchRequest, HabrSearchResponse,
    TelegramSendRequest,
    AutomationDraftRequest, AutomationDraftResponse,
    ContextResponse, HealthResponse,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import engine
from app.integrations.homeassistant import ha_client
from app.integrations.habr import habr_client
from app.integrations.telegram_bot import telegram_client
from app.services.pipeline.orchestrator import pipeline
from app.services.memory_v2.manager import memory_manager
from app.services.tts.openai_tts import openai_tts
from app.services.search.perplexity_enhanced import enhanced_perplexity_client
from app.agents.realtime_voice_agent import RealtimeVoiceAgent
from app.services.monitoring import metrics, get_metrics, get_content_type
from app.core.rate_limiter import rate_limiter
from app import __version__

logger = get_logger(__name__)
router = APIRouter()


class WebSocketRateLimiter:
    """Simple rate limiter for WebSocket messages"""
    
    def __init__(self, max_messages_per_minute: int = 60):
        self.max_messages = max_messages_per_minute
        self.user_messages: Dict[str, list] = {}
    
    def check_limit(self, user_id: str) -> tuple[bool, float]:
        """Check if user is within rate limit"""
        import time
        current_time = time.time()
        
        # Clean old messages
        if user_id in self.user_messages:
            self.user_messages[user_id] = [
                t for t in self.user_messages[user_id]
                if current_time - t < 60
            ]
        else:
            self.user_messages[user_id] = []
        
        # Check limit
        if len(self.user_messages[user_id]) >= self.max_messages:
            wait_time = 60 - (current_time - self.user_messages[user_id][0])
            return False, wait_time
        
        # Add current message
        self.user_messages[user_id].append(current_time)
        return True, 0.0


ws_rate_limiter = WebSocketRateLimiter(max_messages_per_minute=120)


@router.post("/v1/command", response_model=CommandResponse)
async def execute_command(request: CommandRequest):
    """Execute user command through new pipeline"""
    start_time = time.time()
    
    try:
        # Process through pipeline
        response = await pipeline.process(
            user_id=request.user_id,
            command=request.command,
            channel="voice" if request.include_audio else "text",
            include_audio=request.include_audio,
        )

        # Record metrics
        duration = time.time() - start_time
        intent = response.get("intent", "unknown")
        metrics.record_command(intent, "success", duration)

        # Format response
        return CommandResponse(
            type=response.get("type", "text_response"),
            response=response.get("text", ""),
            intent=response.get("intent"),
            actions=response.get("actions"),
            needs_confirmation=response.get("needs_confirmation", False),
            metadata=response.get("pipeline"),
        )

    except Exception as e:
        duration = time.time() - start_time
        metrics.record_command("unknown", "error", duration)
        logger.error("Command execution failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/confirm", response_model=ConfirmResponse)
async def confirm_action(request: ConfirmRequest):
    """Confirm and execute action"""
    start_time = time.time()

    try:
        response = await pipeline.process_confirmation(
            user_id=request.user_id,
            plan=request.plan,
            confirmed=request.confirmed,
        )

        duration = time.time() - start_time
        intent = request.plan.get("intent", "unknown")
        status = "success" if response.get("execution", {}).get("success", True) else "error"
        metrics.record_command(f"{intent}_confirm", status, duration)

        return ConfirmResponse(
            success=response.get("execution", {}).get("success", True),
            message=response.get("text", ""),
            results=response.get("execution", {}).get("results"),
        )

    except Exception as e:
        duration = time.time() - start_time
        metrics.record_command("confirm", "error", duration)
        logger.error("Action confirmation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/context", response_model=ContextResponse)
async def get_context():
    """Get Home Assistant context"""
    try:
        context = await ha_client.get_context()
        
        return ContextResponse(
            config=context["config"],
            total_entities=context["total_entities"],
            areas=context["areas"],
            entities_by_domain=context["entities_by_domain"],
        )

    except Exception as e:
        logger.error("Failed to get context", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/search", response_model=SearchResponse)
async def search_web(request: SearchRequest):
    """Search web via enhanced Perplexity"""
    start_time = time.time()

    try:
        result = await enhanced_perplexity_client.search(
            query=request.query,
            requested_recency_days=request.recency_days,
            category=request.category,
            max_results=request.max_results,
        )

        duration = time.time() - start_time
        metrics.record_perplexity_search(result["category"], "success", duration)

        return SearchResponse(
            answer=result["answer"],
            sources=result["sources"],
            category=result["category"],
            recency=result["policy"].get("recency_days"),
            metadata=result.get("policy"),
        )

    except Exception as e:
        duration = time.time() - start_time
        metrics.record_perplexity_search("unknown", "error", duration)
        logger.error("Search failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/habr/search", response_model=HabrSearchResponse)
async def search_habr(
    query: str = None,
    tags: str = None,
    hubs: str = None,
    days: int = None,
    limit: int = 10,
):
    """Search Habr articles"""
    start_time = time.time()

    try:
        tags_list = tags.split(",") if tags else None
        hubs_list = hubs.split(",") if hubs else None

        articles = await habr_client.search(
            query=query,
            tags=tags_list,
            hubs=hubs_list,
            days=days,
            limit=limit,
        )

        duration = time.time() - start_time
        method = "rss" if not query else "html"
        metrics.record_habr_search(method, "success", duration)

        return HabrSearchResponse(
            articles=articles,
            count=len(articles),
        )

    except Exception as e:
        duration = time.time() - start_time
        metrics.record_habr_search("unknown", "error", duration)
        logger.error("Habr search failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/telegram/send")
async def send_telegram(request: TelegramSendRequest):
    """Send Telegram message"""
    try:
        success = await telegram_client.send_message(
            text=request.text,
            parse_mode=request.parse_mode,
        )

        metrics.record_telegram_message("manual", "success" if success else "error")

        return {"success": success}

    except Exception as e:
        metrics.record_telegram_message("manual", "error")
        logger.error("Telegram send failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/healthz", response_model=HealthResponse)
async def healthcheck():
    """Health check endpoint"""
    checks = {
        "database": True,
        "pipeline": True,
        "memory": True,
        "homeassistant": True,
    }

    # Check database
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
    except:
        checks["database"] = False

    # Check pipeline
    try:
        pipeline_health = await pipeline.health_check()
        checks["pipeline"] = pipeline_health.get("pipeline") == "healthy"
    except:
        checks["pipeline"] = False

    # Check memory
    try:
        memory_health = await memory_manager.health_check()
        checks["memory"] = memory_health.get("overall") == "healthy"
    except:
        checks["memory"] = False

    # Update metrics
    metrics.set_database_health(checks["database"])
    metrics.set_system_health(all(checks.values()))

    status = "healthy" if all(checks.values()) else "degraded"

    return HealthResponse(
        status=status,
        version=__version__,
        checks=checks,
    )


@router.get("/readyz")
async def readiness():
    """Readiness check endpoint"""
    return {"status": "ready"}


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=get_metrics(),
        media_type=get_content_type(),
    )


@router.websocket("/v1/realtime/ws")
async def realtime_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for OpenAI Realtime API
    
    Protocol:
    - Client connects
    - Client sends configuration
    - Bidirectional audio/text streaming
    - Server processes through RealtimeVoiceAgent
    - Function calling support
    """
    await websocket.accept()
    
    metrics.set_websocket_connections(1)
    logger.info("WebSocket connection established")

    # Create voice agent
    voice_agent = RealtimeVoiceAgent()
    await voice_agent.initialize()

    session_id = None
    user_id = None
    event_listener_task = None

    async def listen_and_forward_events():
        """Listen to agent events and forward to client"""
        if not session_id:
            return
            
        queue = voice_agent.event_handlers.get(session_id)
        if not queue:
            return
        
        try:
            while True:
                # Get event from agent's queue
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    await websocket.send_json({"type": "ping"})
                    continue
                
                event_type = event.get("type")
                
                # Forward event to client
                try:
                    # For audio events, keep base64 encoding
                    if event_type in ["response.audio.delta", "response.audio_transcript.delta"]:
                        await websocket.send_json(event)
                        metrics.record_websocket_message("outbound", event_type)
                    
                    # For other events, forward as-is
                    else:
                        await websocket.send_json(event)
                        metrics.record_websocket_message("outbound", event_type)
                    
                    logger.debug("Forwarded event to client", event_type=event_type)
                    
                except Exception as e:
                    logger.error("Failed to forward event", error=str(e))
                    break
                    
        except asyncio.CancelledError:
            logger.debug("Event listener cancelled")
        except Exception as e:
            logger.error("Event listener error", error=str(e))

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            metrics.record_websocket_message("inbound", message_type)
            
            # Check rate limit (skip for pings and audio chunks)
            if message_type not in ["ping", "audio_input"] and user_id:
                allowed, wait_time = ws_rate_limiter.check_limit(user_id)
                if not allowed:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Rate limit exceeded. Wait {wait_time:.1f} seconds.",
                    })
                    continue

            if message_type == "configure":
                # Configure session
                user_id = data.get("user_id", "anonymous")
                session_id = f"{user_id}_{int(time.time())}"
                instructions = data.get("instructions", "Ты — голосовой ассистент.")
                tools = data.get("tools", [])

                # Connect session
                await voice_agent.connect_session(
                    session_id=session_id,
                    instructions=instructions,
                    tools=tools,
                )

                # Start event listener task
                event_listener_task = asyncio.create_task(listen_and_forward_events())

                await websocket.send_json({
                    "type": "configured",
                    "session_id": session_id,
                })
                
                logger.info("Session configured", session_id=session_id, user_id=user_id)

            elif message_type == "audio_input":
                # Receive audio chunk
                if not session_id:
                    await websocket.send_json({"type": "error", "message": "Not configured"})
                    continue

                audio_base64 = data.get("audio")
                if audio_base64:
                    import base64
                    audio_data = base64.b64decode(audio_base64)
                    await voice_agent.send_audio(session_id, audio_data)

            elif message_type == "audio_commit":
                # Commit audio buffer (triggers response generation)
                if not session_id:
                    await websocket.send_json({"type": "error", "message": "Not configured"})
                    continue

                await voice_agent.commit_audio(session_id)
                logger.debug("Audio buffer committed", session_id=session_id)

            elif message_type == "text_input":
                # Receive text input (triggers response generation)
                if not session_id:
                    await websocket.send_json({"type": "error", "message": "Not configured"})
                    continue

                text = data.get("text")
                if text:
                    await voice_agent.send_text(session_id, text)
                    logger.debug("Text input sent", session_id=session_id, text_length=len(text))

            elif message_type == "cancel":
                # Cancel response (barge-in)
                if session_id:
                    await voice_agent.cancel_response(session_id)
                    logger.info("Response cancelled (barge-in)", session_id=session_id)

            elif message_type == "function_result":
                # Function call result
                if not session_id:
                    await websocket.send_json({"type": "error", "message": "Not configured"})
                    continue

                call_id = data.get("call_id")
                output = data.get("output")
                
                if call_id and output:
                    await voice_agent.send_function_result(session_id, call_id, output)
                    logger.debug("Function result sent", call_id=call_id)

            elif message_type == "ping":
                # Ping/pong
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed", session_id=session_id)
    except Exception as e:
        logger.error("WebSocket error", error=str(e), session_id=session_id)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        # Cancel event listener
        if event_listener_task and not event_listener_task.done():
            event_listener_task.cancel()
            try:
                await event_listener_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup
        if session_id:
            await voice_agent.disconnect_session(session_id)
        
        await voice_agent.shutdown()
        metrics.set_websocket_connections(0)
        logger.info("WebSocket cleanup completed", session_id=session_id)


@router.get("/")
async def root():
    """Info endpoint"""
    return {
        "name": "OpenAI Voice Assistant Proxy",
        "version": __version__,
        "status": "operational",
        "features": [
            "voice_first",
            "realtime_api",
            "enforced_recency",
            "policy_based_memory",
            "pipeline_architecture",
        ],
        "endpoints": {
            "command": "POST /v1/command",
            "confirm": "POST /v1/confirm",
            "search": "POST /v1/search",
            "habr": "GET /v1/habr/search",
            "context": "GET /v1/context",
            "realtime": "WS /v1/realtime/ws",
            "health": "GET /healthz",
            "metrics": "GET /metrics",
        },
    }
