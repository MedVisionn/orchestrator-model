"""
Explainability service using Grad-CAM
Generates visual explanations for model predictions
"""

import base64
import io
import time
from typing import Dict, List, Optional

import cv2
import numpy as np
import torch
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.monitoring import gradcam_duration, gradcam_requests
from src.models.model_loader import get_model_loader
from src.schemas.responses import AttentionRegion, DiseaseExplanation, ExplainResponse

logger = get_logger(__name__)
settings = get_settings()


class ExplainabilityService:
    """
    Service for generating visual explanations using Grad-CAM
    """
    
    def __init__(self):
        """Initialize explainability service"""
        self.model_loader = get_model_loader()
        self.device = torch.device(settings.device)
        
        # Cache for storing recent predictions (simple in-memory cache)
        # In production, use Redis
        self._prediction_cache: Dict = {}
        
        logger.info("Explainability service initialized")
    
    async def explain(
        self,
        request_id: str,
        diseases: Optional[List[str]] = None,
        overlay_alpha: float = 0.4,
    ) -> ExplainResponse:
        """
        Generate Grad-CAM explanations
        
        Args:
            request_id: Original prediction request ID
            diseases: Specific diseases to explain (None for all positive predictions)
            overlay_alpha: Overlay transparency (0-1)
        
        Returns:
            ExplainResponse with heatmaps and attention regions
        
        Raises:
            ValueError: If request_id not found or invalid
        """
        start_time = time.time()
        
        logger.info(
            "Generating explanations",
            request_id=request_id,
            diseases=diseases,
        )
        
        # Get cached prediction data
        # TODO: Implement proper caching with Redis
        cached_data = self._prediction_cache.get(request_id)
        
        if cached_data is None:
            raise ValueError(f"Request ID {request_id} not found. Predictions may have expired.")
        
        input_tensor = cached_data["input_tensor"]
        original_image = cached_data["original_image"]
        predictions = cached_data["predictions"]
        
        # Determine which diseases to explain
        if diseases is None:
            # Explain all positive predictions
            diseases_to_explain = [
                disease for disease, pred in predictions.items()
                if pred.get("label") == "positive"
            ]
        else:
            diseases_to_explain = diseases
        
        if not diseases_to_explain:
            diseases_to_explain = list(predictions.keys())[:3]  # Default to first 3
        
        # Generate explanations for each disease
        explanations = {}
        
        for disease in diseases_to_explain:
            try:
                explanation = self._generate_gradcam(
                    input_tensor=input_tensor,
                    original_image=original_image,
                    disease=disease,
                    overlay_alpha=overlay_alpha,
                )
                explanations[disease] = explanation
            except Exception as e:
                logger.error(
                    "Failed to generate explanation",
                    disease=disease,
                    error=str(e),
                )
                # Continue with other diseases
                continue
        
        duration = (time.time() - start_time) * 1000
        
        # Update metrics
        gradcam_requests.inc()
        gradcam_duration.observe(duration / 1000)
        
        logger.info(
            "Explanations generated",
            request_id=request_id,
            num_explanations=len(explanations),
            duration_ms=duration,
        )
        
        return ExplainResponse(
            request_id=request_id,
            explanations=explanations,
            generation_time_ms=duration,
        )
    
    def _generate_gradcam(
        self,
        input_tensor: torch.Tensor,
        original_image: np.ndarray,
        disease: str,
        overlay_alpha: float = 0.4,
    ) -> DiseaseExplanation:
        """
        Generate Grad-CAM for a specific disease
        
        Args:
            input_tensor: Input tensor [1, 1, H, W]
            original_image: Original image for overlay
            disease: Disease name
            overlay_alpha: Overlay transparency
        
        Returns:
            DiseaseExplanation with heatmaps and regions
        """
        model = self.model_loader.get_model()
        model.eval()
        
        # Get disease head
        disease_head = model.get_disease_head(disease)
        
        # Define target layer for Grad-CAM
        # For DenseNet, use the last dense block
        target_layers = [model.foundation.backbone.features.denseblock4]
        
        # Create Grad-CAM object
        cam = GradCAM(
            model=model.foundation.backbone,
            target_layers=target_layers,
            use_cuda=self.device.type == "cuda",
        )
        
        # Generate CAM
        grayscale_cam = cam(
            input_tensor=input_tensor,
            targets=None,  # Use predicted class
        )
        
        # Get first image from batch
        grayscale_cam = grayscale_cam[0, :]
        
        # Normalize original image for visualization
        if original_image.max() > 1.0:
            viz_image = original_image.astype(np.float32) / 255.0
        else:
            viz_image = original_image.astype(np.float32)
        
        # Convert grayscale to RGB for overlay
        if len(viz_image.shape) == 2:
            viz_image = np.stack([viz_image] * 3, axis=-1)
        
        # Resize CAM to match original image size
        cam_resized = cv2.resize(grayscale_cam, (viz_image.shape[1], viz_image.shape[0]))
        
        # Create overlay
        overlay = show_cam_on_image(viz_image, cam_resized, use_rgb=True)
        
        # Convert to base64
        heatmap_base64 = self._array_to_base64(cam_resized)
        overlay_base64 = self._array_to_base64(overlay)
        
        # Detect attention regions
        attention_regions = self._detect_attention_regions(cam_resized)
        
        return DiseaseExplanation(
            heatmap_base64=heatmap_base64,
            overlay_base64=overlay_base64,
            attention_regions=attention_regions,
        )
    
    def _array_to_base64(self, array: np.ndarray) -> str:
        """
        Convert numpy array to base64 encoded PNG
        
        Args:
            array: Numpy array (grayscale or RGB)
        
        Returns:
            Base64 encoded string
        """
        # Normalize to 0-255
        if array.max() <= 1.0:
            array = (array * 255).astype(np.uint8)
        else:
            array = array.astype(np.uint8)
        
        # Convert to PIL Image
        if len(array.shape) == 2:
            # Grayscale
            image = Image.fromarray(array, mode='L')
        else:
            # RGB
            image = Image.fromarray(array, mode='RGB')
        
        # Save to bytes
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Encode to base64
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    def _detect_attention_regions(
        self,
        heatmap: np.ndarray,
        threshold: float = 0.7,
    ) -> List[AttentionRegion]:
        """
        Detect high-attention regions in heatmap
        
        Args:
            heatmap: Attention heatmap [H, W]
            threshold: Intensity threshold for region detection
        
        Returns:
            List of AttentionRegion objects
        """
        # Threshold heatmap
        binary_mask = (heatmap > threshold).astype(np.uint8)
        
        # Find contours
        contours, _ = cv2.findContours(
            binary_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        
        regions = []
        
        for contour in contours:
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calculate average intensity in region
            region_mask = np.zeros_like(heatmap, dtype=np.uint8)
            cv2.drawContours(region_mask, [contour], -1, 1, -1)
            intensity = float(np.mean(heatmap[region_mask == 1]))
            
            # Only include significant regions
            if w * h > 100:  # Minimum area
                region = AttentionRegion(
                    x=int(x),
                    y=int(y),
                    width=int(w),
                    height=int(h),
                    intensity=intensity,
                    anatomical_region=self._map_to_anatomy(x, y, w, h, heatmap.shape),
                )
                regions.append(region)
        
        # Sort by intensity
        regions.sort(key=lambda r: r.intensity, reverse=True)
        
        # Return top 5 regions
        return regions[:5]
    
    def _map_to_anatomy(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        image_shape: tuple,
    ) -> Optional[str]:
        """
        Map image coordinates to anatomical regions (simplified)
        
        Args:
            x, y, w, h: Bounding box
            image_shape: Image dimensions
        
        Returns:
            Anatomical region name or None
        """
        img_h, img_w = image_shape
        
        # Calculate center
        cx = x + w // 2
        cy = y + h // 2
        
        # Divide into regions (simplified)
        # Upper: 0-33%, Middle: 33-66%, Lower: 66-100%
        # Left, Center, Right
        
        if cy < img_h * 0.33:
            vertical = "upper"
        elif cy < img_h * 0.66:
            vertical = "middle"
        else:
            vertical = "lower"
        
        if cx < img_w * 0.33:
            horizontal = "left"
        elif cx < img_w * 0.66:
            horizontal = "central"
        else:
            horizontal = "right"
        
        return f"{horizontal} {vertical} lung field"
    
    def cache_prediction(
        self,
        request_id: str,
        input_tensor: torch.Tensor,
        original_image: np.ndarray,
        predictions: Dict,
    ) -> None:
        """
        Cache prediction data for later explanation
        
        Args:
            request_id: Request identifier
            input_tensor: Input tensor
            original_image: Original image
            predictions: Prediction results
        """
        self._prediction_cache[request_id] = {
            "input_tensor": input_tensor,
            "original_image": original_image,
            "predictions": predictions,
            "timestamp": time.time(),
        }
        
        # Simple cache cleanup (keep last 1000)
        if len(self._prediction_cache) > 1000:
            # Remove oldest
            oldest_key = min(
                self._prediction_cache.keys(),
                key=lambda k: self._prediction_cache[k]["timestamp"],
            )
            del self._prediction_cache[oldest_key]
