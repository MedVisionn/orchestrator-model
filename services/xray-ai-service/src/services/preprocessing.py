"""
DICOM and image preprocessing service
Handles DICOM parsing, image normalization, and augmentation
"""

import io
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np
import pydicom
import torch
from PIL import Image
from torchvision import transforms

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.monitoring import image_quality_warnings, invalid_inputs, preprocessing_duration
from src.schemas.responses import ImageMetadata

logger = get_logger(__name__)
settings = get_settings()


class PreprocessingService:
    """
    Service for preprocessing medical images
    Handles DICOM, PNG, JPEG formats
    """
    
    def __init__(self):
        """Initialize preprocessing service"""
        self.input_size = settings.input_size
        
        # TorchXRayVision preprocessing pipeline
        self.transform = transforms.Compose([
            transforms.Resize(self.input_size),
            transforms.ToTensor(),
            # TorchXRayVision models expect single channel, normalized to [0, 1]
        ])
        
        logger.info(
            "Preprocessing service initialized",
            input_size=self.input_size,
        )
    
    def process_file(
        self,
        file_content: bytes,
        file_type: str,
    ) -> Tuple[torch.Tensor, ImageMetadata]:
        """
        Process uploaded file
        
        Args:
            file_content: Raw file bytes
            file_type: File extension or MIME type
        
        Returns:
            Tuple of (preprocessed tensor, metadata)
        """
        import time
        start_time = time.time()
        
        try:
            # Determine file type and parse
            if file_type in ['dcm', 'dicom', 'application/dicom']:
                image, metadata = self._process_dicom(file_content)
            elif file_type in ['png', 'jpg', 'jpeg', 'image/png', 'image/jpeg']:
                image, metadata = self._process_image(file_content)
            else:
                invalid_inputs.labels(reason="unsupported_format").inc()
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # Validate image quality
            self._validate_image_quality(image)
            
            # Convert to tensor
            tensor = self._to_tensor(image)
            
            # Record timing
            duration = time.time() - start_time
            preprocessing_duration.observe(duration)
            
            logger.debug(
                "File processed",
                file_type=file_type,
                output_shape=tensor.shape,
                duration_ms=duration * 1000,
            )
            
            return tensor, metadata
            
        except Exception as e:
            logger.error("Preprocessing failed", error=str(e), exc_info=True)
            invalid_inputs.labels(reason="processing_error").inc()
            raise
    
    def _process_dicom(self, content: bytes) -> Tuple[np.ndarray, ImageMetadata]:
        """
        Process DICOM file
        
        Args:
            content: DICOM file bytes
        
        Returns:
            Tuple of (image array, metadata)
        """
        try:
            # Parse DICOM
            dcm = pydicom.dcmread(io.BytesIO(content))
            
            # Extract pixel data
            image = dcm.pixel_array.astype(np.float32)
            
            # Handle photometric interpretation
            if hasattr(dcm, 'PhotometricInterpretation'):
                if dcm.PhotometricInterpretation == "MONOCHROME1":
                    # Invert: 0 is white, max is black
                    image = image.max() - image
            
            # Apply VOI LUT (Value of Interest Look-Up Table)
            if hasattr(dcm, 'WindowCenter') and hasattr(dcm, 'WindowWidth'):
                center = float(dcm.WindowCenter) if isinstance(dcm.WindowCenter, (int, float)) else float(dcm.WindowCenter[0])
                width = float(dcm.WindowWidth) if isinstance(dcm.WindowWidth, (int, float)) else float(dcm.WindowWidth[0])
                
                lower = center - width / 2
                upper = center + width / 2
                image = np.clip(image, lower, upper)
            
            # Normalize to [0, 255]
            image = ((image - image.min()) / (image.max() - image.min()) * 255).astype(np.uint8)
            
            # Extract metadata
            metadata = ImageMetadata(
                width=image.shape[1],
                height=image.shape[0],
                modality=getattr(dcm, 'Modality', None),
                view_position=getattr(dcm, 'ViewPosition', None),
                manufacturer=getattr(dcm, 'Manufacturer', None),
                study_date=getattr(dcm, 'StudyDate', None),
                series_description=getattr(dcm, 'SeriesDescription', None),
            )
            
            logger.debug(
                "DICOM processed",
                shape=image.shape,
                modality=metadata.modality,
                view_position=metadata.view_position,
            )
            
            return image, metadata
            
        except Exception as e:
            logger.error("DICOM processing failed", error=str(e), exc_info=True)
            invalid_inputs.labels(reason="dicom_parse_error").inc()
            raise ValueError(f"Invalid DICOM file: {str(e)}")
    
    def _process_image(self, content: bytes) -> Tuple[np.ndarray, ImageMetadata]:
        """
        Process standard image file (PNG, JPEG)
        
        Args:
            content: Image file bytes
        
        Returns:
            Tuple of (image array, metadata)
        """
        try:
            # Load image
            image = Image.open(io.BytesIO(content))
            
            # Convert to grayscale if RGB
            if image.mode == 'RGB':
                image = image.convert('L')
            elif image.mode == 'RGBA':
                # Convert RGBA to RGB first, then to grayscale
                image = image.convert('RGB').convert('L')
            
            # Convert to numpy array
            image_array = np.array(image, dtype=np.uint8)
            
            # Extract metadata
            metadata = ImageMetadata(
                width=image.width,
                height=image.height,
                modality="DX",  # Assume digital X-ray
                view_position=None,
                manufacturer=None,
                study_date=None,
                series_description=None,
            )
            
            logger.debug("Image processed", shape=image_array.shape)
            
            return image_array, metadata
            
        except Exception as e:
            logger.error("Image processing failed", error=str(e), exc_info=True)
            invalid_inputs.labels(reason="image_parse_error").inc()
            raise ValueError(f"Invalid image file: {str(e)}")
    
    def _validate_image_quality(self, image: np.ndarray) -> None:
        """
        Validate image quality and log warnings
        
        Args:
            image: Image array
        """
        # Check size
        if image.shape[0] < 224 or image.shape[1] < 224:
            image_quality_warnings.labels(warning_type="low_resolution").inc()
            logger.warning(
                "Low resolution image",
                shape=image.shape,
                min_recommended=(224, 224),
            )
        
        # Check dynamic range
        if image.max() - image.min() < 50:
            image_quality_warnings.labels(warning_type="low_contrast").inc()
            logger.warning("Low contrast image", dynamic_range=int(image.max() - image.min()))
        
        # Check for excessive noise (simple heuristic)
        if image.std() > 100:
            image_quality_warnings.labels(warning_type="high_noise").inc()
            logger.warning("Potentially noisy image", std=float(image.std()))
    
    def _to_tensor(self, image: np.ndarray) -> torch.Tensor:
        """
        Convert image to tensor
        
        Args:
            image: Image array [H, W]
        
        Returns:
            Tensor [1, 1, H, W] (batch_size=1, channels=1)
        """
        # Convert to PIL Image for transforms
        if image.dtype != np.uint8:
            image = ((image - image.min()) / (image.max() - image.min()) * 255).astype(np.uint8)
        
        pil_image = Image.fromarray(image, mode='L')
        
        # Apply transforms
        tensor = self.transform(pil_image)
        
        # Ensure single channel
        if tensor.shape[0] == 3:
            tensor = tensor.mean(dim=0, keepdim=True)
        elif tensor.shape[0] == 1:
            pass
        else:
            tensor = tensor.unsqueeze(0)
        
        # Add batch dimension
        tensor = tensor.unsqueeze(0)  # [1, 1, H, W]
        
        # Normalize for TorchXRayVision (expects [0, 1])
        if tensor.max() > 1.0:
            tensor = tensor / 255.0
        
        return tensor
    
    def preprocess_for_gradcam(
        self,
        tensor: torch.Tensor,
        original_image: np.ndarray,
    ) -> Tuple[torch.Tensor, np.ndarray]:
        """
        Preprocess for Grad-CAM visualization
        
        Args:
            tensor: Preprocessed tensor
            original_image: Original image array for overlay
        
        Returns:
            Tuple of (tensor for model, resized original for overlay)
        """
        # Resize original image to match model input
        resized_original = cv2.resize(
            original_image,
            self.input_size,
            interpolation=cv2.INTER_LINEAR
        )
        
        return tensor, resized_original
    
    def apply_clahe(self, image: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
        """
        Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        Improves image quality for better model performance
        
        Args:
            image: Input image
            clip_limit: CLAHE clip limit
        
        Returns:
            Enhanced image
        """
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        return clahe.apply(image)
    
    def augment(
        self,
        image: np.ndarray,
        rotation: float = 0,
        horizontal_flip: bool = False,
        brightness: float = 1.0,
    ) -> np.ndarray:
        """
        Apply data augmentation (for training pipeline)
        
        Args:
            image: Input image
            rotation: Rotation angle in degrees
            horizontal_flip: Whether to flip horizontally
            brightness: Brightness adjustment factor
        
        Returns:
            Augmented image
        """
        # Rotation
        if rotation != 0:
            center = (image.shape[1] // 2, image.shape[0] // 2)
            matrix = cv2.getRotationMatrix2D(center, rotation, 1.0)
            image = cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]))
        
        # Horizontal flip
        if horizontal_flip:
            image = cv2.flip(image, 1)
        
        # Brightness
        if brightness != 1.0:
            image = np.clip(image * brightness, 0, 255).astype(np.uint8)
        
        return image


def create_preprocessing_service() -> PreprocessingService:
    """
    Factory function to create preprocessing service
    
    Returns:
        PreprocessingService instance
    """
    return PreprocessingService()
