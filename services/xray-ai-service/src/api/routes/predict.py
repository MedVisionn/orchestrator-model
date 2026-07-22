"""
Prediction endpoint
POST /predict - Disease prediction from chest X-ray
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.api.dependencies import (
    check_rate_limit,
    get_inference_service,
    validate_file_size,
)
from src.core.config import get_settings
from src.core.logging import get_logger
from src.schemas.responses import ErrorResponse, PredictResponse
from src.services.inference import InferenceService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.post(
    "/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Predict diseases from chest X-ray",
    description="""
    Upload a chest X-ray image (DICOM, PNG, or JPEG) and receive:
    - Multi-label disease predictions with confidence scores
    - Clinical report with findings and recommendations
    - Image metadata and processing statistics
    
    **Supported Diseases**:
    - Pneumonia
    - Tuberculosis
    - Cardiomegaly
    - Pleural Effusion
    - Edema
    - Fracture
    
    **File Requirements**:
    - Format: DICOM (.dcm), PNG (.png), JPEG (.jpg)
    - Max size: {max_size}MB
    - Min resolution: 224x224 pixels (higher recommended)
    
    **Rate Limits**:
    - {rate_limit} requests per {rate_window} seconds
    """.format(
        max_size=settings.max_file_size_mb,
        rate_limit=settings.rate_limit_requests,
        rate_window=settings.rate_limit_window,
    ),
)
async def predict(
    file: UploadFile = File(..., description="Chest X-ray image file"),
    patient_id: str = Form(..., description="Patient identifier (anonymized)"),
    study_id: Optional[str] = Form(None, description="Study identifier"),
    acquisition_date: Optional[str] = Form(None, description="Image acquisition date (ISO format)"),
    view_position: Optional[str] = Form(None, description="View position (PA, AP, LAT, etc.)"),
    return_explanations: bool = Form(False, description="Include Grad-CAM explanations"),
    inference_service: InferenceService = Depends(get_inference_service),
    _rate_limit: None = Depends(check_rate_limit),
) -> PredictResponse:
    """
    Predict diseases from chest X-ray image
    
    Args:
        file: Uploaded image file
        patient_id: Patient identifier
        study_id: Study identifier (optional)
        acquisition_date: Image acquisition date (optional)
        view_position: View position (optional)
        return_explanations: Whether to include Grad-CAM
        inference_service: Injected inference service
    
    Returns:
        PredictResponse with predictions, report, and metadata
    
    Raises:
        HTTPException: For invalid input or processing errors
    """
    logger.info(
        "Prediction request received",
        patient_id=patient_id,
        study_id=study_id,
        filename=file.filename,
        content_type=file.content_type,
    )
    
    try:
        # Validate file type
        allowed_types = [
            "application/dicom",
            "image/png",
            "image/jpeg",
            "image/jpg",
        ]
        
        file_extension = file.filename.split(".")[-1].lower() if file.filename else ""
        
        # Determine file type
        if file.content_type in allowed_types:
            file_type = file.content_type
        elif file_extension in ["dcm", "dicom"]:
            file_type = "application/dicom"
        elif file_extension in ["png"]:
            file_type = "image/png"
        elif file_extension in ["jpg", "jpeg"]:
            file_type = "image/jpeg"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed: DICOM, PNG, JPEG. Got: {file.content_type}",
            )
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size (backup check)
        if len(file_content) > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum of {settings.max_file_size_mb}MB",
            )
        
        # Validate file is not empty
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )
        
        # Perform inference
        result = await inference_service.predict(
            file_content=file_content,
            file_type=file_type,
            patient_id=patient_id,
            study_id=study_id,
            return_explanations=return_explanations,
        )
        
        logger.info(
            "Prediction completed successfully",
            request_id=result.request_id,
            patient_id=patient_id,
            num_positive_findings=sum(
                1 for p in result.predictions.values() if p.label == "positive"
            ),
        )
        
        return result
        
    except HTTPException:
        raise
        
    except ValueError as e:
        # Validation or preprocessing errors
        logger.error(
            "Validation error",
            patient_id=patient_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
        
    except Exception as e:
        # Unexpected errors
        logger.error(
            "Prediction failed",
            patient_id=patient_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during prediction. Please try again.",
        )


@router.post(
    "/predict/batch",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Batch prediction (Coming Soon)",
    description="Upload multiple X-ray images for batch processing",
)
async def predict_batch():
    """Batch prediction endpoint (future feature)"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Batch prediction is not yet implemented. Use /predict for single images.",
    )
