# Training Pipeline Documentation

## Overview

The MedScanAI training pipeline is designed for continuous model improvement through radiologist feedback. It is completely separated from the inference service to ensure production stability and security.

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    Continuous Learning Pipeline                     │
└────────────────────────────────────────────────────────────────────┘

1. FEEDBACK COLLECTION (Ongoing)
   ┌──────────────────┐
   │  Radiologist     │
   │  Reviews AI      │
   │  Predictions     │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Feedback DB     │
   │  PostgreSQL      │
   └────────┬─────────┘
            │
            │ Weekly query for new feedback
            ▼

2. DATASET VERSIONING (Weekly)
   ┌──────────────────┐
   │  Query Feedback  │
   │  • flag_for_     │
   │    training=true │
   │  • status=pending│
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Create Dataset  │
   │  Version         │
   │  • DVC tracking  │
   │  • S3 storage    │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Data Quality    │
   │  Validation      │
   │  • Check labels  │
   │  • Check images  │
   │  • Remove dups   │
   └────────┬─────────┘
            │
            │ Pass validation
            ▼

3. MODEL TRAINING (Weekly/Monthly)
   ┌──────────────────┐
   │  Load Previous   │
   │  Model Weights   │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Fine-tune on    │
   │  New Data        │
   │  • GPU Training  │
   │  • Mixed Prec.   │
   │  • Distributed   │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  MLflow Tracking │
   │  • Metrics       │
   │  • Params        │
   │  • Artifacts     │
   └────────┬─────────┘
            │
            ▼

4. MODEL VALIDATION (After training)
   ┌──────────────────┐
   │  Validation Set  │
   │  Evaluation      │
   │  • AUC-ROC       │
   │  • Sensitivity   │
   │  • Specificity   │
   └────────┬─────────┘
            │
            │ Meets threshold?
            ├─── NO ──→ [Discard model]
            │
            │ YES
            ▼
   ┌──────────────────┐
   │  Calibration     │
   │  • Temperature   │
   │  • Platt scaling │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Export ONNX     │
   │  • Optimize      │
   │  • Quantize      │
   └────────┬─────────┘
            │
            ▼

5. MODEL REGISTRY (After validation)
   ┌──────────────────┐
   │  Register Model  │
   │  in MLflow       │
   │  • version: v1.3 │
   │  • stage: staging│
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Update Database │
   │  model_metadata  │
   └────────┬─────────┘
            │
            ▼

6. SHADOW TESTING (Before production)
   ┌──────────────────┐
   │  Deploy to       │
   │  Staging         │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Run A/B Test    │
   │  • Old vs New    │
   │  • 48 hours      │
   │  • 1000+ studies │
   └────────┬─────────┘
            │
            │ Better performance?
            ├─── NO ──→ [Keep current model]
            │
            │ YES
            ▼

7. PRODUCTION DEPLOYMENT (Manual approval)
   ┌──────────────────┐
   │  Manual Review   │
   │  & Approval      │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Promote to Prod │
   │  • Blue-green    │
   │  • Canary        │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Monitor for     │
   │  24 hours        │
   └──────────────────┘
```

## Training Pipeline Components

### 1. Data Collection & Versioning

**Script:** `training/scripts/create_dataset_version.py`

```python
# Pseudocode
def create_dataset_version():
    # Query feedback from database
    feedback = query_flagged_feedback(
        flagged_for_training=True,
        used_in_training=False
    )
    
    # Download images from S3
    images = download_images(feedback.study_instance_uids)
    
    # Create dataset
    dataset = create_dataset(images, feedback.ground_truth)
    
    # Validate data quality
    validate_dataset(dataset)
    
    # Version with DVC
    dataset_version = dvc.add(dataset)
    
    # Tag and push
    dvc.push()
    git.tag(f"dataset-{version}")
    git.push()
    
    return dataset_version
