# High-Level Architecture Design

## Executive Summary

MedScanAI is an enterprise-grade AI medical imaging platform designed for regulatory approval, HIPAA compliance, and production deployment at scale (millions of studies).

**Design Principles:**
- Microservices architecture for scalability
- Separation of inference and training
- Medical foundation models with task-specific heads
- Observability-first design
- Security and compliance by design
- Continuous learning without runtime retraining

## System Components

### 1. AI Orchestrator (Future)
**Purpose**: Route requests to appropriate modality-specific services

**Responsibilities**:
- Request routing based on modality (X-Ray, CT, MRI)
- Load balancing across service instances
- Request queuing and prioritization
- Multi-modality ensemble coordination
- API gateway functionality

**Technology**: FastAPI + Redis + PostgreSQL

### 2. X-Ray AI Service (V1 - Current Implementation)
**Purpose**: Chest X-Ray analysis with disease detection

**Responsibilities**:
- DICOM/image ingestion and validation
- Preprocessing and normalization
- Multi-label disease classification
- Grad-CAM explainability generation
- Confidence calibration
- Clinical report generation
- Feedback collection

**Technology**: FastAPI + PyTorch + TorchXRayVision + MONAI

### 3. Model Registry
**Purpose**: Centralized model versioning and lifecycle management

**Responsibilities**:
- Model versioning with metadata
- A/B testing configuration
- Model promotion workflow (dev → staging → production)
- Model performance tracking
- Rollback capabilities

**Technology**: MLflow + MinIO/S3

### 4. Training Pipeline (Offline)
**Purpose**: Continuous model improvement without production impact

**Responsibilities**:
- Dataset versioning and management
- Distributed training orchestration
- Hyperparameter optimization
- Model validation and testing
- Calibration pipeline
- Model export (PyTorch → ONNX)

**Technology**: PyTorch Lightning + DVC + MLflow + Kubernetes Jobs

### 5. Monitoring & Observability
**Purpose**: System health, model performance, and compliance tracking

**Responsibilities**:
- Inference latency and throughput metrics
- Model prediction distribution monitoring
- Data drift detection
- Concept drift detection
- Error rate tracking
- Regulatory audit logging

**Technology**: Prometheus + Grafana + ELK Stack + OpenTelemetry

### 6. Storage Layer
**Purpose**: Persistent data storage for different use cases

**Components**:
- **Object Storage (S3/MinIO)**: DICOM files, model artifacts, training datasets
- **Relational DB (PostgreSQL)**: Feedback, metadata, audit logs
- **Cache (Redis)**: Model predictions, rate limiting, session management
- **Time-Series DB (TimescaleDB)**: Metrics and monitoring data

## Architecture Patterns

### Pattern 1: Medical Foundation Model + Task-Specific Heads

```
┌─────────────────────────────────────────────────────────┐
│                    Input: Chest X-Ray                   │
│                  (DICOM or PNG/JPEG)                    │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Preprocessing Pipeline                      │
│  • DICOM parsing & metadata extraction                  │
│  • Pixel normalization (0-1 or -1 to 1)                │
│  • Resize to 224x224 or 512x512                        │
│  • Histogram equalization (optional)                    │
│  • MONAI transforms                                     │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│        Medical Foundation Model (Frozen/Fine-tuned)     │
│                                                          │
│  Options:                                               │
│  1. TorchXRayVision DenseNet-121                       │
│     (Pretrained: CheXpert + MIMIC-CXR + NIH)           │
│  2. MONAI models                                        │
│  3. MedCLIP (multimodal)                               │
│                                                          │
│  Output: Feature Vector [1024-dim or 2048-dim]         │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Disease-Specific Heads                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Pneumonia   │  │ Tuberculosis │  │ Cardiomegaly │  │
│  │    Head      │  │    Head      │  │    Head      │  │
│  │ FC(1024→1)   │  │ FC(1024→1)   │  │ FC(1024→1)   │  │
│  │  + Sigmoid   │  │  + Sigmoid   │  │  + Sigmoid   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐  │
│  │   Pleural    │  │    Edema     │  │   Fracture   │  │
│  │   Effusion   │  │    Head      │  │    Head      │  │
│  │    Head      │  │ FC(1024→1)   │  │ FC(1024→1)   │  │
│  │ FC(1024→1)   │  │  + Sigmoid   │  │  + Sigmoid   │  │
│  │  + Sigmoid   │  └──────────────┘  └──────────────┘  │
│  └──────────────┘                                       │
│                                                          │
│  Each head outputs: probability ∈ [0, 1]               │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│            Confidence Calibration                        │
│  • Temperature Scaling                                   │
│  • Platt Scaling                                        │
│  • Isotonic Regression                                  │
│                                                          │
│  Converts raw probabilities to calibrated confidence    │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Explainability (Grad-CAM)                   │
│  • Generate attention heatmaps                          │
│  • Overlay on original image                            │
│  • Per-disease visualization                            │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│            Clinical Report Generation                    │
│  • Structured findings                                   │
│  • Confidence scores                                    │
│  • Differential diagnoses                               │
│  • Recommendations                                      │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    JSON Response                         │
│  {                                                       │
│    "predictions": {...},                                │
│    "confidence_scores": {...},                          │
│    "explanations": {...},                               │
│    "clinical_report": "...",                            │
│    "metadata": {...}                                    │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
```

