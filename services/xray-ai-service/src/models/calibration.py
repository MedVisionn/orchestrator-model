"""
Confidence calibration for medical predictions
Ensures predicted probabilities reflect true likelihood
"""

from typing import Dict, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from src.core.logging import get_logger

logger = get_logger(__name__)


class TemperatureScaling(nn.Module):
    """
    Temperature scaling calibration
    Divides logits by learned temperature parameter
    
    Reference: "On Calibration of Modern Neural Networks" (Guo et al., 2017)
    """
    
    def __init__(self, temperature: float = 1.5):
        """
        Initialize temperature scaling
        
        Args:
            temperature: Initial temperature value (>1 smooths, <1 sharpens)
        """
        super().__init__()
        
        self.temperature = nn.Parameter(torch.tensor(temperature))
        
        logger.info("Temperature scaling initialized", temperature=temperature)
    
    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        """
        Apply temperature scaling
        
        Args:
            logits: Model logits [B, ...]
        
        Returns:
            Scaled probabilities
        """
        scaled_logits = logits / self.temperature
        return torch.sigmoid(scaled_logits)
    
    def fit(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        lr: float = 0.01,
        max_iter: int = 50,
    ) -> float:
        """
        Fit temperature on validation set
        
        Args:
            logits: Validation logits
            labels: True labels
            lr: Learning rate
            max_iter: Maximum iterations
        
        Returns:
            Final NLL loss
        """
        optimizer = torch.optim.LBFGS([self.temperature], lr=lr, max_iter=max_iter)
        
        def eval():
            optimizer.zero_grad()
            loss = nn.functional.binary_cross_entropy_with_logits(
                logits / self.temperature,
                labels
            )
            loss.backward()
            return loss
        
        optimizer.step(eval)
        
        final_loss = eval().item()
        
        logger.info(
            "Temperature fitted",
            temperature=self.temperature.item(),
            final_loss=final_loss,
        )
        
        return final_loss


class PlattScaling:
    """
    Platt scaling calibration
    Fits logistic regression on validation set
    
    Reference: "Probabilistic Outputs for Support Vector Machines" (Platt, 1999)
    """
    
    def __init__(self):
        """Initialize Platt scaling"""
        self.model = LogisticRegression()
        logger.info("Platt scaling initialized")
    
    def fit(self, logits: np.ndarray, labels: np.ndarray) -> None:
        """
        Fit Platt scaling
        
        Args:
            logits: Validation logits
            labels: True labels
        """
        self.model.fit(logits.reshape(-1, 1), labels)
        
        logger.info(
            "Platt scaling fitted",
            coef=self.model.coef_[0][0],
            intercept=self.model.intercept_[0],
        )
    
    def predict_proba(self, logits: np.ndarray) -> np.ndarray:
        """
        Get calibrated probabilities
        
        Args:
            logits: Model logits
        
        Returns:
            Calibrated probabilities
        """
        return self.model.predict_proba(logits.reshape(-1, 1))[:, 1]


class IsotonicCalibration:
    """
    Isotonic regression calibration
    Non-parametric calibration method
    
    Reference: "Predicting Good Probabilities With Supervised Learning" (Niculescu-Mizil & Caruana, 2005)
    """
    
    def __init__(self):
        """Initialize isotonic calibration"""
        self.model = IsotonicRegression(out_of_bounds='clip')
        logger.info("Isotonic calibration initialized")
    
    def fit(self, probs: np.ndarray, labels: np.ndarray) -> None:
        """
        Fit isotonic regression
        
        Args:
            probs: Validation probabilities
            labels: True labels
        """
        self.model.fit(probs, labels)
        logger.info("Isotonic calibration fitted")
    
    def predict(self, probs: np.ndarray) -> np.ndarray:
        """
        Get calibrated probabilities
        
        Args:
            probs: Model probabilities
        
        Returns:
            Calibrated probabilities
        """
        return self.model.predict(probs)


