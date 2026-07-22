# System Components Detailed Specification

## 1. X-Ray AI Service (V1)

### 1.1 Service Architecture

```python
# Core Class Structure

class XRayAIService:
    """Main service orchestrator"""
    
    def __init__(self):
        self.model_loader = ModelLoader()
        self.preprocessor = DicomPreprocessor()
        self.inference_pipeline = InferencePipeline()
        self.explainability_engine = GradCAMEngine()
        self.calibrator = ConfidenceCalibrator()
        self.report_generator = ClinicalReportGenerator()
        self.cache = RedisCache()
        self.db = PostgreSQLConnection()
        self.metrics = MetricsCollector()
    
    async def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Main prediction endpoint"""
        pass
    
    async def explain(self, request: ExplainabilityRequest) -> ExplainabilityResponse:
        """Generate Grad-CAM explanations"""
        pass
    
    async def feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """Collect radiologist feedback"""
        pass
```

### 1.2 Model Architecture

```python
import torch
import torch.nn as nn
import torchxrayvision as xrv

class MedicalFoundationModel(nn.Module):
    """Foundation model for medical imaging"""
    
    def __init__(self, backbone='densenet121', pretrained=True):
        super().__init__()
        
        # Load pretrained TorchXRayVision model
        if backbone == 'densenet121':
            self.backbone = xrv.models.DenseNet(weights="densenet121-res224-all")
        elif backbone == 'resnet50':
            self.backbone = xrv.models.ResNet(weights="resnet50-res512-all")
        
        # Freeze backbone for initial training (optional)
        self.freeze_backbone()
        
        # Get feature dimension
        self.feature_dim = 1024  # DenseNet121 output
        
    def freeze_backbone(self):
        """Freeze backbone weights"""
        for param in self.backbone.parameters():
            param.requires_grad = False
    
    def unfreeze_backbone(self):
        """Unfreeze for fine-tuning"""
        for param in self.backbone.parameters():
            param.requires_grad = True
    
    def forward(self, x):
        """Extract features"""
        features = self.backbone.features(x)
        features = torch.nn.functional.relu(features, inplace=True)
        features = torch.nn.functional.adaptive_avg_pool2d(features, (1, 1))
        features = torch.flatten(features, 1)
        return features


class DiseaseHead(nn.Module):
    """Single disease classification head"""
    
    def __init__(self, in_features, disease_name, dropout=0.3):
        super().__init__()
        self.disease_name = disease_name
        
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(in_features, 512),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(512, 1)
        )
    
    def forward(self, features):
        return self.classifier(features)


class MultiDiseaseXRayModel(nn.Module):
    """Complete X-Ray AI model with multiple disease heads"""
    
    def __init__(self, diseases, backbone='densenet121', dropout=0.3):
        super().__init__()
        
        self.diseases = diseases
        self.foundation_model = MedicalFoundationModel(backbone=backbone)
        
        # Create disease-specific heads
        self.disease_heads = nn.ModuleDict({
            disease: DiseaseHead(
                in_features=self.foundation_model.feature_dim,
                disease_name=disease,
                dropout=dropout
            )
            for disease in diseases
        })
    
    def forward(self, x, return_features=False):
        """
        Forward pass
        
        Args:
            x: Input image tensor [B, C, H, W]
            return_features: If True, return intermediate features for Grad-CAM
        
        Returns:
            predictions: Dict of disease predictions
            features: (Optional) Intermediate features
        """
        # Extract features from foundation model
        features = self.foundation_model(x)
        
        # Pass through each disease head
        predictions = {}
        for disease, head in self.disease_heads.items():
            logits = head(features)
            predictions[disease] = torch.sigmoid(logits)
        
        if return_features:
            return predictions, features
        return predictions
    
    def get_disease_specific_features(self, x, disease):
        """Get features for specific disease (for Grad-CAM)"""
        features = self.foundation_model(x)
        logits = self.disease_heads[disease](features)
        return logits, features


# Disease taxonomy configuration
DISEASE_TAXONOMY = {
    "pneumonia": {
        "full_name": "Pneumonia",
        "icd10": "J18.9",
        "severity_levels": ["mild", "moderate", "severe"],
        "urgent": True
    },
    "tuberculosis": {
        "full_name": "Tuberculosis",
        "icd10": "A15.0",
        "severity_levels": ["active", "inactive"],
        "urgent": True
    },
    "cardiomegaly": {
        "full_name": "Cardiomegaly",
        "icd10": "I51.7",
        "severity_levels": ["mild", "moderate", "severe"],
        "urgent": False
    },
    "pleural_effusion": {
        "full_name": "Pleural Effusion",
        "icd10": "J90",
        "severity_levels": ["small", "moderate", "large"],
        "urgent": False
    },
    "pulmonary_edema": {
        "full_name": "Pulmonary Edema",
        "icd10": "J81.0",
        "severity_levels": ["mild", "moderate", "severe"],
        "urgent": True
    },
    "fracture": {
        "full_name": "Rib Fracture",
        "icd10": "S22.3",
        "severity_levels": ["single", "multiple"],
        "urgent": False
    }
}
```

