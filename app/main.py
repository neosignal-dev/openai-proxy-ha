"""Main FastAPI application"""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db
from app.api.routes import router
from app.services.monitoring import metrics
from app import __version__

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting OpenAI Proxy for Home Assistant", version=__version__)
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Set initial health
    metrics.set_system_health(True)
    metrics.set_database_health(True)
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title="OpenAI Proxy for Home Assistant",
    description="LLM-powered voice assistant and smart home controller",
    version=__version__,
    lifespan=lifespan,
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, configure specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request timing and metrics"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Add header
        response.headers["X-Process-Time"] = str(duration)
        
        # Record metrics
        metrics.record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
            duration=duration,
        )
        
        return response
    
    except Exception as e:
        duration = time.time() - start_time
        logger.error("Request failed", error=str(e), path=request.url.path)
        
        metrics.record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status=500,
            duration=duration,
        )
        
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "OpenAI Proxy for Home Assistant",
        "version": __version__,
        "status": "running",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


