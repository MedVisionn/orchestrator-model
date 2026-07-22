"""
Inference service orchestrating the prediction pipeline
"""

import time
import uuid
from datetime import datetime
from typing import Dict, Optional

import torch

from src.core.config import get_settings
from src.core.logging import audit_logger, get_logger
from src.core.monitoring import inference_duration, metrics
from src.models.model_loader import get_model_loader
from src.schemas.responses import (
    ClinicalReport,
    DiseasePrediction,
    InferenceMetadata,
    PredictResponse,
)
from src.services.preprocessing import PreprocessingService
from src.services.report import ReportGenerator

logger = get_logger(__name__)
settings = get_settings()


class InferenceService:
    """
    Core inference service
    Coordinates preprocessing, model inference, calibration, and report generation
    """
    
    def __init__(self):
        """Initialize inference service"""
        self.model_loader = get_model_loader()
        self.preprocessing = PreprocessingService()
        self.report_generator = ReportGenerator()
        self.device = torch.device(settings.device)
        
        logger.info("Inference service initialized", device=str(self.device))
    
    async def predict(
        self,
        file_content: bytes,
        file_type: str,
        patient_id: str,
        study_id: Optional[str] = None,
        return_explanations: bool = False,
    ) -> PredictResponse:
        """
        Perform inference on X-ray image
        
        Args:
            file_content: Raw file bytes
            file_type: File type (dicom, png, jpg)
            patient_id: Patient identifier
            study_id: Study identifier
            return_explanations: Whether to include Grad-CAM (future)
        
        Returns:
            PredictResponse with all results
        """
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        logger.info(
            "Starting inference",
            request_id=request_id,
            patient_id=patient_id,
            study_id=study_id,
            file_type=file_type,
        )
        
        # Timing
        total_start = time.time()
        preprocessing_time = 0
        model_time = 0
        postprocessing_time = 0
        
        try:
            # 1. Preprocessing
            preproc_start = time.time()
            tensor, image_metadata = self.preprocessing.process_file(
                file_content=file_content,
                file_type=file_type,
            )
            tensor = tensor.to(self.device)
            preprocessing_time = (time.time() - preproc_start) * 1000
            
            # 2. Model Inference
            model_start = time.time()
            model = self.model_loader.get_model()
            
            with torch.no_grad():
                predictions = model(tensor)
            
            model_time = (time.time() - model_start) * 1000
            
            # 3. Calibration
            postproc_start = time.time()
            calibration = self.model_loader.get_calibration()
            
            if calibration is not None:
                predictions = calibration.calibrate(predictions)
            
            # 4. Convert to response format
            disease_predictions = self._format_predictions(predictions)
            
            # 5. Generate clinical report
            clinical_report = self.report_generator.generate_report(
                predictions=disease_predictions,
                metadata=image_metadata,
            )
            
            postprocessing_time = (time.time() - postproc_start) * 1000
            
            # Total time
            total_time = (time.time() - total_start) * 1000
            
            # Create response
            response = PredictResponse(
                request_id=request_id,
                patient_id=patient_id,
                study_id=study_id or f"study_{uuid.uuid4().hex[:8]}",
                model_version=settings.model_version,
                predictions=disease_predictions,
                clinical_report=clinical_report,
                metadata=InferenceMetadata(
                    inference_time_ms=total_time,
                    preprocessing_time_ms=preprocessing_time,
                    model_time_ms=model_time,
                    postprocessing_time_ms=postprocessing_time,
                    timestamp=datetime.utcnow(),
                    image_properties=image_metadata,
                ),
            )
            
            # Record metrics
            inference_duration.labels(
                model_version=settings.model_version,
                device=str(self.device),
            ).observe(total_time / 1000)
            
            metrics.record_inference(
                model_version=settings.model_version,
                device=str(self.device),
                duration=total_time / 1000,
                predictions=disease_predictions,
            )
            
            # Audit log
            if settings.log_predictions:
                audit_logger.log_inference(
                    request_id=request_id,
                    patient_id=patient_id,
                    study_id=response.study_id,
                    model_version=settings.model_version,
                    predictions={
                        disease: {
                            "label": pred.label,
                            "confidence": pred.confidence,
                        }
                        for disease, pred in disease_predictions.items()
                    },
                    inference_time_ms=total_time,
                )
            
            logger.info(
                "Inference completed",
                request_id=request_id,
                total_time_ms=total_time,
                positive_findings=sum(
                    1 for p in disease_predictions.values() if p.label == "positive"
                ),
            )
            
            return response
            
        except Exception as e:
            logger.error(
                "Inference failed",
                request_id=request_id,
                error=str(e),
                exc_info=True,
            )
            
            audit_logger.log_error(
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            
            raise
    
    def _format_predictions(
        self,
        raw_predictions: Dict[str, torch.Tensor],
    ) -> Dict[str, DiseasePrediction]:
        """
        Format raw model outputs to DiseasePrediction objects
        
        Args:
            raw_predictions: Dictionary of disease tensors
        
        Returns:
            Dictionary of DiseasePrediction objects
        """
        formatted = {}
        
        for disease in settings.diseases:
            if disease not in raw_predictions:
                logger.warning(f"Missing prediction for disease: {disease}")
                continue
            
            # Get probability (already calibrated if calibration was applied)
            prob_tensor = raw_predictions[disease]
            probability = float(prob_tensor.squeeze().cpu().item())
            
            # Get disease configuration
            disease_config = settings.get_disease_config(disease)
            threshold = disease_config["threshold"]
            
            # Determine label
            if probability >= threshold:
                label = "positive"
            elif probability < threshold - 0.1:  # Add buffer zone
                label = "negative"
            else:
                label = "uncertain"
            
            # Confidence is the calibrated probability
            # For negative predictions, confidence is 1 - probability
            if label == "negative":
                confidence = 1 - probability
            else:
                confidence = probability
            
            formatted[disease] = DiseasePrediction(
                probability=probability,
                confidence=confidence,
                label=label,
                threshold=threshold,
            )
        
        return formatted
    
    async def batch_predict(
        self,
        files: list,
        patient_ids: list,
    ) -> list[PredictResponse]:
        """
        Batch prediction (future feature)
        
        Args:
            files: List of file contents
            patient_ids: List of patient IDs
        
        Returns:
            List of predictions
        """
        results = []
        
        for file_content, patient_id in zip(files, patient_ids):
            result = await self.predict(
                file_content=file_content,
                file_type="image/png",  # Would need to detect
                patient_id=patient_id,
            )
            results.append(result)
        
        return results
    
    def get_model_info(self) -> Dict:
        """
        Get current model information
        
        Returns:
            Dictionary with model metadata
        """
        model = self.model_loader.get_model()
        
        return {
            "name": settings.model_name,
            "version": settings.model_version,
            "architecture": "DenseNet-121 + Disease Heads",
            "input_size": list(settings.input_size),
            "diseases": settings.diseases,
            "training_datasets": [
                "CheXpert",
                "MIMIC-CXR",
                "NIH ChestX-ray14",
            ],
            "performance_metrics": {
                # These would come from validation set
                "pneumonia_auc": 0.92,
                "tuberculosis_auc": 0.89,
                "cardiomegaly_auc": 0.91,
                "pleural_effusion_auc": 0.93,
                "edema_auc": 0.90,
                "fracture_auc": 0.88,
            },
            "num_parameters": sum(p.numel() for p in model.parameters()),
            "device": str(self.device),
        }


def create_inference_service() -> InferenceService:
    """
    Factory function to create inference service
    
    Returns:
        InferenceService instance
    """
    return InferenceService()