### 1.3 DICOM Processing

```python
import pydicom
from pydicom.pixel_data_handlers.util import apply_voi_lut
import numpy as np
from monai.transforms import (
    Compose, LoadImage, EnsureChannelFirst,
    ScaleIntensity, Resize, NormalizeIntensity
)

class DicomPreprocessor:
    """DICOM and image preprocessing"""
    
    def __init__(self, target_size=(224, 224), normalize=True):
        self.target_size = target_size
        self.normalize = normalize
        
        # MONAI transforms for medical images
        self.transforms = Compose([
            EnsureChannelFirst(),
            ScaleIntensity(),
            Resize(spatial_size=target_size),
            NormalizeIntensity()
        ])
    
    def load_dicom(self, dicom_path):
        """
        Load and parse DICOM file
        
        Returns:
            image: numpy array
            metadata: dict of DICOM tags
        """
        try:
            ds = pydicom.dcmread(dicom_path)
            
            # Extract pixel data
            image = ds.pixel_array
            
            # Apply VOI LUT (window/level)
            if hasattr(ds, 'WindowCenter') and hasattr(ds, 'WindowWidth'):
                image = apply_voi_lut(image, ds)
            
            # Handle photometric interpretation
            if hasattr(ds, 'PhotometricInterpretation'):
                if ds.PhotometricInterpretation == "MONOCHROME1":
                    image = np.max(image) - image
            
            # Extract metadata
            metadata = self.extract_metadata(ds)
            
            return image, metadata
            
        except Exception as e:
            raise ValueError(f"Failed to load DICOM: {str(e)}")
    
    def extract_metadata(self, ds):
        """Extract relevant DICOM metadata"""
        metadata = {
            "patient_id": str(ds.get("PatientID", "UNKNOWN")),
            "study_instance_uid": str(ds.get("StudyInstanceUID", "UNKNOWN")),
            "series_instance_uid": str(ds.get("SeriesInstanceUID", "UNKNOWN")),
            "sop_instance_uid": str(ds.get("SOPInstanceUID", "UNKNOWN")),
            "modality": str(ds.get("Modality", "UNKNOWN")),
            "body_part": str(ds.get("BodyPartExamined", "UNKNOWN")),
            "view_position": str(ds.get("ViewPosition", "UNKNOWN")),
            "patient_age": str(ds.get("PatientAge", "UNKNOWN")),
            "patient_sex": str(ds.get("PatientSex", "UNKNOWN")),
            "study_date": str(ds.get("StudyDate", "UNKNOWN")),
            "image_type": str(ds.get("ImageType", "UNKNOWN")),
            "rows": int(ds.get("Rows", 0)),
            "columns": int(ds.get("Columns", 0)),
            "pixel_spacing": ds.get("PixelSpacing", [0, 0]),
        }
        return metadata
    
    def validate_xray(self, metadata):
        """Validate that DICOM is a chest X-ray"""
        if metadata["modality"] != "CR" and metadata["modality"] != "DX":
            raise ValueError(f"Invalid modality: {metadata['modality']}. Expected CR or DX.")
        
        if metadata["body_part"].upper() not in ["CHEST", "THORAX"]:
            raise ValueError(f"Invalid body part: {metadata['body_part']}. Expected CHEST.")
        
        valid_views = ["PA", "AP", "LAT", "LATERAL"]
        if metadata["view_position"].upper() not in valid_views:
            raise ValueError(f"Invalid view: {metadata['view_position']}. Expected {valid_views}.")
    
    def preprocess(self, image):
        """Apply preprocessing transforms"""
        # Convert to 3-channel if grayscale
        if len(image.shape) == 2:
            image = np.stack([image] * 3, axis=0)
        elif len(image.shape) == 3 and image.shape[2] == 1:
            image = np.transpose(image, (2, 0, 1))
            image = np.repeat(image, 3, axis=0)
        
        # Apply MONAI transforms
        image = self.transforms(image)
        
        return image
    
    def anonymize_dicom(self, ds):
        """Remove PHI from DICOM"""
        phi_tags = [
            "PatientName", "PatientBirthDate", "PatientAddress",
            "InstitutionName", "InstitutionAddress", "ReferringPhysicianName",
            "PerformingPhysicianName", "OperatorName"
        ]
        
        for tag in phi_tags:
            if hasattr(ds, tag):
                delattr(ds, tag)
        
        return ds
```

