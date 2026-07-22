"""
MedScanAI X-Ray AI Service
Main application entry point
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from src.api.middleware import (
    LoggingMiddleware,
    RequestIDMiddleware,
    TimingMiddleware,
)
from src.api.routes import explain, feedback, health, predict
from src.cache.redis_client import close_redis, init_redis
from src.core.config import get_settings
from src.core.logging import get_logger, setup_logging
from src.core.monitoring import metrics
from src.database.connection import close_database, init_database
from src.models.model_loader import ModelLoader

# Initialize settings and logging
settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager - handles startup and shutdown
    """
    # Startup
    logger.info("Starting X-Ray AI Service", version=settings.version)
    
    try:
        # Initialize database connections
        logger.info("Initializing database connections")
        await init_database()
        
        # Initialize Redis cache
        logger.info("Initializing Redis cache")
        await init_redis()
        
        # Load ML model
        logger.info("Loading ML model", model_version=settings.model_version)
        model_loader = ModelLoader()
        await asyncio.to_thread(model_loader.load_model)
        
        # Store model loader in app state
        app.state.model_loader = model_loader
        
        logger.info("Service started successfully")
        metrics.service_starts.inc()
        
        yield
        
    except Exception as e:
        logger.error("Failed to start service", error=str(e), exc_info=True)
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down X-Ray AI Service")
        
        # Clean up database connections
        await close_database()
        
        # Clean up Redis connections
        await close_redis()
        
        # Clear model from memory
        if hasattr(app.state, "model_loader"):
            del app.state.model_loader
        
        logger.info("Service shut down complete")


# Create FastAPI application
app = FastAPI(
    title="MedScanAI X-Ray AI Service",
    description="""
    Production-grade chest X-ray analysis service with multi-label disease detection,
    explainability, and confidence calibration.
    
    ## Features
    
    * **Multi-label Disease Classification**: Pneumonia, TB, Cardiomegaly, Pleural Effusion, Edema, Fracture
    * **DICOM Support**: Native DICOM parsing and metadata extraction
    * **Grad-CAM Explainability**: Visual attention heatmaps for each disease
    * **Confidence Calibration**: Calibrated probability scores
    * **Clinical Report Generation**: Structured findings and recommendations
    * **Production Ready**: Monitoring, logging, error handling
    
    ## Security
    
    * Input validation on all endpoints
    * Rate limiting
    * File size restrictions
    * HIPAA-compliant logging
    """,
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compression Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Custom Middleware
app.add_middleware(TimingMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(predict.router, tags=["Inference"])
app.include_router(explain.router, tags=["Explainability"])
app.include_router(feedback.router, tags=["Feedback"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unhandled errors
    """
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    
    metrics.errors.labels(error_type="unhandled_exception").inc()
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": request.state.request_id if hasattr(request.state, "request_id") else None,
        },
    )


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Root endpoint - redirect to docs"""
    return {
        "service": "MedScanAI X-Ray AI Service",
        "version": settings.version,
        "documentation": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
    )
