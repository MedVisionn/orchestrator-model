"""
Response schemas for API endpoints
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DiseasePrediction(BaseModel):
    """Individual disease prediction"""
    probability: float = Field(..., ge=0.0, le=1.0, description="Raw model probability")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence score")
    label: str = Field(..., description="Predicted label: positive, negative, or uncertain")
    threshold: float = Field(..., description="Decision threshold used")


class ImageMetadata(BaseModel):
    """Image metadata"""
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    modality: Optional[str] = Field(None, description="DICOM modality (e.g., DX, CR)")
    view_position: Optional[str] = Field(None, description="View position (PA, AP, LAT)")
    manufacturer: Optional[str] = Field(None, description="Equipment manufacturer")
    study_date: Optional[str] = Field(None, description="Study date")
    series_description: Optional[str] = Field(None, description="Series description")


class InferenceMetadata(BaseModel):
    """Inference timing and metadata"""
    inference_time_ms: float = Field(..., description="Total inference time in milliseconds")
    preprocessing_time_ms: float = Field(..., description="Preprocessing time in milliseconds")
    model_time_ms: float = Field(..., description="Model forward pass time in milliseconds")
    postprocessing_time_ms: float = Field(..., description="Postprocessing time in milliseconds")
    timestamp: datetime = Field(..., description="Inference timestamp")
    image_properties: ImageMetadata = Field(..., description="Input image metadata")


class ClinicalReport(BaseModel):
    """Clinical report with findings and recommendations"""
    impression: str = Field(..., description="Overall impression")
    findings: List[str] = Field(..., description="List of specific findings")
    recommendations: List[str] = Field(..., description="Clinical recommendations")
    limitations: str = Field(..., description="Limitations and disclaimers")


class PredictResponse(BaseModel):
    """Response model for prediction endpoint"""
    request_id: str = Field(..., description="Unique request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    study_id: Optional[str] = Field(None, description="Study identifier")
    model_version: str = Field(..., description="Model version used")
    predictions: Dict[str, DiseasePrediction] = Field(..., description="Disease predictions")
    clinical_report: ClinicalReport = Field(..., description="Generated clinical report")
    metadata: InferenceMetadata = Field(..., description="Inference metadata")


class AttentionRegion(BaseModel):
    """Region of interest from Grad-CAM"""
    x: int = Field(..., description="X coordinate (top-left)")
    y: int = Field(..., description="Y coordinate (top-left)")
    width: int = Field(..., description="Region width")
    height: int = Field(..., description="Region height")
    intensity: float = Field(..., ge=0.0, le=1.0, description="Attention intensity")
    anatomical_region: Optional[str] = Field(None, description="Anatomical region name")


class DiseaseExplanation(BaseModel):
    """Explanation for a single disease"""
    heatmap_base64: str = Field(..., description="Grad-CAM heatmap (base64 encoded PNG)")
    overlay_base64: str = Field(..., description="Heatmap overlaid on original image (base64)")
    attention_regions: List[AttentionRegion] = Field(..., description="Key attention regions")


class ExplainResponse(BaseModel):
    """Response model for explanation endpoint"""
    request_id: str = Field(..., description="Original request ID")
    explanations: Dict[str, DiseaseExplanation] = Field(..., description="Explanations by disease")
    generation_time_ms: float = Field(..., description="Explanation generation time")


class FeedbackResponse(BaseModel):
    """Response model for feedback endpoint"""
    feedback_id: str = Field(..., description="Unique feedback identifier")
    request_id: str = Field(..., description="Original request ID")
    status: str = Field(..., description="Feedback processing status")
    message: str = Field(..., description="Confirmation message")
    timestamp: datetime = Field(..., description="Feedback submission timestamp")


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str = Field(..., description="Service status: healthy, degraded, unhealthy")
    version: str = Field(..., description="Service version")
    model_loaded: bool = Field(..., description="Whether model is loaded")
    database_connected: bool = Field(..., description="Database connection status")
    cache_connected: bool = Field(..., description="Cache connection status")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    timestamp: datetime = Field(..., description="Health check timestamp")


class ModelInfo(BaseModel):
    """Model information"""
    name: str = Field(..., description="Model name")
    version: str = Field(..., description="Model version")
    architecture: str = Field(..., description="Model architecture")
    input_size: List[int] = Field(..., description="Expected input size [H, W]")
    diseases: List[str] = Field(..., description="Supported diseases")
    training_datasets: List[str] = Field(..., description="Training datasets")
    performance_metrics: Dict[str, float] = Field(..., description="Validation metrics")


class ModelInfoResponse(BaseModel):
    """Response model for model info endpoint"""
    model: ModelInfo = Field(..., description="Current model information")
    device: str = Field(..., description="Inference device (cuda/cpu)")
    calibration: Dict[str, Any] = Field(..., description="Calibration parameters")
    last_updated: datetime = Field(..., description="Model last updated timestamp")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    request_id: Optional[str] = Field(None, description="Request ID if available")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class MetricsResponse(BaseModel):
    """Response model for metrics summary endpoint"""
    total_requests: int = Field(..., description="Total requests processed")
    avg_inference_time_ms: float = Field(..., description="Average inference time")
    cache_hit_rate: float = Field(..., description="Cache hit rate")
    error_rate: float = Field(..., description="Error rate")
    predictions_by_disease: Dict[str, int] = Field(..., description="Prediction counts by disease")