### 1.4 Inference Pipeline

```python
from typing import Dict, Optional
import torch
from torch.utils.data import DataLoader
import time

class InferencePipeline:
    """End-to-end inference pipeline"""
    
    def __init__(
        self,
        model: MultiDiseaseXRayModel,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        use_amp: bool = True,
        batch_size: int = 8
    ):
        self.model = model.to(device)
        self.model.eval()
        self.device = device
        self.use_amp = use_amp
        self.batch_size = batch_size
    
    @torch.no_grad()
    def predict(
        self,
        image: torch.Tensor,
        return_features: bool = False
    ) -> Dict[str, float]:
        """
        Run inference on single image
        
        Args:
            image: Preprocessed image tensor [C, H, W] or [B, C, H, W]
            return_features: Whether to return intermediate features
        
        Returns:
            predictions: Dict of disease probabilities
        """
        # Ensure batch dimension
        if image.dim() == 3:
            image = image.unsqueeze(0)
        
        image = image.to(self.device)
        
        # Time inference
        start_time = time.time()
        
        # Automatic Mixed Precision for speed
        if self.use_amp:
            with torch.cuda.amp.autocast():
                if return_features:
                    predictions, features = self.model(image, return_features=True)
                else:
                    predictions = self.model(image)
        else:
            if return_features:
                predictions, features = self.model(image, return_features=True)
            else:
                predictions = self.model(image)
        
        inference_time = time.time() - start_time
        
        # Convert to CPU and format
        predictions = {
            disease: float(prob.cpu().item())
            for disease, prob in predictions.items()
        }
        
        result = {
            "predictions": predictions,
            "inference_time_ms": inference_time * 1000
        }
        
        if return_features:
            result["features"] = features
        
        return result
    
    @torch.no_grad()
    def batch_predict(
        self,
        images: torch.Tensor
    ) -> List[Dict[str, float]]:
        """
        Run inference on batch of images
        
        Args:
            images: Batch of preprocessed images [B, C, H, W]
        
        Returns:
            predictions: List of prediction dicts
        """
        images = images.to(self.device)
        
        # Create dataloader for large batches
        dataloader = DataLoader(
            images,
            batch_size=self.batch_size,
            shuffle=False
        )
        
        all_predictions = []
        
        for batch in dataloader:
            if self.use_amp:
                with torch.cuda.amp.autocast():
                    batch_preds = self.model(batch)
            else:
                batch_preds = self.model(batch)
            
            # Convert to list of dicts
            batch_size = batch.size(0)
            for i in range(batch_size):
                preds = {
                    disease: float(prob[i].cpu().item())
                    for disease, prob in batch_preds.items()
                }
                all_predictions.append(preds)
        
        return all_predictions
```

### 1.5 Explainability (Grad-CAM)

