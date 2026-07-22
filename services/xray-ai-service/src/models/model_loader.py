"""
Model loading and management
Handles model initialization, loading from registry, and caching
"""

import os
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.monitoring import model_loaded, model_memory_usage, model_version_info
from src.models.calibration import MultiDiseaseCalibration
from src.models.disease_heads import XRayDiseaseClassifier
from src.models.foundation import create_foundation_model

logger = get_logger(__name__)
settings = get_settings()


class ModelLoader:
    """
    Model loader with caching and version management
    """
    
    def __init__(self):
        """Initialize model loader"""
        self.model: Optional[XRayDiseaseClassifier] = None
        self.calibration: Optional[MultiDiseaseCalibration] = None
        self.device = torch.device(settings.device)
        self.model_version = settings.model_version
        
        logger.info(
            "Model loader initialized",
            device=str(self.device),
            model_version=self.model_version,
        )
    
    def load_model(
        self,
        model_path: Optional[Path] = None,
        force_reload: bool = False,
    ) -> XRayDiseaseClassifier:
        """
        Load model from disk or create new one
        
        Args:
            model_path: Path to model checkpoint (None for pretrained only)
            force_reload: Force reload even if already loaded
        
        Returns:
            Loaded model
        """
        if self.model is not None and not force_reload:
            logger.info("Model already loaded, returning cached instance")
            return self.model
        
        logger.info("Loading model", model_path=str(model_path))
        
        try:
            # Create foundation model
            foundation = create_foundation_model(
                model_name=settings.model_name,
                pretrained=True,
                freeze_backbone=False,
            )
            
            # Create classifier with disease heads
            model = XRayDiseaseClassifier(
                foundation_model=foundation,
                diseases=settings.diseases,
                hidden_dims=[512],  # Single hidden layer for disease heads
                dropout=0.3,
            )
            
            # Load fine-tuned weights if available
            if model_path and os.path.exists(model_path):
                logger.info("Loading fine-tuned weights", path=str(model_path))
                checkpoint = torch.load(model_path, map_location=self.device)
                
                if "model_state_dict" in checkpoint:
                    model.load_state_dict(checkpoint["model_state_dict"])
                    logger.info(
                        "Loaded checkpoint",
                        epoch=checkpoint.get("epoch"),
                        metrics=checkpoint.get("metrics"),
                    )
                else:
                    model.load_state_dict(checkpoint)
            
            # Move to device
            model = model.to(self.device)
            model.eval()
            
            self.model = model
            
            # Update metrics
            model_loaded.set(1)
            model_memory_usage.set(self._get_model_memory())
            model_version_info.info({
                "version": self.model_version,
                "name": settings.model_name,
                "device": str(self.device),
            })
            
            logger.info(
                "Model loaded successfully",
                num_params=sum(p.numel() for p in model.parameters()),
                memory_mb=self._get_model_memory() / (1024 * 1024),
            )
            
            return self.model
            
        except Exception as e:
            logger.error("Failed to load model", error=str(e), exc_info=True)
            model_loaded.set(0)
            raise
    
    def load_calibration(
        self,
        calibration_path: Optional[Path] = None,
    ) -> MultiDiseaseCalibration:
        """
        Load calibration parameters
        
        Args:
            calibration_path: Path to calibration file
        
        Returns:
            Calibration instance
        """
        if self.calibration is not None:
            return self.calibration
        
        try:
            if calibration_path and os.path.exists(calibration_path):
                logger.info("Loading calibration", path=str(calibration_path))
                self.calibration = MultiDiseaseCalibration.load(str(calibration_path))
            else:
                # Use default temperature scaling
                logger.info("Using default calibration")
                self.calibration = MultiDiseaseCalibration(
                    diseases=settings.diseases,
                    method=settings.calibration_method,
                    temperatures={disease: settings.temperature for disease in settings.diseases},
                )
            
            return self.calibration
            
        except Exception as e:
            logger.error("Failed to load calibration", error=str(e), exc_info=True)
            # Fallback to no calibration
            return None
    
    def get_model(self) -> XRayDiseaseClassifier:
        """
        Get loaded model (load if not already loaded)
        
        Returns:
            Model instance
        """
        if self.model is None:
            self.load_model()
        return self.model
    
    def get_calibration(self) -> Optional[MultiDiseaseCalibration]:
        """
        Get calibration instance
        
        Returns:
            Calibration instance or None
        """
        if self.calibration is None:
            self.load_calibration()
        return self.calibration
    
    def reload_model(self, model_path: Optional[Path] = None) -> XRayDiseaseClassifier:
        """
        Reload model (for hot-swapping new versions)
        
        Args:
            model_path: Path to new model checkpoint
        
        Returns:
            Reloaded model
        """
        logger.info("Reloading model", model_path=str(model_path))
        
        # Clear cache
        if self.model is not None:
            del self.model
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
        return self.load_model(model_path=model_path, force_reload=True)
    
    def _get_model_memory(self) -> int:
        """
        Get model memory usage in bytes
        
        Returns:
            Memory usage in bytes
        """
        if self.model is None:
            return 0
        
        total_bytes = 0
        for param in self.model.parameters():
            total_bytes += param.nelement() * param.element_size()
        
        # Also count buffers
        for buffer in self.model.buffers():
            total_bytes += buffer.nelement() * buffer.element_size()
        
        return total_bytes
    
    def export_onnx(
        self,
        output_path: Path,
        input_size: tuple = (1, 1, 224, 224),
    ) -> None:
        """
        Export model to ONNX format for optimized inference
        
        Args:
            output_path: Path to save ONNX model
            input_size: Input tensor size (B, C, H, W)
        """
        if self.model is None:
            raise ValueError("Model not loaded")
        
        logger.info("Exporting to ONNX", output_path=str(output_path))
        
        # Create dummy input
        dummy_input = torch.randn(*input_size, device=self.device)
        
        # Export
        torch.onnx.export(
            self.model,
            dummy_input,
            str(output_path),
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=["input"],
            output_names=list(settings.diseases),
            dynamic_axes={
                "input": {0: "batch_size"},
                **{disease: {0: "batch_size"} for disease in settings.diseases},
            },
        )
        
        logger.info("ONNX export complete", output_path=str(output_path))


# Global model loader instance
_model_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    """
    Get global model loader instance (singleton)
    
    Returns:
        ModelLoader instance
    """
    global _model_loader
    
    if _model_loader is None:
        _model_loader = ModelLoader()
    
    return _model_loader
