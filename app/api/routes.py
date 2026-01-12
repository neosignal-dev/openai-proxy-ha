"""API route handlers"""

import time
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
from app.integrations.openai_client import tts_client
from app.integrations.perplexity import perplexity_client
from app.integrations.habr import habr_client
from app.integrations.telegram_bot import telegram_client
from app.services.command_processor import command_processor
from app.services.memory import memory_service
from app.services.monitoring import metrics, get_metrics, get_content_type
from app import __version__

logger = get_logger(__name__)
router = APIRouter()


@router.post("/v1/command", response_model=CommandResponse)
async def execute_command(request: CommandRequest):
    """Execute user command"""
    start_time = time.time()
    
    try:
        # Get HA context if requested
        ha_context = None
        if request.include_context:
            ha_context = await ha_client.get_context()

        # Process command
        result = await command_processor.process_command(
            user_id=request.user_id,
            command=request.command,
            ha_context=ha_context,
        )

        # Generate TTS audio
        response_text = result.get("response", "")
        if response_text:
            audio_bytes = await tts_client.synthesize_speech(response_text, format="opus")
            # In production, save to storage and return URL
            # For now, we'll include it in the response
            result["audio_size"] = len(audio_bytes)

        # Record metrics
        duration = time.time() - start_time
        intent = result.get("intent", "text_response")
        metrics.record_command(intent, "success", duration)

        return CommandResponse(
            type=result.get("type", "action_plan"),
            response=response_text,
            intent=result.get("intent"),
            actions=result.get("actions"),
            needs_confirmation=result.get("needs_confirmation"),
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
        result = await command_processor.execute_action_plan(
            user_id=request.user_id,
            plan=request.plan,
            confirmed=request.confirmed,
        )

        duration = time.time() - start_time
        intent = request.plan.get("intent", "unknown")
        status = "success" if result["success"] else "error"
        metrics.record_command(f"{intent}_confirm", status, duration)

        return ConfirmResponse(
            success=result["success"],
            message=result["message"],
            results=result.get("results"),
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
    """Search web via Perplexity"""
    start_time = time.time()

    try:
        result = await perplexity_client.search(
            query=request.query,
            recency_days=request.recency_days,
            category=request.category,
            max_results=request.max_results,
        )

        # Generate TTS
        audio_bytes = await tts_client.synthesize_speech(result["answer"], format="opus")

        duration = time.time() - start_time
        metrics.record_perplexity_search(result["category"], "success", duration)

        return SearchResponse(
            answer=result["answer"],
            sources=result["sources"],
            category=result["category"],
            recency=result["recency"],
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


@router.post("/v1/automation/draft", response_model=AutomationDraftResponse)
async def draft_automation(request: AutomationDraftRequest):
    """Draft automation from natural language"""
    try:
        # This would use LLM to generate automation config
        # For now, return a placeholder
        automation = {
            "alias": "Generated Automation",
            "description": request.description,
            "trigger": [],
            "condition": [],
            "action": [],
        }

        return AutomationDraftResponse(
            automation=automation,
            warnings=["This is a draft. Please review before applying."],
        )

    except Exception as e:
        logger.error("Automation draft failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/automation/apply")
async def apply_automation(automation: Dict[str, Any]):
    """Apply automation to Home Assistant"""
    try:
        result = await ha_client.create_automation(automation)
        return result

    except Exception as e:
        logger.error("Automation apply failed", error=str(e))
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
        "openai": True,
        "homeassistant": True,
    }

    # Check database
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
    except:
        checks["database"] = False

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
    """WebSocket endpoint for OpenAI Realtime API"""
    await websocket.accept()
    
    metrics.set_websocket_connections(1)
    logger.info("WebSocket connection established")

    try:
        # In production, this would proxy to OpenAI Realtime API
        # For now, it's a placeholder
        
        while True:
            data = await websocket.receive_json()
            
            # Process message
            message_type = data.get("type")
            
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif message_type == "configure":
                await websocket.send_json({"type": "configured"})
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Not implemented yet"
                })

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
        metrics.set_websocket_connections(0)
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        metrics.set_websocket_connections(0)