class MultiDiseaseCalibration:
    """
    Calibration for multiple diseases
    Each disease has independent calibration
    """
    
    def __init__(
        self,
        diseases: list,
        method: str = "temperature_scaling",
        temperatures: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize multi-disease calibration
        
        Args:
            diseases: List of disease names
            method: Calibration method (temperature_scaling, platt_scaling, isotonic)
            temperatures: Pre-computed temperatures for each disease
        """
        self.diseases = diseases
        self.method = method
        self.calibrators = {}
        
        if method == "temperature_scaling":
            for disease in diseases:
                temp = temperatures.get(disease, 1.5) if temperatures else 1.5
                self.calibrators[disease] = TemperatureScaling(temperature=temp)
        elif method == "platt_scaling":
            for disease in diseases:
                self.calibrators[disease] = PlattScaling()
        elif method == "isotonic":
            for disease in diseases:
                self.calibrators[disease] = IsotonicCalibration()
        else:
            raise ValueError(f"Unknown calibration method: {method}")
        
        logger.info(
            "Multi-disease calibration initialized",
            num_diseases=len(diseases),
            method=method,
        )
    
    def calibrate(
        self,
        predictions: Dict[str, torch.Tensor],
        return_numpy: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Apply calibration to predictions
        
        Args:
            predictions: Dictionary of disease predictions
            return_numpy: Return numpy arrays instead of tensors
        
        Returns:
            Calibrated predictions
        """
        calibrated = {}
        
        for disease, pred in predictions.items():
            if disease not in self.calibrators:
                # No calibrator for this disease, return as-is
                calibrated[disease] = pred
                continue
            
            calibrator = self.calibrators[disease]
            
            if self.method == "temperature_scaling":
                # Temperature scaling works with tensors
                # Convert sigmoid output back to logits
                eps = 1e-7
                logits = torch.log(pred / (1 - pred + eps) + eps)
                calibrated_pred = calibrator(logits)
            else:
                # Other methods work with numpy
                pred_np = pred.detach().cpu().numpy()
                
                if self.method == "platt_scaling":
                    # Convert probs back to logits for Platt scaling
                    logits_np = np.log(pred_np / (1 - pred_np + 1e-7) + 1e-7)
                    calibrated_np = calibrator.predict_proba(logits_np)
                else:  # isotonic
                    calibrated_np = calibrator.predict(pred_np)
                
                calibrated_pred = torch.tensor(
                    calibrated_np,
                    dtype=pred.dtype,
                    device=pred.device
                )
            
            calibrated[disease] = calibrated_pred
        
        if return_numpy:
            calibrated = {
                k: v.detach().cpu().numpy() if isinstance(v, torch.Tensor) else v
                for k, v in calibrated.items()
            }
        
        return calibrated
    
    def save(self, path: str) -> None:
        """Save calibration parameters"""
        import pickle
        
        with open(path, 'wb') as f:
            pickle.dump({
                'method': self.method,
                'diseases': self.diseases,
                'calibrators': self.calibrators,
            }, f)
        
        logger.info("Calibration saved", path=path)
    
    @classmethod
    def load(cls, path: str) -> 'MultiDiseaseCalibration':
        """Load calibration parameters"""
        import pickle
        
        with open(path, 'rb') as f:
            data = pickle.load(f)
        
        calibration = cls(
            diseases=data['diseases'],
            method=data['method'],
        )
        calibration.calibrators = data['calibrators']
        
        logger.info("Calibration loaded", path=path)
        
        return calibration


def compute_calibration_metrics(
    predictions: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 10,
) -> Dict[str, float]:
    """
    Compute calibration metrics
    
    Args:
        predictions: Predicted probabilities [N]
        labels: True labels [N]
        n_bins: Number of bins for calibration curve
    
    Returns:
        Dictionary with ECE, MCE, and Brier score
    """
    # Sort predictions and labels
    sorted_indices = np.argsort(predictions)
    sorted_preds = predictions[sorted_indices]
    sorted_labels = labels[sorted_indices]
    
    # Create bins
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(sorted_preds, bins) - 1
    
    # Compute Expected Calibration Error (ECE)
    ece = 0.0
    mce = 0.0  # Maximum Calibration Error
    
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_acc = sorted_labels[mask].mean()
            bin_conf = sorted_preds[mask].mean()
            bin_size = mask.sum()
            
            error = abs(bin_acc - bin_conf)
            ece += error * (bin_size / len(predictions))
            mce = max(mce, error)
    
    # Compute Brier score
    brier = np.mean((predictions - labels) ** 2)
    
    return {
        "ece": float(ece),
        "mce": float(mce),
        "brier_score": float(brier),
    }
