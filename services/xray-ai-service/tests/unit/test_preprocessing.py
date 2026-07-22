"""
Unit tests for preprocessing service
"""

import numpy as np
import pytest
from PIL import Image

from src.services.preprocessing import PreprocessingService


class TestPreprocessingService:
    """Test preprocessing service"""
    
    @pytest.fixture
    def preprocessing_service(self):
        """Get preprocessing service instance"""
        return PreprocessingService()
    
    def test_initialization(self, preprocessing_service):
        """Test service initialization"""
        assert preprocessing_service.input_size == (224, 224)
        assert preprocessing_service.transform is not None
    
    @pytest.mark.asyncio
    async def test_process_png_image(self, preprocessing_service):
        """Test processing PNG image"""
        # Create test image
        img = Image.new('L', (512, 512), color=128)
        img_bytes = img.tobytes()
        
        # This would fail without actual image, but shows structure
        # In real tests, use actual test images
        pass
    
    def test_validate_image_quality_low_resolution(self, preprocessing_service):
        """Test image quality validation for low resolution"""
        small_image = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        
        # Should log warning for low resolution
        preprocessing_service._validate_image_quality(small_image)
    
    def test_validate_image_quality_low_contrast(self, preprocessing_service):
        """Test image quality validation for low contrast"""
        low_contrast_image = np.ones((512, 512), dtype=np.uint8) * 128
        
        # Should log warning for low contrast
        preprocessing_service._validate_image_quality(low_contrast_image)
    
    def test_to_tensor_shape(self, preprocessing_service):
        """Test tensor conversion output shape"""
        image = np.random.randint(0, 255, (224, 224), dtype=np.uint8)
        tensor = preprocessing_service._to_tensor(image)
        
        # Should be [1, 1, 224, 224]
        assert tensor.shape[0] == 1  # Batch size
        assert tensor.shape[1] == 1  # Channels
        assert tensor.shape[2] == 224  # Height
        assert tensor.shape[3] == 224  # Width
    
    def test_apply_clahe(self, preprocessing_service):
        """Test CLAHE enhancement"""
        image = np.random.randint(0, 255, (512, 512), dtype=np.uint8)
        enhanced = preprocessing_service.apply_clahe(image)
        
        assert enhanced.shape == image.shape
        assert enhanced.dtype == np.uint8
