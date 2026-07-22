"""
Medical Foundation Model using TorchXRayVision
Pre-trained on CheXpert, MIMIC-CXR, NIH ChestX-ray datasets
"""

from typing import Tuple

import torch
import torch.nn as nn
import torchxrayvision as xrv

from src.core.logging import get_logger

logger = get_logger(__name__)


class MedicalFoundationModel(nn.Module):
    """
    Medical foundation model for chest X-ray analysis
    Uses TorchXRayVision DenseNet-121 pretrained on multiple datasets
    """
    
    def __init__(
        self,
        model_name: str = "densenet121-res224-all",
        pretrained: bool = True,
        freeze_backbone: bool = False,
    ):
        """
        Initialize foundation model
        
        Args:
            model_name: TorchXRayVision model name
            pretrained: Load pretrained weights
            freeze_backbone: Freeze backbone weights (for fine-tuning)
        """
        super().__init__()
        
        logger.info(
            "Initializing medical foundation model",
            model_name=model_name,
            pretrained=pretrained,
            freeze_backbone=freeze_backbone,
        )
        
        # Load TorchXRayVision model
        if model_name == "densenet121-res224-all":
            self.backbone = xrv.models.DenseNet(weights="densenet121-res224-all")
        elif model_name == "densenet121-res224-mimic_ch":
            self.backbone = xrv.models.DenseNet(weights="densenet121-res224-mimic_ch")
        elif model_name == "densenet121-res224-chex":
            self.backbone = xrv.models.DenseNet(weights="densenet121-res224-chex")
        else:
            raise ValueError(f"Unsupported model: {model_name}")
        
        # Get feature dimension
        self.feature_dim = self._get_feature_dim()
        
        # Freeze backbone if requested
        if freeze_backbone:
            self._freeze_backbone()
        
        logger.info(
            "Foundation model initialized",
            feature_dim=self.feature_dim,
            num_params=sum(p.numel() for p in self.parameters()),
            trainable_params=sum(p.numel() for p in self.parameters() if p.requires_grad),
        )
    
    def _get_feature_dim(self) -> int:
        """Get feature dimension from backbone"""
        # For DenseNet-121, feature dim is 1024
        return 1024
    
    def _freeze_backbone(self) -> None:
        """Freeze backbone parameters"""
        logger.info("Freezing backbone parameters")
        for param in self.backbone.parameters():
            param.requires_grad = False
    
    def unfreeze_backbone(self) -> None:
        """Unfreeze backbone parameters for fine-tuning"""
        logger.info("Unfreezing backbone parameters")
        for param in self.backbone.parameters():
            param.requires_grad = True
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through foundation model
        
        Args:
            x: Input tensor [B, C, H, W]
        
        Returns:
            Feature embeddings [B, feature_dim]
        """
        # TorchXRayVision models expect single channel input
        if x.shape[1] == 3:
            # Convert RGB to grayscale if needed
            x = x.mean(dim=1, keepdim=True)
        
        # Get features from backbone
        # For DenseNet, we want the features before the classifier
        features = self.backbone.features(x)
        
        # Global average pooling
        features = torch.nn.functional.adaptive_avg_pool2d(features, (1, 1))
        features = torch.flatten(features, 1)
        
        return features
    
    def get_feature_extractor(self) -> nn.Module:
        """
        Get feature extractor for Grad-CAM
        
        Returns:
            Feature extraction module
        """
        return self.backbone.features


class MultiModalFoundation(nn.Module):
    """
    Multi-modal foundation model (future feature)
    Supports both image and clinical text
    """
    
    def __init__(
        self,
        image_model: str = "densenet121-res224-all",
        text_model: str = "bert-base-uncased",
        fusion_method: str = "concatenate",
    ):
        """
        Initialize multi-modal foundation model
        
        Args:
            image_model: Image backbone model name
            text_model: Text encoder model name
            fusion_method: How to fuse image and text features
        """
        super().__init__()
        
        # Image encoder
        self.image_encoder = MedicalFoundationModel(image_model)
        
        # Text encoder (placeholder - would use BERT/BioClinicalBERT)
        self.text_encoder = None  # Future implementation
        
        # Fusion layer
        self.fusion_method = fusion_method
        
        logger.info("Multi-modal foundation model initialized")
    
    def forward(
        self,
        image: torch.Tensor,
        text: torch.Tensor = None,
    ) -> torch.Tensor:
        """
        Forward pass with multi-modal inputs
        
        Args:
            image: Image tensor [B, C, H, W]
            text: Text tensor [B, seq_len] (optional)
        
        Returns:
            Fused features
        """
        # Get image features
        image_features = self.image_encoder(image)
        
        # If no text provided, return image features only
        if text is None or self.text_encoder is None:
            return image_features
        
        # Get text features
        text_features = self.text_encoder(text)
        
        # Fuse features
        if self.fusion_method == "concatenate":
            return torch.cat([image_features, text_features], dim=1)
        elif self.fusion_method == "add":
            return image_features + text_features
        elif self.fusion_method == "multiply":
            return image_features * text_features
        else:
            raise ValueError(f"Unknown fusion method: {self.fusion_method}")


def create_foundation_model(
    model_name: str = "densenet121-res224-all",
    pretrained: bool = True,
    freeze_backbone: bool = False,
) -> MedicalFoundationModel:
    """
    Factory function to create foundation model
    
    Args:
        model_name: Model name
        pretrained: Load pretrained weights
        freeze_backbone: Freeze backbone weights
    
    Returns:
        Foundation model instance
    """
    return MedicalFoundationModel(
        model_name=model_name,
        pretrained=pretrained,
        freeze_backbone=freeze_backbone,
    )