**Why This Pattern?**
- **Efficiency**: Single forward pass through foundation model
- **Consistency**: Shared representation across diseases
- **Modularity**: Easy to add/remove disease heads
- **Transfer Learning**: Foundation captures general X-Ray features
- **Maintainability**: Update heads independently

### Pattern 2: Inference-Training Separation

```
┌────────────────────────────────────────────────────────────────┐
│                      Production Inference                       │
│                                                                 │
│  ┌────────────┐         ┌──────────────┐                      │
│  │   Client   │────────>│  X-Ray API   │                      │
│  │  Request   │         │   Service    │                      │
│  └────────────┘         └──────┬───────┘                      │
│                                 │                               │
│                                 ▼                               │
│                         ┌───────────────┐                      │
│                         │ Model (v1.2)  │                      │
│                         │  (Immutable)  │                      │
│                         └───────┬───────┘                      │
│                                 │                               │
│                                 ▼                               │
│                         ┌───────────────┐                      │
│                         │  Prediction   │                      │
│                         └───────┬───────┘                      │
│                                 │                               │
│                                 ▼                               │
│                  ┌──────────────────────────┐                  │
│                  │  Feedback Collection     │                  │
│                  │  (Radiologist Review)    │                  │
│                  └──────────┬───────────────┘                  │
└─────────────────────────────┼───────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  PostgreSQL DB   │
                    │  (Feedback Data) │
                    └──────────┬───────┘
                              │
╔═════════════════════════════╧════════════════════════════════╗
║              Offline Training Environment                     ║
║                                                               ║
║  ┌────────────────┐                                          ║
║  │ Feedback Query │                                          ║
║  │  (Weekly/Daily)│                                          ║
║  └────────┬───────┘                                          ║
║           │                                                   ║
║           ▼                                                   ║
║  ┌──────────────────┐      ┌──────────────────┐             ║
║  │  Dataset Update  │─────>│ DVC Version      │             ║
║  │  (Add New Cases) │      │ dataset-v1.3.dvc │             ║
║  └──────────────────┘      └──────────────────┘             ║
║           │                                                   ║
║           ▼                                                   ║
║  ┌──────────────────┐      ┌──────────────────┐             ║
║  │  Training Job    │─────>│ MLflow Tracking  │             ║
║  │  (K8s Job/GPU)   │      │ Experiment #347  │             ║
║  └──────────────────┘      └──────────────────┘             ║
║           │                                                   ║
║           ▼                                                   ║
║  ┌──────────────────┐                                        ║
║  │   Validation     │                                        ║
║  │  • Accuracy      │                                        ║
║  │  • AUC-ROC       │                                        ║
║  │  • Calibration   │                                        ║
║  │  • Clinical Test │                                        ║
║  └──────────┬───────┘                                        ║
║           │ PASS                                              ║
║           ▼                                                   ║
║  ┌──────────────────┐      ┌──────────────────┐             ║
║  │ Model Registry   │─────>│  Model v1.3      │             ║
║  │ (MLflow)         │      │  Status: Staging │             ║
║  └──────────────────┘      └──────────────────┘             ║
║           │                                                   ║
║           ▼                                                   ║
║  ┌──────────────────┐                                        ║
║  │  Shadow Testing  │                                        ║
║  │  (A/B Compare)   │                                        ║
║  └──────────┬───────┘                                        ║
║           │ SUCCESS                                           ║
║           ▼                                                   ║
║  ┌──────────────────┐                                        ║
║  │ Promote to Prod  │                                        ║
║  │  Model v1.3      │                                        ║
║  └──────────┬───────┘                                        ║
╚═════════════╧═════════════════════════════════════════════════╝
              │
              ▼
    ┌──────────────────┐
    │ Update Production│
    │ (Blue-Green or   │
    │  Canary Deploy)  │
    └──────────────────┘
```

