"""
Explainability endpoint
POST /explain - Generate Grad-CAM visualizations
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import check_rate_limit
from src.core.config import get_settings
from src.core.logging import get_logger
from src.schemas.requests import ExplainRequest
from src.schemas.responses import ErrorResponse, ExplainResponse
from src.services.explainability import ExplainabilityService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.post(
    "/explain",
    response_model=ExplainResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Request ID not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Generate Grad-CAM explanations",
    description="""
    Generate visual explanations (Grad-CAM heatmaps) for a previous prediction.
    
    **How it works**:
    1. Provide the request_id from a previous /predict call
    2. Optionally specify which diseases to explain
    3. Receive attention heatmaps showing where the model "looks"
    
    **Output**:
    - Heatmap image (base64 encoded PNG)
    - Overlay image (heatmap on original X-ray)
    - Attention regions with coordinates and intensity
    
    **Use Cases**:
    - Validate model predictions
    - Clinical decision support
    - Research and development
    - Regulatory documentation
    """,
)
async def explain(
    request: ExplainRequest,
    _rate_limit: None = Depends(check_rate_limit),
) -> ExplainResponse:
    """
    Generate Grad-CAM explanations for predictions
    
    Args:
        request: ExplainRequest with request_id and optional disease list
    
    Returns:
        ExplainResponse with heatmaps and attention regions
    
    Raises:
        HTTPException: For invalid request or processing errors
    """
    logger.info(
        "Explanation request received",
        request_id=request.request_id,
        diseases=request.diseases,
    )
    
    try:
        # Get explainability service
        explainability_service = ExplainabilityService()
        
        # Generate explanations
        result = await explainability_service.explain(
            request_id=request.request_id,
            diseases=request.diseases,
            overlay_alpha=request.overlay_alpha,
        )
        
        logger.info(
            "Explanation generated successfully",
            request_id=request.request_id,
            num_diseases=len(result.explanations),
        )
        
        return result
        
    except ValueError as e:
        # Request ID not found or invalid
        logger.warning(
            "Explanation request failed - invalid input",
            request_id=request.request_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
        
    except Exception as e:
        # Unexpected errors
        logger.error(
            "Explanation generation failed",
            request_id=request.request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during explanation generation.",
        )
