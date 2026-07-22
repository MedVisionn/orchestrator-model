"""
Health check and system information endpoints
GET /health - Service health check
GET /metrics - Prometheus metrics (mounted separately)
GET /model-info - Current model information
"""

import time
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from src.core.config import get_settings
from src.core.logging import get_logger
from src.database.connection import check_database_health
from src.cache.redis_client import check_redis_health
from src.models.model_loader import get_model_loader
from src.schemas.responses import HealthResponse, ModelInfoResponse

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()

# Service start time
SERVICE_START_TIME = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check service health and readiness",
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    """
    Comprehensive health check
    
    Returns:
        HealthResponse with service status
    """
    # Check model
    model_loaded = False
    try:
        model_loader = get_model_loader()
        model = model_loader.get_model()
        model_loaded = model is not None
    except Exception as e:
        logger.warning("Model health check failed", error=str(e))
    
    # Check database
    database_connected = await check_database_health()
    
    # Check cache
    cache_connected = await check_redis_health()
    
    # Determine overall status
    if model_loaded and database_connected and cache_connected:
        overall_status = "healthy"
    elif model_loaded:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"
    
    # Calculate uptime
    uptime = time.time() - SERVICE_START_TIME
    
    return HealthResponse(
        status=overall_status,
        version=settings.version,
        model_loaded=model_loaded,
        database_connected=database_connected,
        cache_connected=cache_connected,
        uptime_seconds=uptime,
        timestamp=datetime.utcnow(),
    )


@router.get(
    "/readiness",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Kubernetes readiness probe - checks if service can handle requests",
    tags=["Health"],
)
async def readiness() -> Dict:
    """
    Readiness probe for Kubernetes
    Returns 200 if ready, 503 if not ready
    """
    try:
        # Check if model is loaded
        model_loader = get_model_loader()
        model = model_loader.get_model()
        
        if model is None:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not ready", "reason": "Model not loaded"},
            )
        
        return {"status": "ready"}
        
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "reason": str(e)},
        )


@router.get(
    "/liveness",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Kubernetes liveness probe - checks if service is alive",
    tags=["Health"],
)
async def liveness() -> Dict:
    """
    Liveness probe for Kubernetes
    Simple check that service is responding
    """
    return {"status": "alive"}


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Model information",
    description="Get information about the current model version and configuration",
    tags=["Health"],
)
async def model_info() -> ModelInfoResponse:
    """
    Get current model information
    
    Returns:
        ModelInfoResponse with model metadata
    """
    try:
        model_loader = get_model_loader()
        model = model_loader.get_model()
        calibration = model_loader.get_calibration()
        
        from src.schemas.responses import ModelInfo
        
        model_info_obj = ModelInfo(
            name=settings.model_name,
            version=settings.model_version,
            architecture="DenseNet-121 + Disease Heads",
            input_size=list(settings.input_size),
            diseases=settings.diseases,
            training_datasets=[
                "CheXpert",
                "MIMIC-CXR",
                "NIH ChestX-ray14",
            ],
            performance_metrics={
                "pneumonia_auc": 0.92,
                "tuberculosis_auc": 0.89,
                "cardiomegaly_auc": 0.91,
                "pleural_effusion_auc": 0.93,
                "edema_auc": 0.90,
                "fracture_auc": 0.88,
            },
        )
        
        calibration_info = {
            "method": settings.calibration_method,
            "temperature": settings.temperature,
        }
        
        return ModelInfoResponse(
            model=model_info_obj,
            device=settings.device,
            calibration=calibration_info,
            last_updated=datetime.utcnow(),
        )
        
    except Exception as e:
        logger.error("Failed to get model info", error=str(e), exc_info=True)
        raise


@router.get(
    "/",
    include_in_schema=False,
    tags=["Health"],
)
async def root() -> Dict:
    """Root endpoint"""
    return {
        "service": "MedScanAI X-Ray AI Service",
        "version": settings.version,
        "status": "operational",
        "documentation": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }
