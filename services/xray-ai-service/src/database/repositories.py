"""
Data access layer (repositories)
Abstracts database operations
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.database.models import Feedback, InferenceRequest, ModelVersion

logger = get_logger(__name__)


class InferenceRepository:
    """Repository for inference requests"""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize repository"""
        self.session = session
    
    async def create_inference_request(
        self,
        request_id: str,
        patient_id: str,
        study_id: Optional[str],
        model_version: str,
        predictions: Dict,
        metadata: Optional[Dict] = None,
        **kwargs,
    ) -> InferenceRequest:
        """
        Create inference request record
        
        Args:
            request_id: Request identifier
            patient_id: Patient identifier
            study_id: Study identifier
            model_version: Model version used
            predictions: Prediction results
            metadata: Additional metadata
        
        Returns:
            Created InferenceRequest
        """
        inference_request = InferenceRequest(
            request_id=request_id,
            patient_id=patient_id,
            study_id=study_id,
            model_version=model_version,
            predictions=predictions,
            metadata=metadata,
            **kwargs,
        )
        
        if self.session:
            self.session.add(inference_request)
            await self.session.flush()
        
        logger.debug("Inference request created", request_id=request_id)
        
        return inference_request
    
    async def get_by_request_id(self, request_id: str) -> Optional[InferenceRequest]:
        """Get inference request by ID"""
        if not self.session:
            return None
        
        result = await self.session.execute(
            select(InferenceRequest).where(InferenceRequest.request_id == request_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_patient_id(
        self,
        patient_id: str,
        limit: int = 10,
    ) -> List[InferenceRequest]:
        """Get inference requests for a patient"""
        if not self.session:
            return []
        
        result = await self.session.execute(
            select(InferenceRequest)
            .where(InferenceRequest.patient_id == patient_id)
            .order_by(InferenceRequest.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class FeedbackRepository:
    """Repository for feedback"""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize repository"""
        self.session = session
    
    async def create_feedback(
        self,
        feedback_id: str,
        request_id: str,
        radiologist_id: str,
        ground_truth: Dict[str, bool],
        comments: Optional[str] = None,
        quality_rating: int = 3,
        review_time_seconds: Optional[int] = None,
        flagged_for_training: bool = False,
    ) -> Feedback:
        """
        Create feedback record
        
        Args:
            feedback_id: Feedback identifier
            request_id: Original request identifier
            radiologist_id: Radiologist identifier
            ground_truth: Ground truth labels
            comments: Optional comments
            quality_rating: Quality rating (1-5)
            review_time_seconds: Review time
            flagged_for_training: Training flag
        
        Returns:
            Created Feedback
        """
        feedback = Feedback(
            feedback_id=feedback_id,
            request_id=request_id,
            radiologist_id=radiologist_id,
            ground_truth=ground_truth,
            comments=comments,
            quality_rating=quality_rating,
            review_time_seconds=review_time_seconds,
            flagged_for_training=flagged_for_training,
        )
        
        if self.session:
            self.session.add(feedback)
            await self.session.flush()
        
        logger.debug("Feedback created", feedback_id=feedback_id)
        
        return feedback
    
    async def get_by_feedback_id(self, feedback_id: str) -> Optional[Feedback]:
        """Get feedback by ID"""
        if not self.session:
            return None
        
        result = await self.session.execute(
            select(Feedback).where(Feedback.feedback_id == feedback_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_request_id(self, request_id: str) -> List[Feedback]:
        """Get all feedback for a request"""
        if not self.session:
            return []
        
        result = await self.session.execute(
            select(Feedback)
            .where(Feedback.request_id == request_id)
            .order_by(Feedback.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_flagged_for_training(
        self,
        limit: int = 100,
    ) -> List[Feedback]:
        """Get feedback flagged for training"""
        if not self.session:
            return []
        
        result = await self.session.execute(
            select(Feedback)
            .where(Feedback.flagged_for_training == True)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class ModelVersionRepository:
    """Repository for model versions"""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize repository"""
        self.session = session
    
    async def create_model_version(
        self,
        version: str,
        model_name: str,
        model_path: str,
        training_dataset: Optional[str] = None,
        metrics: Optional[Dict] = None,
        status: str = "development",
    ) -> ModelVersion:
        """Create model version record"""
        model_version = ModelVersion(
            version=version,
            model_name=model_name,
            model_path=model_path,
            training_dataset=training_dataset,
            metrics=metrics,
            status=status,
        )
        
        if self.session:
            self.session.add(model_version)
            await self.session.flush()
        
        logger.debug("Model version created", version=version)
        
        return model_version
    
    async def get_by_version(self, version: str) -> Optional[ModelVersion]:
        """Get model version by version string"""
        if not self.session:
            return None
        
        result = await self.session.execute(
            select(ModelVersion).where(ModelVersion.version == version)
        )
        return result.scalar_one_or_none()
    
    async def get_by_status(self, status: str) -> List[ModelVersion]:
        """Get all model versions with given status"""
        if not self.session:
            return []
        
        result = await self.session.execute(
            select(ModelVersion)
            .where(ModelVersion.status == status)
            .order_by(ModelVersion.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def update_status(
        self,
        version: str,
        new_status: str,
    ) -> Optional[ModelVersion]:
        """Update model version status"""
        model_version = await self.get_by_version(version)
        
        if model_version and self.session:
            model_version.status = new_status
            if new_status == "production":
                model_version.deployed_at = datetime.utcnow()
            await self.session.flush()
        
        return model_version