```

**Configuration:** `training/configs/dataset_config.yaml`
```yaml
dataset:
  name: "xray_training_dataset"
  version: "v1.3.0"
  
  sources:
    - name: "chexpert"
      path: "s3://medscanai-data/chexpert/"
      weight: 0.4
    
    - name: "mimic_cxr"
      path: "s3://medscanai-data/mimic-cxr/"
      weight: 0.4
    
    - name: "feedback"
      path: "s3://medscanai-data/feedback/"
      weight: 0.2
  
  split:
    train: 0.8
    val: 0.1
    test: 0.1
  
  augmentation:
    horizontal_flip: 0.5
    rotation: [-15, 15]
    brightness: [0.8, 1.2]
    contrast: [0.8, 1.2]
    
  preprocessing:
    resize: [224, 224]
    normalize: true
    histogram_equalization: false
```

---

### 2. Model Training

**Script:** `training/scripts/train.py`

```python
import torch
import pytorch_lightning as pl
from torch.utils.data import DataLoader
import mlflow

class XRayTrainingPipeline:
    def __init__(self, config):
        self.config = config
        self.model = self.load_model()
        self.train_loader = self.create_dataloader('train')
        self.val_loader = self.create_dataloader('val')
    
    def load_model(self):
        """Load pretrained model or checkpoint"""
        if self.config.checkpoint_path:
            model = MultiDiseaseXRayModel.load_from_checkpoint(
                self.config.checkpoint_path
            )
        else:
            model = MultiDiseaseXRayModel(
                diseases=self.config.diseases,
                backbone=self.config.backbone
            )
        return model
    
    def train(self):
        """Main training loop"""
        # MLflow tracking
        mlflow.set_tracking_uri(self.config.mlflow_uri)
        mlflow.set_experiment(self.config.experiment_name)
        
        with mlflow.start_run():
            # Log parameters
            mlflow.log_params(self.config.to_dict())
            
            # Lightning trainer
            trainer = pl.Trainer(
                max_epochs=self.config.max_epochs,
                gpus=self.config.gpus,
                strategy='ddp',  # Distributed training
                precision=16,  # Mixed precision
                callbacks=[
                    pl.callbacks.ModelCheckpoint(
                        monitor='val_auc',
                        mode='max',
                        save_top_k=3
                    ),
                    pl.callbacks.EarlyStopping(
                        monitor='val_auc',
                        patience=10,
                        mode='max'
                    ),
                    MLflowCallback()  # Custom callback
                ],
                logger=pl.loggers.MLFlowLogger()
            )
            
            # Train
            trainer.fit(
                self.model,
                train_dataloaders=self.train_loader,
                val_dataloaders=self.val_loader
            )
            
            # Save best model
            best_model_path = trainer.checkpoint_callback.best_model_path
            mlflow.log_artifact(best_model_path)
            
            return best_model_path
```

**Configuration:** `training/configs/training_config.yaml`
```yaml
training:
  experiment_name: "xray_disease_detection"
  max_epochs: 50
  batch_size: 32
  num_workers: 8
  gpus: 4
  
  model:
    backbone: "densenet121"
    pretrained: true
    freeze_backbone: false
    dropout: 0.3
  
  optimizer:
    name: "adamw"
    lr: 0.0001
    weight_decay: 0.01
    
  scheduler:
    name: "cosine"
    warmup_epochs: 5
    min_lr: 0.00001
  
  loss:
    type: "focal_loss"  # Better for imbalanced data
    alpha: 0.25
    gamma: 2.0
  
  early_stopping:
    monitor: "val_auc"
    patience: 10
    mode: "max"
  
  checkpoint:
    monitor: "val_auc"
    save_top_k: 3
    mode: "max"
```

---

### 3. Model Evaluation

**Script:** `training/scripts/evaluate.py`

```python
import numpy as np
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score
import torch