```python
import cv2
import numpy as np
from torch.autograd import Variable

class GradCAM:
    """Grad-CAM for explainability"""
    
    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        
        # Register hooks
        self._register_hooks()
    
    def _register_hooks(self):
        """Register forward and backward hooks"""
        def forward_hook(module, input, output):
            self.activations = output.detach()
        
        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0].detach()
        
        self.target_layer.register_forward_hook(forward_hook)
        self.target_layer.register_full_backward_hook(backward_hook)
    
    def generate(self, input_image, target_class=None):
        """
        Generate Grad-CAM heatmap
        
        Args:
            input_image: Input tensor [1, C, H, W]
            target_class: Target disease class (if None, use predicted class)
        
        Returns:
            heatmap: Grad-CAM heatmap [H, W]
        """
        self.model.eval()
        
        # Forward pass
        output = self.model(input_image)
        
        # Get target class
        if target_class is None:
            target_class = output.argmax(dim=1)
        
        # Backward pass
        self.model.zero_grad()
        output[0, target_class].backward()
        
        # Get gradients and activations
        gradients = self.gradients[0]  # [C, H, W]
        activations = self.activations[0]  # [C, H, W]
        
        # Weight activations by gradients
        weights = gradients.mean(dim=(1, 2), keepdim=True)  # [C, 1, 1]
        weighted_activations = weights * activations  # [C, H, W]
        
        # Sum over channels and apply ReLU
        heatmap = weighted_activations.sum(dim=0)  # [H, W]
        heatmap = torch.relu(heatmap)
        
        # Normalize
        heatmap = heatmap / (heatmap.max() + 1e-8)
        
        return heatmap.cpu().numpy()


class GradCAMEngine:
    """Grad-CAM engine for multiple diseases"""
    
    def __init__(self, model, target_layer_name='features.denseblock4'):
        self.model = model
        self.target_layer = self._get_target_layer(target_layer_name)
        self.gradcam = GradCAM(model, self.target_layer)
    
    def _get_target_layer(self, layer_name):
        """Get target layer from model"""
        parts = layer_name.split('.')
        layer = self.model
        for part in parts:
            layer = getattr(layer, part)
        return layer
    
    def generate_disease_heatmaps(
        self,
        image: torch.Tensor,
        predictions: Dict[str, float],
        threshold: float = 0.5
    ) -> Dict[str, np.ndarray]:
        """
        Generate Grad-CAM for all predicted diseases
        
        Args:
            image: Input image tensor [1, C, H, W]
            predictions: Dict of disease predictions
            threshold: Only generate heatmaps for predictions above threshold
        
        Returns:
            heatmaps: Dict of disease heatmaps
        """
        heatmaps = {}
        
        for disease, prob in predictions.items():
            if prob >= threshold:
                heatmap = self.generate_disease_heatmap(image, disease)
                heatmaps[disease] = heatmap
        
        return heatmaps
    
    def generate_disease_heatmap(
        self,
        image: torch.Tensor,
        disease: str
    ) -> np.ndarray:
        """Generate Grad-CAM for specific disease"""
        # Get disease-specific output
        logits, features = self.model.get_disease_specific_features(image, disease)
        
        # Backward pass
        self.model.zero_grad()
        logits.backward()
        
        # Generate heatmap
        heatmap = self.gradcam.generate(image)
        
        return heatmap
    
    def overlay_heatmap(
        self,
        image: np.ndarray,
        heatmap: np.ndarray,
        alpha: float = 0.4
    ) -> np.ndarray:
        """
        Overlay heatmap on original image
        
        Args:
            image: Original image [H, W, C] or [H, W]
            heatmap: Grad-CAM heatmap [H, W]
            alpha: Transparency of heatmap
        
        Returns:
            overlay: Overlayed image [H, W, 3]
        """
        # Resize heatmap to match image
        heatmap_resized = cv2.resize(heatmap, (image.shape[1], image.shape[0]))
        
        # Convert heatmap to color
        heatmap_colored = cv2.applyColorMap(
            (heatmap_resized * 255).astype(np.uint8),
            cv2.COLORMAP_JET
        )
        
        # Convert grayscale image to RGB if needed
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        
        # Normalize image
        image_norm = ((image - image.min()) / (image.max() - image.min()) * 255).astype(np.uint8)
        
        # Overlay
        overlay = cv2.addWeighted(image_norm, 1 - alpha, heatmap_colored, alpha, 0)
        
        return overlay
```

### 1.6 Confidence Calibration

