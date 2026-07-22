"""
Request schemas for API endpoints
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PredictRequest(BaseModel):
    """Request model for prediction endpoint (multipart/form-data handled separately)"""
    patient_id: str = Field(..., description="Patient identifier (anonymized)")
    study_id: Optional[str] = Field(None, description="Study identifier")
    acquisition_date: Optional[datetime] = Field(None, description="Image acquisition date")
    view_position: Optional[str] = Field(None, description="View position (PA, AP, LAT, etc.)")
    return_explanations: bool = Field(
        default=False,
        description="Whether to include Grad-CAM explanations in response"
    )
    
    @field_validator("patient_id")
    @classmethod
    def validate_patient_id(cls, v: str) -> str:
        """Validate patient ID format"""
        if not v or len(v) < 3:
            raise ValueError("Patient ID must be at least 3 characters")
        return v


class ExplainRequest(BaseModel):
    """Request model for explanation endpoint"""
    request_id: str = Field(..., description="Original prediction request ID")
    diseases: Optional[List[str]] = Field(
        default=None,
        description="Specific diseases to explain. If None, explain all positive predictions"
    )
    overlay_alpha: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Overlay transparency for heatmap visualization"
    )
    
    @field_validator("diseases")
    @classmethod
    def validate_diseases(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate disease names"""
        if v is not None:
            allowed = [
                "pneumonia",
                "tuberculosis",
                "cardiomegaly",
                "pleural_effusion",
                "edema",
                "fracture",
            ]
            for disease in v:
                if disease not in allowed:
                    raise ValueError(f"Invalid disease: {disease}. Allowed: {allowed}")
        return v


class FeedbackRequest(BaseModel):
    """Request model for feedback endpoint"""
    request_id: str = Field(..., description="Original prediction request ID")
    radiologist_id: str = Field(..., description="Radiologist identifier")
    ground_truth: Dict[str, bool] = Field(
        ...,
        description="Ground truth labels from radiologist review"
    )
    comments: Optional[str] = Field(
        None,
        max_length=2000,
        description="Radiologist comments"
    )
    quality_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Quality rating (1-5, where 5 is excellent)"
    )
    review_time_seconds: Optional[int] = Field(
        None,
        description="Time spent reviewing in seconds"
    )
    flagged_for_training: bool = Field(
        default=False,
        description="Flag this case for inclusion in training dataset"
    )
    
    @field_validator("ground_truth")
    @classmethod
    def validate_ground_truth(cls, v: Dict[str, bool]) -> Dict[str, bool]:
        """Validate ground truth format"""
        allowed_diseases = [
            "pneumonia",
            "tuberculosis",
            "cardiomegaly",
            "pleural_effusion",
            "edema",
            "fracture",
        ]
        
        for disease in v.keys():
            if disease not in allowed_diseases:
                raise ValueError(f"Invalid disease in ground truth: {disease}")
        
        return v
    
    @field_validator("comments")
    @classmethod
    def sanitize_comments(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize comments to prevent injection"""
        if v:
            # Remove potential HTML/script tags
            import re
            v = re.sub(r'<[^>]+>', '', v)
        return v


class BatchPredictRequest(BaseModel):
    """Request model for batch prediction (future feature)"""
    batch_id: str = Field(..., description="Batch identifier")
    patient_ids: List[str] = Field(..., description="List of patient IDs")
    priority: int = Field(default=1, ge=1, le=5, description="Priority (1=low, 5=critical)")
    
    @field_validator("patient_ids")
    @classmethod
    def validate_batch_size(cls, v: List[str]) -> List[str]:
        """Validate batch size"""
        if len(v) > 100:
            raise ValueError("Batch size cannot exceed 100")
        return v