class ModelEvaluator:
    def __init__(self, model, test_loader):
        self.model = model
        self.test_loader = test_loader
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    def evaluate(self):
        """Comprehensive model evaluation"""
        self.model.eval()
        self.model.to(self.device)
        
        all_predictions = []
        all_labels = []
        all_logits = []
        
        with torch.no_grad():
            for batch in self.test_loader:
                images, labels = batch
                images = images.to(self.device)
                
                # Forward pass
                predictions = self.model(images)
                
                for disease in self.model.diseases:
                    all_predictions.append(predictions[disease].cpu().numpy())
                    all_labels.append(labels[disease].numpy())
        
        # Calculate metrics per disease
        metrics = {}
        for disease in self.model.diseases:
            disease_preds = np.concatenate([p for p in all_predictions])
            disease_labels = np.concatenate([l for l in all_labels])
            
            metrics[disease] = {
                'auc_roc': roc_auc_score(disease_labels, disease_preds),
                'accuracy': accuracy_score(
                    disease_labels,
                    (disease_preds > 0.5).astype(int)
                ),
                'f1_score': f1_score(
                    disease_labels,
                    (disease_preds > 0.5).astype(int)
                ),
                'sensitivity': self.calculate_sensitivity(
                    disease_labels, disease_preds
                ),
                'specificity': self.calculate_specificity(
                    disease_labels, disease_preds
                )
            }
        
        # Overall metrics
        overall_auc = np.mean([m['auc_roc'] for m in metrics.values()])
        
        return {
            'per_disease_metrics': metrics,
            'overall_auc': overall_auc,
            'passes_threshold': overall_auc >= 0.90
        }
    
    def calculate_sensitivity(self, labels, predictions, threshold=0.5):
        """True Positive Rate"""
        preds_binary = (predictions > threshold).astype(int)
        true_positives = np.sum((preds_binary == 1) & (labels == 1))
        actual_positives = np.sum(labels == 1)
        return true_positives / actual_positives if actual_positives > 0 else 0
    
    def calculate_specificity(self, labels, predictions, threshold=0.5):
        """True Negative Rate"""
        preds_binary = (predictions > threshold).astype(int)
        true_negatives = np.sum((preds_binary == 0) & (labels == 0))
        actual_negatives = np.sum(labels == 0)
        return true_negatives / actual_negatives if actual_negatives > 0 else 0
```

**Validation Thresholds:**
```yaml
validation_thresholds:
  overall_auc: 0.90
  per_disease_auc: 0.85
  sensitivity: 0.85
  specificity: 0.80
  
  # Must pass all thresholds to proceed
  fail_on_threshold: true
```

---

### 4. Confidence Calibration

**Script:** `training/scripts/calibrate.py`

```python
from sklearn.isotonic import IsotonicRegression
from scipy.optimize import minimize
import pickle