```python
import numpy as np
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression

class TemperatureScaling:
    """Temperature scaling for probability calibration"""
    
    def __init__(self):
        self.temperature = 1.0
    
    def fit(self, logits, labels):
        """
        Learn optimal temperature
        
        Args:
            logits: Model logits (before sigmoid)
            labels: Ground truth labels
        """
        def nll_loss(temperature):
            scaled_logits = logits / temperature
            probs = 1 / (1 + np.exp(-scaled_logits))
            loss = -np.mean(labels * np.log(probs + 1e-8) + 
                          (1 - labels) * np.log(1 - probs + 1e-8))
            return loss
        
        result = minimize(nll_loss, x0=1.0, bounds=[(0.01, 10.0)])
        self.temperature = result.x[0]
    
    def transform(self, logits):
        """Apply temperature scaling"""
        scaled_logits = logits / self.temperature
        return 1 / (1 + np.exp(-scaled_logits))


class PlattScaling:
    """Platt scaling (logistic regression) calibration"""
    
    def __init__(self):
        self.A = 1.0
        self.B = 0.0
    
    def fit(self, logits, labels):
        """Learn Platt scaling parameters"""
        def nll_loss(params):
            A, B = params
            probs = 1 / (1 + np.exp(A * logits + B))
            loss = -np.mean(labels * np.log(probs + 1e-8) + 
                          (1 - labels) * np.log(1 - probs + 1e-8))
            return loss
        
        result = minimize(nll_loss, x0=[1.0, 0.0])
        self.A, self.B = result.x
    
    def transform(self, logits):
        """Apply Platt scaling"""
        return 1 / (1 + np.exp(self.A * logits + self.B))


class ConfidenceCalibrator:
    """Multi-method confidence calibration"""
    
    def __init__(self, method='temperature'):
        self.method = method
        self.calibrators = {}
    
    def fit(self, predictions_dict, labels_dict):
        """
        Fit calibration for each disease
        
        Args:
            predictions_dict: Dict of disease predictions
            labels_dict: Dict of disease labels
        """
        for disease in predictions_dict.keys():
            logits = predictions_dict[disease]
            labels = labels_dict[disease]
            
            if self.method == 'temperature':
                calibrator = TemperatureScaling()
            elif self.method == 'platt':
                calibrator = PlattScaling()
            elif self.method == 'isotonic':
                calibrator = IsotonicRegression(out_of_bounds='clip')
            else:
                raise ValueError(f"Unknown method: {self.method}")
            
            calibrator.fit(logits, labels)
            self.calibrators[disease] = calibrator
    
    def transform(self, predictions_dict):
        """Apply calibration to predictions"""
        calibrated = {}
        for disease, probs in predictions_dict.items():
            if disease in self.calibrators:
                calibrated[disease] = self.calibrators[disease].transform(probs)
            else:
                calibrated[disease] = probs
        return calibrated
    
    def save(self, path):
        """Save calibration parameters"""
        import pickle
        with open(path, 'wb') as f:
            pickle.dump(self.calibrators, f)
    
    def load(self, path):
        """Load calibration parameters"""
        import pickle
        with open(path, 'rb') as f:
            self.calibrators = pickle.load(f)
```

## 2. Storage Layer

### 2.1 Redis Cache

```python
import redis
import json
import hashlib
from typing import Optional

class RedisCache:
    """Redis caching layer"""
    
    def __init__(self, host='localhost', port=6379, db=0, ttl=3600):
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
        self.ttl = ttl
    
    def generate_key(self, image_bytes: bytes) -> str:
        """Generate cache key from image"""
        hash_obj = hashlib.sha256(image_bytes)
        return f"prediction:{hash_obj.hexdigest()}"
    
    def get(self, key: str) -> Optional[dict]:
        """Get cached prediction"""
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def set(self, key: str, value: dict):
        """Cache prediction"""
        self.client.setex(
            key,
            self.ttl,
            json.dumps(value)
        )
    
    def delete(self, key: str):
        """Delete cached entry"""
        self.client.delete(key)
```

### 2.2 PostgreSQL Database

```python
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class InferenceLog(Base):
    """Log of all inference requests"""
    __tablename__ = 'inference_logs'
    
    id = Column(Integer, primary_key=True)
    request_id = Column(String, unique=True, index=True)
    study_instance_uid = Column(String, index=True)
    patient_id_hash = Column(String, index=True)  # Hashed for privacy
    model_version = Column(String)
    predictions = Column(JSON)  # Disease predictions
    confidence_scores = Column(JSON)  # Calibrated confidences
    inference_time_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class FeedbackRecord(Base):
    """Radiologist feedback"""
    __tablename__ = 'feedback_records'
    
    id = Column(Integer, primary_key=True)
    inference_id = Column(Integer, index=True)
    request_id = Column(String, index=True)
    radiologist_id = Column(String)
    ground_truth = Column(JSON)  # Actual diagnoses
    agreement = Column(JSON)  # Per-disease agreement
    comments = Column(String)
    flagged_for_training = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ModelMetadata(Base):
    """Model registry metadata"""
    __tablename__ = 'model_metadata'
    
    id = Column(Integer, primary_key=True)
    model_version = Column(String, unique=True)
    model_path = Column(String)
    framework = Column(String)
    architecture = Column(String)
    diseases = Column(JSON)
    training_dataset = Column(String)
    validation_metrics = Column(JSON)
    calibration_params = Column(JSON)
    status = Column(String)  # development, staging, production, deprecated
    deployed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
```

## Next Steps
Continue to `03-data-flow.md` for detailed data flow sequences.
