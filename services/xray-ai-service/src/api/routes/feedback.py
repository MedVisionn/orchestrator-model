"""
Feedback endpoint
POST /feedback - Submit radiologist feedback
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import check_rate_limit, get_current_user
from src.core.config import get_settings
from src.core.logging import get_logger
from src.schemas.requests import FeedbackRequest
from src.schemas.responses import ErrorResponse, FeedbackResponse
from src.services.feedback import FeedbackService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid feedback"},
        404: {"model": ErrorResponse, "description": "Request ID not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Submit radiologist feedback",
    description="""
    Submit radiologist feedback for a previous prediction to enable continuous learning.
    
    **Feedback Components**:
    - Ground truth labels (actual diagnoses)
    - Quality rating (1-5 scale)
    - Optional comments
    - Flag for training dataset inclusion
    
    **Continuous Learning Workflow**:
    1. Radiologist reviews AI prediction
    2. Submits ground truth labels via this endpoint
    3. Feedback stored in database
    4. Periodic aggregation for dataset updates
    5. Offline training with new data
    6. Model improvement and deployment
    
    **Privacy & Security**:
    - All feedback is logged for audit trail
    - No PHI (Protected Health Information) in comments
    - Feedback tied to request_id, not patient identifiers
    """,
)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: str = Depends(get_current_user),
    _rate_limit: None = Depends(check_rate_limit),
) -> FeedbackResponse:
    """
    Submit feedback for a prediction
    
    Args:
        request: FeedbackRequest with ground truth and ratings
        current_user: Current authenticated user (optional)
    
    Returns:
        FeedbackResponse with confirmation
    
    Raises:
        HTTPException: For invalid feedback or processing errors
    """
    logger.info(
        "Feedback submission received",
        request_id=request.request_id,
        radiologist_id=request.radiologist_id,
        quality_rating=request.quality_rating,
    )
    
    try:
        # Get feedback service
        feedback_service = FeedbackService()
        
        # Submit feedback
        result = await feedback_service.submit_feedback(
            request_id=request.request_id,
            radiologist_id=request.radiologist_id,
            ground_truth=request.ground_truth,
            comments=request.comments,
            quality_rating=request.quality_rating,
            review_time_seconds=request.review_time_seconds,
            flagged_for_training=request.flagged_for_training,
        )
        
        logger.info(
            "Feedback submitted successfully",
            feedback_id=result.feedback_id,
            request_id=request.request_id,
        )
        
        return result
        
    except ValueError as e:
        # Invalid feedback or request ID not found
        logger.warning(
            "Feedback submission failed - invalid input",
            request_id=request.request_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
        
    except Exception as e:
        # Unexpected errors
        logger.error(
            "Feedback submission failed",
            request_id=request.request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while submitting feedback.",
        )


@router.get(
    "/feedback/stats",
    status_code=status.HTTP_200_OK,
    summary="Get feedback statistics",
    description="Get aggregated feedback statistics (admin only)",
)
async def get_feedback_stats(
    current_user: str = Depends(get_current_user),
):
    """
    Get feedback statistics (future feature)
    """
    # TODO: Implement feedback statistics
    return {
        "total_feedback": 0,
        "avg_quality_rating": 0.0,
        "agreement_rate": 0.0,
        "message": "Feature coming soon",
    }