class CalibrationPipeline:
    def __init__(self, model, calibration_set):
        self.model = model
        self.calibration_set = calibration_set
        self.calibrators = {}
    
    def calibrate(self, method='temperature'):
        """
        Calibrate model predictions
        
        Methods:
        - temperature: Temperature scaling (single parameter)
        - platt: Platt scaling (logistic regression)
        - isotonic: Isotonic regression (non-parametric)
        """
        # Get predictions and labels
        predictions, labels = self.get_predictions()
        
        # Calibrate each disease separately
        for disease in self.model.diseases:
            logits = predictions[disease]
            true_labels = labels[disease]
            
            if method == 'temperature':
                calibrator = self.temperature_scaling(logits, true_labels)
            elif method == 'platt':
                calibrator = self.platt_scaling(logits, true_labels)
            elif method == 'isotonic':
                calibrator = IsotonicRegression(out_of_bounds='clip')
                calibrator.fit(logits, true_labels)
            
            self.calibrators[disease] = calibrator
        
        # Save calibrators
        self.save_calibrators()
        
        return self.calibrators
    
    def temperature_scaling(self, logits, labels):
        """Find optimal temperature"""
        def nll_loss(temperature):
            scaled = logits / temperature
            probs = 1 / (1 + np.exp(-scaled))
            loss = -np.mean(
                labels * np.log(probs + 1e-8) +
                (1 - labels) * np.log(1 - probs + 1e-8)
            )
            return loss
        
        result = minimize(nll_loss, x0=1.0, bounds=[(0.01, 10.0)])
        return {'temperature': result.x[0]}
    
    def evaluate_calibration(self):
        """Evaluate calibration quality"""
        from sklearn.calibration import calibration_curve
        
        calibration_metrics = {}
        
        for disease in self.model.diseases:
            # Get calibrated predictions
            calibrated_preds = self.apply_calibration(disease)
            labels = self.calibration_set[disease]
            
            # Compute calibration curve
            prob_true, prob_pred = calibration_curve(
                labels,
                calibrated_preds,
                n_bins=10
            )
            
            # Expected Calibration Error (ECE)
            ece = np.mean(np.abs(prob_true - prob_pred))
            
            calibration_metrics[disease] = {
                'ece': ece,
                'calibration_curve': {
                    'prob_true': prob_true.tolist(),
                    'prob_pred': prob_pred.tolist()
                }
            }
        
        return calibration_metrics
    
    def save_calibrators(self, path='calibration.pkl'):
        """Save calibration parameters"""
        with open(path, 'wb') as f:
            pickle.dump(self.calibrators, f)
```

---

### 5. Model Export (ONNX)

**Script:** `training/scripts/export_onnx.py`

```python
import torch
import onnx
import onnxruntime as ort

class ONNXExporter:
    def __init__(self, model, output_path):
        self.model = model
        self.output_path = output_path
    
    def export(self, optimize=True, quantize=False):
        """Export model to ONNX format"""
        self.model.eval()
        
        # Dummy input
        dummy_input = torch.randn(1, 3, 224, 224)
        
        # Export
        torch.onnx.export(
            self.model,
            dummy_input,
            self.output_path,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={
                'input': {0: 'batch_size'},
                'output': {0: 'batch_size'}
            }
        )
        
        # Verify
        onnx_model = onnx.load(self.output_path)
        onnx.checker.check_model(onnx_model)
        
        if optimize:
            self.optimize_onnx()
        
        if quantize:
            self.quantize_onnx()
        
        # Benchmark
        self.benchmark()
    
    def optimize_onnx(self):
        """Optimize ONNX model"""
        from onnxruntime.transformers import optimizer
        
        optimized_path = self.output_path.replace('.onnx', '_optimized.onnx')
        optimizer.optimize_model(
            self.output_path,
            optimized_path,
            optimization_level=99
        )
        self.output_path = optimized_path
    
    def quantize_onnx(self):
        """Quantize to INT8"""
        from onnxruntime.quantization import quantize_dynamic, QuantType
        
        quantized_path = self.output_path.replace('.onnx', '_quantized.onnx')
        quantize_dynamic(
            self.output_path,
            quantized_path,
            weight_type=QuantType.QInt8
        )
        self.output_path = quantized_path
    
    def benchmark(self):
        """Benchmark ONNX model"""
        session = ort.InferenceSession(self.output_path)
        
        dummy_input = np.random.randn(1, 3, 224, 224).astype(np.float32)
        
        # Warmup
        for _ in range(10):
            session.run(None, {'input': dummy_input})
        
        # Benchmark
        import time
        num_runs = 100
        start = time.time()
        for _ in range(num_runs):
            session.run(None, {'input': dummy_input})
        end = time.time()
        
        avg_latency = (end - start) / num_runs * 1000  # ms
        
        print(f"Average latency: {avg_latency:.2f} ms")
        print(f"Throughput: {1000 / avg_latency:.2f} FPS")
```

---

### 6. Model Registry & Deployment

**Script:** `training/scripts/register_model.py`

```python
import mlflow
from mlflow.tracking import MlflowClient

