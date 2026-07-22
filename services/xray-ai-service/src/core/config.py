"""
Configuration management using Pydantic Settings
Supports environment variables and YAML config files
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application Info
    app_name: str = "xray-ai-service"
    version: str = "1.0.0"
    environment: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or console")
    
    # CORS
    cors_origins: List[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )
    
    # Model Configuration
    model_name: str = Field(
        default="densenet121-res224-all",
        description="TorchXRayVision model name"
    )
    model_version: str = Field(default="1.0.0", description="Model version")
    model_path: Path = Field(
        default=Path("./models"),
        description="Path to model artifacts"
    )
    device: str = Field(
        default="cpu",
        description="Inference device: cuda, cuda:0, cpu"
    )
    use_onnx: bool = Field(default=False, description="Use ONNX runtime for inference")
    
    # Inference Configuration
    input_size: tuple = Field(default=(224, 224), description="Model input size (H, W)")
    batch_size: int = Field(default=1, description="Inference batch size")
    inference_timeout: int = Field(default=30, description="Inference timeout in seconds")
    max_file_size_mb: int = Field(default=10, description="Max upload file size in MB")
    
    # Disease Configuration
    diseases: List[str] = Field(
        default=[
            "pneumonia",
            "tuberculosis",
            "cardiomegaly",
            "pleural_effusion",
            "edema",
            "fracture",
        ],
        description="Supported diseases"
    )
    
    # Calibration
    calibration_method: str = Field(
        default="temperature_scaling",
        description="Calibration method: temperature_scaling, platt_scaling, isotonic"
    )
    temperature: float = Field(default=1.5, description="Temperature for scaling")
    
    # Caching
    enable_cache: bool = Field(default=True, description="Enable Redis caching")
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    redis_max_connections: int = Field(default=50, description="Redis connection pool size")
    
    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/medscan",
        description="PostgreSQL connection URL"
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=10, description="Max overflow connections")
    
    # MLflow Model Registry
    mlflow_tracking_uri: str = Field(
        default="http://localhost:5000",
        description="MLflow tracking server URI"
    )
    mlflow_experiment_name: str = Field(
        default="xray-inference",
        description="MLflow experiment name"
    )
    enable_mlflow: bool = Field(default=False, description="Enable MLflow tracking")
    
    # Monitoring
    enable_prometheus: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Prometheus metrics port")
    
    # Explainability
    enable_gradcam: bool = Field(default=True, description="Enable Grad-CAM")
    gradcam_layer: str = Field(
        default="features.denseblock4",
        description="Target layer for Grad-CAM"
    )
    
    # Rate Limiting
    enable_rate_limit: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=100, description="Requests per window")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")
    
    # Security
    secret_key: str = Field(
        default="change-me-in-production-use-secrets-manager",
        description="Secret key for JWT and encryption"
    )
    enable_auth: bool = Field(default=False, description="Enable JWT authentication")
    
    # Feature Flags
    enable_report_generation: bool = Field(default=True, description="Enable clinical report generation")
    enable_feedback: bool = Field(default=True, description="Enable feedback endpoint")
    log_predictions: bool = Field(default=True, description="Log predictions for audit")
    
    # File Paths
    config_path: Path = Field(
        default=Path("./config"),
        description="Configuration files directory"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value"""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Validate device value"""
        import torch
        
        if v.startswith("cuda"):
            if not torch.cuda.is_available():
                raise ValueError("CUDA device requested but CUDA is not available")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v_upper
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development"
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes"""
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def model_full_path(self) -> Path:
        """Get full path to model directory"""
        return self.model_path / self.model_version
    
    def get_disease_config(self, disease: str) -> dict:
        """
        Get disease-specific configuration
        In production, this would load from diseases.yaml
        """
        # Default thresholds based on clinical validation
        thresholds = {
            "pneumonia": 0.5,
            "tuberculosis": 0.3,  # Lower threshold for high-risk disease
            "cardiomegaly": 0.5,
            "pleural_effusion": 0.4,
            "edema": 0.5,
            "fracture": 0.3,
        }
        
        clinical_significance = {
            "pneumonia": "high",
            "tuberculosis": "critical",
            "cardiomegaly": "high",
            "pleural_effusion": "medium",
            "edema": "medium",
            "fracture": "high",
        }
        
        return {
            "name": disease,
            "threshold": thresholds.get(disease, 0.5),
            "clinical_significance": clinical_significance.get(disease, "medium"),
        }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Use lru_cache to ensure singleton pattern
    """
    return Settings()


# Export settings instance
settings = get_settings()
