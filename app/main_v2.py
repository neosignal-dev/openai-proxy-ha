"""Main FastAPI application with refactored architecture"""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db
from app.api.routes_v2 import router
from app.services.monitoring import metrics
from app.services.pipeline.orchestrator import pipeline
from app.services.memory_v2.manager import memory_manager
from app.services.tts.openai_tts import openai_tts
from app.services.search.perplexity_enhanced import enhanced_perplexity_client
from app import __version__

# Setup logging
setup_logging()
logger = get_logger(__name__)


def check_dependencies():
    """Check critical dependencies on startup"""
    missing_deps = []
    
    # Check websockets
    try:
        import websockets
    except ImportError:
        missing_deps.append("websockets")
    
    # Check numpy
    try:
        import numpy
    except ImportError:
        missing_deps.append("numpy")
    
    # Check chromadb
    try:
        import chromadb
    except ImportError:
        missing_deps.append("chromadb")
    
    # Check openai
    try:
        from openai import AsyncOpenAI
    except ImportError:
        missing_deps.append("openai")
    
    if missing_deps:
        logger.error(
            "Missing required dependencies",
            missing=missing_deps,
        )
        raise RuntimeError(
            f"Missing required dependencies: {', '.join(missing_deps)}. "
            f"Run: pip install {' '.join(missing_deps)}"
        )
    
    logger.info("All dependencies verified")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with new architecture"""
    # Startup
    logger.info(
        "Starting OpenAI Voice Assistant Proxy",
        version=__version__,
        architecture="voice-first-v2",
    )
    
    # Check dependencies first
    check_dependencies()
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize memory system
    try:
        await memory_manager.initialize()
        logger.info("Memory manager initialized")
    except Exception as e:
        logger.error("Memory initialization failed", error=str(e))
    
    # Initialize pipeline
    try:
        await pipeline.initialize()
        logger.info("Pipeline orchestrator initialized")
    except Exception as e:
        logger.error("Pipeline initialization failed", error=str(e))
    
    # Initialize TTS
    try:
        await openai_tts.initialize()
        logger.info("TTS provider initialized")
    except Exception as e:
        logger.error("TTS initialization failed", error=str(e))
    
    # Set initial health
    metrics.set_system_health(True)
    metrics.set_database_health(True)
    
    logger.info(
        "Application started successfully",
        features=[
            "voice_first",
            "realtime_api",
            "enforced_recency",
            "policy_based_memory",
            "pipeline_architecture",
        ],
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Cleanup resources
    try:
        await pipeline.shutdown()
        await memory_manager.shutdown()
        await openai_tts.shutdown()
        await enhanced_perplexity_client.close()
        logger.info("All services shutdown gracefully")
    except Exception as e:
        logger.error("Shutdown error", error=str(e))


# Create FastAPI app
app = FastAPI(
    title="OpenAI Voice Assistant Proxy for Home Assistant",
    description=(
        "Voice-first LLM assistant with OpenAI Realtime API, enforced recency policies, "
        "policy-based memory, and safe home automation control."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, configure specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing and metrics middleware
@app.middleware("http")
async def add_process_time_and_metrics(request: Request, call_next):
    """Add request timing, metrics, and error handling"""
    start_time = time.time()
    request_id = f"{int(start_time * 1000)}"
    
    logger.info(
        "Request started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Add headers
        response.headers["X-Process-Time"] = f"{duration:.3f}"
        response.headers["X-Request-ID"] = request_id
        
        # Record metrics
        metrics.record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
            duration=duration,
        )
        
        logger.info(
            "Request completed",
            request_id=request_id,
            status=response.status_code,
            duration_ms=int(duration * 1000),
        )
        
        return response
    
    except Exception as e:
        duration = time.time() - start_time
        
        logger.error(
            "Request failed",
            request_id=request_id,
            error=str(e),
            path=request.url.path,
            duration_ms=int(duration * 1000),
        )
        
        metrics.record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status=500,
            duration=duration,
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )


# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint with architecture info"""
    return {
        "name": "OpenAI Voice Assistant Proxy",
        "version": __version__,
        "architecture": "voice-first-v2",
        "status": "operational",
        "features": {
            "voice_first": "OpenAI Realtime API for low-latency voice interaction",
            "enforced_recency": "Policy-based web search with mandatory recency for time-sensitive queries",
            "policy_memory": "Smart memory with automatic importance classification",
            "pipeline": "Modular pipeline: Intent → Context → Plan → Execute → Response",
            "agents": "Multiple agent types: Text, Realtime Voice",
            "tts": "High-quality OpenAI TTS with 6 voices",
            "safety": "Confirmation for dangerous actions, audit logging, rate limiting",
        },
        "endpoints": {
            "command": "POST /v1/command - Execute voice/text command",
            "confirm": "POST /v1/confirm - Confirm pending action",
            "search": "POST /v1/search - Web search with enforced recency",
            "habr": "GET /v1/habr/search - Search Habr.com articles",
            "context": "GET /v1/context - Get Home Assistant context",
            "telegram": "POST /v1/telegram/send - Send Telegram message",
            "realtime": "WS /v1/realtime/ws - WebSocket for Realtime API",
            "health": "GET /healthz - Health check",
            "ready": "GET /readyz - Readiness check",
            "metrics": "GET /metrics - Prometheus metrics",
            "docs": "GET /docs - Interactive API documentation",
        },
        "documentation": {
            "api_docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main_v2:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        ws_ping_interval=30,
        ws_ping_timeout=10,
    )
