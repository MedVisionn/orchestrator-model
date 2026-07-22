"""
SQLAlchemy ORM models
Database schema definitions
"""

from datetime import datetime
from typing import Dict

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from src.database.connection import Base


class InferenceRequest(Base):
    """
    Inference request audit log
    Stores all prediction requests for compliance and analysis
    """
    __tablename__ = "inference_requests"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Request identification
    request_id = Column(String(50), unique=True, nullable=False, index=True)
    patient_id = Column(String(100), nullable=False, index=True)
    study_id = Column(String(100), nullable=True)
    
    # Model information
    model_version = Column(String(20), nullable=False)
    
    # Predictions (JSONB for flexibility)
    predictions = Column(JSON, nullable=False)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Image properties
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    modality = Column(String(10), nullable=True)
    view_position = Column(String(10), nullable=True)
    
    # Timing
    inference_time_ms = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index("ix_inference_requests_created_at_desc", created_at.desc()),
        Index("ix_inference_requests_patient_created", patient_id, created_at.desc()),
    )
    
    def __repr__(self) -> str:
        return f"<InferenceRequest(request_id={self.request_id}, patient_id={self.patient_id})>"


class Feedback(Base):
    """
    Radiologist feedback
    Enables continuous learning pipeline
    """
    __tablename__ = "feedback"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Feedback identification
    feedback_id = Column(String(50), unique=True, nullable=False, index=True)
    request_id = Column(String(50), nullable=False, index=True)
    
    # Radiologist information
    radiologist_id = Column(String(100), nullable=False, index=True)
    
    # Ground truth labels (JSONB)
    ground_truth = Column(JSON, nullable=False)
    
    # Feedback details
    comments = Column(Text, nullable=True)
    quality_rating = Column(Integer, nullable=False)  # 1-5 scale
    review_time_seconds = Column(Integer, nullable=True)
    
    # Training dataset flag
    flagged_for_training = Column(Boolean, default=False, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index("ix_feedback_created_at_desc", created_at.desc()),
        Index("ix_feedback_flagged_created", flagged_for_training, created_at.desc()),
        Index("ix_feedback_radiologist_created", radiologist_id, created_at.desc()),
    )
    
    def __repr__(self) -> str:
        return f"<Feedback(feedback_id={self.feedback_id}, request_id={self.request_id})>"


class ModelVersion(Base):
    """
    Model version registry
    Tracks deployed model versions
    """
    __tablename__ = "model_versions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Version information
    version = Column(String(20), unique=True, nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    model_path = Column(Text, nullable=False)
    
    # Training information
    training_dataset = Column(String(100), nullable=True)
    training_date = Column(DateTime, nullable=True)
    
    # Performance metrics (JSONB)
    metrics = Column(JSON, nullable=True)
    
    # Deployment status
    status = Column(
        String(20),
        default="development",
        nullable=False,
        index=True,
    )  # development, staging, production, deprecated
    
    # Timestamps
    deployed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ModelVersion(version={self.version}, status={self.status})>"


class AuditLog(Base):
    """
    Immutable audit log
    Records all significant events for compliance
    """
    __tablename__ = "audit_log"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Event information
    event_type = Column(String(50), nullable=False, index=True)
    event_data = Column(JSON, nullable=False)
    
    # User information
    user_id = Column(String(100), nullable=True, index=True)
    
    # Request tracking
    request_id = Column(String(50), nullable=True, index=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index("ix_audit_log_event_created", event_type, created_at.desc()),
        Index("ix_audit_log_user_created", user_id, created_at.desc()),
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(event_type={self.event_type}, created_at={self.created_at})>"


class CachedPrediction(Base):
    """
    Cached prediction results
    Optional table for persistence (Redis is primary cache)
    """
    __tablename__ = "cached_predictions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Cache key
    cache_key = Column(String(100), unique=True, nullable=False, index=True)
    
    # Cached data
    prediction_data = Column(JSON, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f"<CachedPrediction(cache_key={self.cache_key})>"