**Why Separate Inference and Training?**
- **Stability**: Production service never interrupted by training
- **Resource Isolation**: Training requires GPU, inference can use CPU/optimized runtime
- **Security**: Training data never in production environment
- **Scalability**: Scale inference and training independently
- **Compliance**: Clear audit trail, no data leakage

### Pattern 3: Multi-Stage Deployment Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Development  │────>│   Staging    │────>│ Production   │
│              │     │              │     │              │
│ • Local Test │     │ • Integration│     │ • Canary     │
│ • Unit Tests │     │ • Load Test  │     │ • Blue-Green │
│              │     │ • Shadow Mode│     │ • Full Deploy│
└──────────────┘     └──────────────┘     └──────────────┘
```

## Data Flow Diagrams

### Inference Request Flow

```
User/System
    │
    │ 1. POST /predict
    │    (DICOM or Image + Metadata)
    ▼
┌─────────────────────┐
│   API Gateway       │
│   • Rate Limiting   │
│   • Auth Check      │
│   • Request Log     │
└────────┬────────────┘
         │
         │ 2. Forward Request
         ▼
┌─────────────────────┐
│  X-Ray AI Service   │
│                     │
│  ┌───────────────┐  │
│  │ Check Cache   │  │
│  └───────┬───────┘  │
│          │ MISS     │
│          ▼          │
│  ┌───────────────┐  │
│  │ Validate      │  │
│  │ Input         │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Preprocess    │  │
│  │ DICOM/Image   │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Load Model    │  │
│  │ (from cache)  │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Inference     │  │
│  │ (GPU/CPU)     │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Calibration   │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Explainability│  │
│  │ (Grad-CAM)    │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Report Gen    │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Cache Result  │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Log Inference │  │
│  └───────┬───────┘  │
└──────────┼──────────┘
           │
           │ 3. JSON Response
           ▼
        Client
           │
           │ 4. Radiologist Review (async)
           ▼
┌─────────────────────┐
│  Feedback Service   │
│  POST /feedback     │
└─────────┬───────────┘
          │
          │ 5. Store Feedback
          ▼
┌─────────────────────┐
│   PostgreSQL        │
│   feedback table    │
└─────────────────────┘
```

## Scalability Design

### Horizontal Scaling Strategy

```
┌─────────────────────────────────────────────────────┐
│                Load Balancer                        │
│            (NGINX / AWS ALB / Kong)                 │
└───────┬─────────────────────────────────┬───────────┘
        │                                 │
        ▼                                 ▼
┌─────────────────┐            ┌─────────────────┐
│ X-Ray Service   │            │ X-Ray Service   │
│   Instance 1    │    ...     │   Instance N    │
│   (Pod 1)       │            │   (Pod N)       │
└────────┬────────┘            └────────┬────────┘
         │                              │
         └──────────────┬───────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
┌──────────────┐  ┌──────────┐  ┌──────────────┐
│    Redis     │  │PostgreSQL│  │ Model Store  │
│  (Shared)    │  │ (Shared) │  │   (S3/EFS)   │
└──────────────┘  └──────────┘  └──────────────┘
```

### Auto-Scaling Configuration

**Horizontal Pod Autoscaler (HPA)**:
```yaml
minReplicas: 3
maxReplicas: 50
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: inference_queue_length
      target:
        type: AverageValue
        averageValue: "10"
```

**Cluster Autoscaler**:
- Scale nodes based on pending pods
- Support GPU node pools for batch processing
- Mixed instance types (CPU vs GPU)

## Performance Targets

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Inference Latency (p95) | < 2 seconds | < 5 seconds |
| Throughput | > 1000 req/min/instance | > 500 req/min/instance |
| Model Accuracy (AUC) | > 0.90 | > 0.85 |
| Availability | 99.9% | 99.5% |
| Error Rate | < 0.1% | < 1% |
| Cache Hit Rate | > 30% | > 20% |

## Disaster Recovery

### Backup Strategy
- **Database**: Daily full backup + continuous WAL archiving
- **Models**: Version-controlled in S3 with cross-region replication
- **Configuration**: Git-tracked, immutable infrastructure

### Recovery Time Objectives (RTO/RPO)
- RTO: 1 hour
- RPO: 15 minutes

### Failure Scenarios
1. **Service Instance Failure**: Automatic pod restart + health checks
2. **Database Failure**: Automatic failover to standby replica
3. **Region Failure**: Multi-region deployment with DNS failover
4. **Model Corruption**: Rollback to previous version from registry

## Next: Component Deep Dive
See `02-system-components.md` for detailed component specifications.
