"""
Task-specific disease classification heads
Each disease has its own head with independent parameters
"""

from typing import Dict, List

import torch
import torch.nn as nn

from src.core.logging import get_logger

logger = get_logger(__name__)


class DiseaseHead(nn.Module):
    """
    Single disease classification head
    Binary classifier with optional intermediate layers
    """
    
    def __init__(
        self,
        input_dim: int,
        disease_name: str,
        hidden_dims: List[int] = None,
        dropout: float = 0.3,
    ):
        """
        Initialize disease head
        
        Args:
            input_dim: Input feature dimension from foundation model
            disease_name: Name of the disease
            hidden_dims: List of hidden layer dimensions (None for single layer)
            dropout: Dropout rate
        """
        super().__init__()
        
        self.disease_name = disease_name
        self.input_dim = input_dim
        
        layers = []
        
        if hidden_dims is None:
            # Simple single-layer classifier
            layers.append(nn.Linear(input_dim, 1))
        else:
            # Multi-layer classifier
            prev_dim = input_dim
            for hidden_dim in hidden_dims:
                layers.extend([
                    nn.Linear(prev_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ])
                prev_dim = hidden_dim
            
            # Final output layer
            layers.append(nn.Linear(prev_dim, 1))
        
        self.classifier = nn.Sequential(*layers)
        
        logger.debug(
            "Disease head initialized",
            disease=disease_name,
            input_dim=input_dim,
            hidden_dims=hidden_dims,
            num_params=sum(p.numel() for p in self.parameters()),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass
        
        Args:
            x: Input features [B, input_dim]
        
        Returns:
            Logits [B, 1]
        """
        return self.classifier(x)


class MultiDiseaseHead(nn.Module):
    """
    Multiple disease classification heads
    Each disease has its own independent head
    """
    
    def __init__(
        self,
        input_dim: int,
        diseases: List[str],
        hidden_dims: List[int] = None,
        dropout: float = 0.3,
    ):
        """
        Initialize multi-disease heads
        
        Args:
            input_dim: Input feature dimension
            diseases: List of disease names
            hidden_dims: Hidden layer dimensions (shared across all heads)
            dropout: Dropout rate
        """
        super().__init__()
        
        self.diseases = diseases
        self.input_dim = input_dim
        
        # Create individual heads for each disease
        self.heads = nn.ModuleDict({
            disease: DiseaseHead(
                input_dim=input_dim,
                disease_name=disease,
                hidden_dims=hidden_dims,
                dropout=dropout,
            )
            for disease in diseases
        })
        
        logger.info(
            "Multi-disease heads initialized",
            num_diseases=len(diseases),
            diseases=diseases,
            total_params=sum(p.numel() for p in self.parameters()),
        )
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass through all disease heads
        
        Args:
            x: Input features [B, input_dim]
        
        Returns:
            Dictionary of disease logits
        """
        outputs = {}
        for disease, head in self.heads.items():
            logits = head(x)
            outputs[disease] = logits
        
        return outputs
    
    def get_head(self, disease: str) -> DiseaseHead:
        """Get specific disease head"""
        return self.heads[disease]


class XRayDiseaseClassifier(nn.Module):
    """
    Complete X-Ray disease classifier
    Foundation model + disease heads
    """
    
    def __init__(
        self,
        foundation_model: nn.Module,
        diseases: List[str],
        hidden_dims: List[int] = None,
        dropout: float = 0.3,
    ):
        """
        Initialize complete classifier
        
        Args:
            foundation_model: Pre-trained foundation model
            diseases: List of diseases to classify
            hidden_dims: Hidden dimensions for disease heads
            dropout: Dropout rate
        """
        super().__init__()
        
        self.foundation = foundation_model
        self.diseases = diseases
        
        # Get feature dimension from foundation model
        feature_dim = foundation_model.feature_dim
        
        # Create disease heads
        self.disease_heads = MultiDiseaseHead(
            input_dim=feature_dim,
            diseases=diseases,
            hidden_dims=hidden_dims,
            dropout=dropout,
        )
        
        logger.info(
            "XRay disease classifier initialized",
            feature_dim=feature_dim,
            num_diseases=len(diseases),
            total_params=sum(p.numel() for p in self.parameters()),
            trainable_params=sum(p.numel() for p in self.parameters() if p.requires_grad),
        )
    
    def forward(
        self,
        x: torch.Tensor,
        return_features: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass
        
        Args:
            x: Input images [B, C, H, W]
            return_features: Whether to return intermediate features
        
        Returns:
            Dictionary with disease logits and optionally features
        """
        # Extract features from foundation model
        features = self.foundation(x)
        
        # Get disease predictions
        logits = self.disease_heads(features)
        
        # Apply sigmoid to get probabilities
        outputs = {
            disease: torch.sigmoid(logit)
            for disease, logit in logits.items()
        }
        
        if return_features:
            outputs["features"] = features
        
        return outputs
    
    def get_disease_head(self, disease: str) -> DiseaseHead:
        """Get specific disease head"""
        return self.disease_heads.get_head(disease)
    
    def freeze_foundation(self) -> None:
        """Freeze foundation model for head-only training"""
        logger.info("Freezing foundation model")
        for param in self.foundation.parameters():
            param.requires_grad = False
    
    def unfreeze_foundation(self) -> None:
        """Unfreeze foundation model for fine-tuning"""
        logger.info("Unfreezing foundation model")
        for param in self.foundation.parameters():
            param.requires_grad = True
    
    def get_trainable_params(self) -> List[torch.nn.Parameter]:
        """Get list of trainable parameters"""
        return [p for p in self.parameters() if p.requires_grad]


class EnsembleClassifier(nn.Module):
    """
    Ensemble of multiple classifiers (future feature)
    Useful for uncertainty estimation and improved performance
    """
    
    def __init__(
        self,
        classifiers: List[XRayDiseaseClassifier],
        ensemble_method: str = "mean",
    ):
        """
        Initialize ensemble
        
        Args:
            classifiers: List of individual classifiers
            ensemble_method: How to combine predictions (mean, weighted_mean, voting)
        """
        super().__init__()
        
        self.classifiers = nn.ModuleList(classifiers)
        self.ensemble_method = ensemble_method
        self.num_models = len(classifiers)
        
        if ensemble_method == "weighted_mean":
            # Learnable weights for each model
            self.weights = nn.Parameter(torch.ones(self.num_models) / self.num_models)
        
        logger.info(
            "Ensemble classifier initialized",
            num_models=self.num_models,
            method=ensemble_method,
        )
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass through ensemble
        
        Args:
            x: Input images [B, C, H, W]
        
        Returns:
            Aggregated predictions
        """
        # Get predictions from all models
        all_predictions = [model(x) for model in self.classifiers]
        
        # Extract diseases from first model
        diseases = list(all_predictions[0].keys())
        
        # Aggregate predictions
        ensemble_output = {}
        
        for disease in diseases:
            if disease == "features":
                continue
            
            # Stack predictions from all models
            preds = torch.stack([
                pred[disease] for pred in all_predictions
            ])  # [num_models, B, 1]
            
            if self.ensemble_method == "mean":
                ensemble_output[disease] = preds.mean(dim=0)
            elif self.ensemble_method == "weighted_mean":
                weights = torch.softmax(self.weights, dim=0)
                weighted_preds = preds * weights.view(-1, 1, 1)
                ensemble_output[disease] = weighted_preds.sum(dim=0)
            elif self.ensemble_method == "voting":
                # Binary voting (>0.5)
                votes = (preds > 0.5).float()
                ensemble_output[disease] = votes.mean(dim=0)
            else:
                raise ValueError(f"Unknown ensemble method: {self.ensemble_method}")
        
        return ensemble_output
    
    def get_uncertainty(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Get prediction uncertainty based on model disagreement
        
        Args:
            x: Input images
        
        Returns:
            Dictionary of uncertainties (standard deviation across models)
        """
        all_predictions = [model(x) for model in self.classifiers]
        diseases = list(all_predictions[0].keys())
        
        uncertainties = {}
        for disease in diseases:
            if disease == "features":
                continue
            
            preds = torch.stack([pred[disease] for pred in all_predictions])
            uncertainties[disease] = preds.std(dim=0)
        
        return uncertainties