class ModelRegistry:
    def __init__(self, mlflow_uri):
        mlflow.set_tracking_uri(mlflow_uri)
        self.client = MlflowClient()
    
    def register_model(
        self,
        run_id,
        model_name="xray_disease_classifier",
        metrics=None
    ):
        """Register model in MLflow"""
        # Register model
        model_uri = f"runs:/{run_id}/model"
        mv = mlflow.register_model(model_uri, model_name)
        
        # Add tags
        self.client.set_model_version_tag(
            model_name,
            mv.version,
            "framework",
            "pytorch"
        )
        
        # Add metrics
        if metrics:
            for key, value in metrics.items():
                self.client.set_model_version_tag(
                    model_name,
                    mv.version,
                    f"metric.{key}",
                    str(value)
                )
        
        return mv
    
    def promote_to_staging(self, model_name, version):
        """Promote model to staging"""
        self.client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage="Staging"
        )
    
    def promote_to_production(self, model_name, version):
        """Promote model to production (requires approval)"""
        # Add approval check here
        self.client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage="Production",
            archive_existing_versions=True
        )
```

---

## DVC Pipeline Configuration

**File:** `training/dvc.yaml`

```yaml
stages:
  prepare_dataset:
    cmd: python scripts/create_dataset_version.py
    deps:
      - scripts/create_dataset_version.py
    outs:
      - data/dataset.dvc
    params:
      - dataset
  
  train:
    cmd: python scripts/train.py
    deps:
      - scripts/train.py
      - data/dataset.dvc
    params:
      - training
    metrics:
      - metrics/train_metrics.json:
          cache: false
  
  evaluate:
    cmd: python scripts/evaluate.py
    deps:
      - scripts/evaluate.py
      - models/best_model.pth
    outs:
      - metrics/eval_metrics.json
    metrics:
      - metrics/eval_metrics.json:
          cache: false
  
  calibrate:
    cmd: python scripts/calibrate.py
    deps:
      - scripts/calibrate.py
      - models/best_model.pth
    outs:
      - models/calibration.pkl
  
  export_onnx:
    cmd: python scripts/export_onnx.py
    deps:
      - scripts/export_onnx.py
      - models/best_model.pth
    outs:
      - models/model.onnx
  
  register:
    cmd: python scripts/register_model.py
    deps:
      - scripts/register_model.py
      - models/model.onnx
      - models/calibration.pkl
      - metrics/eval_metrics.json
```

---

## Kubernetes CronJob for Automated Training

**File:** `infrastructure/kubernetes/training/cronjob.yaml`

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: model-training
  namespace: medscanai-training
spec:
  schedule: "0 2 * * 0"  # Weekly on Sunday at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: training
              image: medscanai/training-pipeline:latest
              command: ["python", "scripts/train_pipeline.py"]
              env:
                - name: MLFLOW_TRACKING_URI
                  value: "http://mlflow:5000"
                - name: DVC_REMOTE
                  value: "s3://medscanai-training-data"
              resources:
                requests:
                  nvidia.com/gpu: 4
                  memory: "32Gi"
                  cpu: "16"
                limits:
                  nvidia.com/gpu: 4
                  memory: "64Gi"
                  cpu: "32"
          nodeSelector:
            node.kubernetes.io/instance-type: p3.8xlarge
```

---

## Monitoring Training

**Grafana Dashboard Metrics:**
- Training loss per epoch
- Validation AUC per disease
- GPU utilization
- Training time
- Dataset size growth
- Model size
- Inference latency (ONNX vs PyTorch)

---

## Best Practices

1. **Always version datasets with DVC**
2. **Track all experiments in MLflow**
3. **Validate models before deployment**
4. **Calibrate confidence scores**
5. **Export to ONNX for production**
6. **A/B test new models in staging**
7. **Never deploy directly to production**
8. **Monitor model performance continuously**
9. **Keep rollback capability**
10. **Document all changes**
