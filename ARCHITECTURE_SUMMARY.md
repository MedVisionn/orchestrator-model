# MedScanAI - Enterprise Medical AI Platform Architecture

## 🎯 Executive Summary

**MedScanAI** is an enterprise-grade, production-ready AI medical imaging platform designed for regulatory approval (FDA 510(k)), HIPAA compliance, and deployment at scale (millions of medical studies annually).

This repository contains the **X-Ray AI Service** - the first microservice in a multi-modality medical imaging platform that will eventually support CT, MRI, Mammography, and Ultrasound.

---

## 🏛️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Orchestrator (Future)                     │
│         Routes requests to modality-specific services            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    ┌──────────┐     ┌──────────┐    ┌──────────┐
    │  X-Ray   │     │   CT AI  │    │  MRI AI  │
    │ Service  │     │ Service  │    │ Service  │
    │  (V1)    │     │ (Future) │    │ (Future) │
    └────┬─────┘     └──────────┘    └──────────┘
         │
         ├─────────────────────────────┐
         │                             │
         ▼                             ▼
    ┌─────────────┐              ┌─────────────┐
    │   Model     │              │  Feedback   │
    │  Registry   │              │  Database   │
    │  (MLflow)   │              │(PostgreSQL) │
    └─────────────┘              └─────────────┘
         │
         ▼
    ┌─────────────┐              ┌─────────────┐
    │  Training   │─────────────>│  Dataset    │
    │  Pipeline   │              │ Versioning  │
    │  (Offline)  │              │    (DVC)    │
    └─────────────┘              └─────────────┘
```

---

## 🔬 X-Ray AI Service Architecture

### Medical AI Pipeline

```
Input Image (DICOM/PNG/JPEG)
         │
         ▼
┌─────────────────────┐
│  DICOM/Image Parser │  ← pydicom, PIL
│  • Metadata extract │
│  • Pixel normalization
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Preprocessing      │  ← MONAI, OpenCV
│  • Resize to 224x224│
│  • Normalize [0,1]  │
│  • Quality checks   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Foundation Model    │  ← TorchXRayVision
│ DenseNet-121        │
│ (Pretrained on:)    │
│ • CheXpert          │
│ • MIMIC-CXR         │
│ • NIH ChestX-ray14  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Feature Embedding   │
│ [B, 1024]           │
└──────────┬──────────┘
           │
           ├──────────┬──────────┬──────────┐
           ▼          ▼          ▼          ▼
      ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
      │Pneumo- │ │  TB    │ │Cardio- │ │Pleural │
      │nia     │ │ Head   │ │megaly  │ │Effusion│
      │ Head   │ │        │ │ Head   │ │ Head   │
      └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘
           │          │          │          │
           ├──────────┼──────────┼──────────┤
           │          │          │          │
      ┌────▼───┐ ┌───▼────┐           │
      │ Edema  │ │Fracture│           │
      │ Head   │ │ Head   │           │
      └────┬───┘ └────┬───┘           │
           │          │                │
           └──────────┴────────────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │ Calibration         │  ← Temperature Scaling
           │ • Temperature scale │     Platt Scaling
           │ • Confidence adjust │     Isotonic Regression
           └──────────┬──────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │ Explainability      │  ← Grad-CAM
           │ • Heatmap generation│
           │ • Attention regions │
           └──────────┬──────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │ Clinical Report     │
           │ • Findings          │
           │ • Recommendations   │
           │ • HL7 FHIR format   │
           └──────────┬──────────┘
                      │
                      ▼
                JSON Response
```

---

## 🎨 Design Patterns

### 1. Shared Foundation + Task-Specific Heads

**Why**: Instead of training 6 separate models (one per disease), we use:
- **One foundation model** (pretrained DenseNet-121) - extracts general X-ray features
- **Six disease heads** (lightweight classifiers) - specialized for each disease

**Benefits**:
- Single forward pass → faster inference
- Shared features → better generalization
- Easy to add/remove diseases
- Lower memory footprint
- Consistent feature representation

### 2. Inference-Training Separation

**Production Inference Service**:
- Immutable model versions
- No training logic
- Optimized for latency
- Stateless and scalable

**Offline Training Pipeline**:
- GPU-intensive
- Dataset versioning (DVC)
- Experiment tracking (MLflow)
- Validation and testing
- Model registry integration

**Why**: Security, stability, resource isolation, compliance

### 3. Confidence Calibration

**Problem**: Raw neural network outputs are often poorly calibrated (overconfident or underconfident)

**Solution**: Post-hoc calibration methods
- **Temperature Scaling**: Divides logits by learned temperature
- **Platt Scaling**: Logistic regression on validation set
- **Isotonic Regression**: Non-parametric calibration

**Why Critical for Medical AI**: Physicians need to trust confidence scores for clinical decision-making

---

## 📊 Data Flow Diagrams

### Inference Request Flow

```
1. Client Request
   ↓
2. FastAPI Endpoint (/predict)
   ↓
3. Validate Input (Pydantic)
   ↓
4. Check Cache (Redis)
   ↓ [MISS]
5. Preprocessing Service
   • Parse DICOM/Image
   • Extract metadata
   • Normalize pixels
   ↓
6. Model Inference
   • Load model (cached)
   • Forward pass
   • Get predictions
   ↓
7. Calibration
   • Apply temperature scaling
   • Adjust confidence scores
   ↓
8. Report Generation
   • Format findings
   • Generate recommendations
   • Create clinical report
   ↓
9. Store in Cache
   ↓
10. Audit Log
    • Log prediction
    • Store metrics
    ↓
11. Return Response
```

### Continuous Learning Flow

```
1. Radiologist Reviews Prediction
   ↓
2. POST /feedback
   • Ground truth labels
   • Comments
   • Quality rating
   ↓
3. Store in PostgreSQL
   • feedback table
   • Indexed by request_id
   ↓
4. Weekly Aggregation Job
   • Query new feedback
   • Filter quality > 3
   • Export to training format
   ↓
5. Dataset Versioning (DVC)
   • Add new cases
   • Create dataset-v1.x.dvc
   • Push to remote storage
   ↓
6. Trigger Training Pipeline (K8s Job)
   • Load new dataset
   • Fine-tune model
   • Validate on hold-out set
   ↓
7. Model Registry (MLflow)
   • Save model artifact
   • Log metrics
   • Set status: staging
   ↓
8. A/B Testing
   • Shadow mode deployment
   • Compare with production
   ↓
9. Promotion Decision
   • If metrics improve → production
   • If metrics degrade → rollback
   ↓
10. Blue-Green Deployment
    • Update K8s deployment
    • Switch traffic gradually
```

---

## 🛠️ Technology Stack

### Core ML/AI

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **PyTorch** | Deep learning framework | Industry standard, strong ecosystem, medical AI libraries |
| **TorchXRayVision** | Medical foundation models | Pretrained on 6+ medical datasets, clinically validated |
| **MONAI** | Medical imaging toolkit | Medical-specific transforms, DICOM handling, production-tested |
| **pytorch-grad-cam** | Explainability | Standard Grad-CAM implementation, multiple CAM variants |

### Web Framework

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **FastAPI** | REST API | Async support, auto OpenAPI docs, Pydantic integration, high performance |
| **Pydantic** | Data validation | Type safety, automatic validation, clear error messages |
| **uvicorn** | ASGI server | Production-grade, async, high performance |

### Data Storage

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **PostgreSQL** | Feedback, metadata | ACID compliance, JSON support, medical data requirements |
| **Redis** | Caching, rate limiting | In-memory speed, pub/sub, distributed locks |
| **S3/MinIO** | Model artifacts, images | Object storage, versioning, scalability |
| **TimescaleDB** | Time-series metrics | PostgreSQL extension, efficient time-series queries |

### MLOps

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **MLflow** | Model registry, tracking | Experiment tracking, model versioning, deployment integration |
| **DVC** | Dataset versioning | Git-like interface for data, reproducibility, S3 backend |
| **ONNX** | Model optimization | Cross-platform, faster inference, NVIDIA Triton support |

### Observability

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **Prometheus** | Metrics | Industry standard, pull-based, PromQL, Kubernetes native |
| **Grafana** | Dashboards | Visualization, alerting, multi-datasource |
| **structlog** | Logging | Structured logs, JSON output, context preservation, HIPAA-compliant |
| **OpenTelemetry** | Distributed tracing | Standard tracing, vendor-neutral, spans and traces |

### Infrastructure

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **Docker** | Containerization | Reproducible builds, isolation, portability |
| **Kubernetes** | Orchestration | Auto-scaling, self-healing, rolling updates, production standard |
| **Helm** | K8s package manager | Templating, versioning, easy deployment |
| **GitHub Actions** | CI/CD | Integrated with GitHub, matrix testing, artifact caching |

---

## 🔒 Security & Compliance

### HIPAA Compliance

1. **PHI Protection**:
   - Patient IDs anonymized
   - PHI redacted from logs
   - Encrypted storage (at rest)
   - TLS for data in transit

2. **Audit Trail**:
   - Every inference logged
   - Immutable audit logs
   - Radiologist actions tracked
   - Model version recorded

3. **Access Control**:
   - JWT authentication (configurable)
   - Role-based access control (RBAC)
   - Rate limiting per user/API key
   - IP whitelisting support

4. **Data Retention**:
   - Configurable retention policies
   - Automated archival
   - Secure deletion

### FDA 510(k) Readiness

1. **Software as Medical Device (SaMD)**:
   - Clear intended use documentation
   - Risk classification
   - Software Bill of Materials (SBOM)

2. **Clinical Validation**:
   - Validation dataset tracking
   - Performance metrics (AUC, sensitivity, specificity)
   - Subgroup analysis (age, gender, comorbidities)
   - Calibration metrics (ECE, Brier score)

3. **Quality Management System (QMS)**:
   - Version control for all components
   - Change management process
   - Bug tracking and resolution
   - Design history file

4. **Post-Market Surveillance**:
   - Continuous monitoring
   - Adverse event reporting
   - Model drift detection
   - Retraining triggers

---

## 📈 Scalability Design

### Horizontal Scaling

```
┌──────────────┐
│ Load Balancer│ (NGINX/AWS ALB)
└──────┬───────┘
       │
       ├────────────┬────────────┬────────────┐
       ▼            ▼            ▼            ▼
   ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐
   │ Pod 1│    │ Pod 2│    │ Pod 3│    │Pod...N│
   └──┬───┘    └──┬───┘    └──┬───┘    └──┬───┘
      │           │           │           │
      └───────────┴───────────┴───────────┘
                  │
      ┌───────────┼───────────┐
      │           │           │
      ▼           ▼           ▼
  ┌──────┐   ┌──────┐   ┌──────┐
  │Redis │   │ PG   │   │  S3  │
  │Cluster│  │Primary│  │Storage│
  └──────┘   └───┬──┘   └──────┘
                 │
                 ▼
            ┌────────┐
            │PG      │
            │Replicas│
            └────────┘
```

### Auto-Scaling Strategy

**Horizontal Pod Autoscaler (HPA)**:
```yaml
minReplicas: 3
maxReplicas: 50
metrics:
  - CPU > 70%
  - Memory > 80%
  - Custom: inference_queue_length > 10
```

**Cluster Autoscaler**:
- Add nodes when pods pending
- GPU node pools for batch jobs
- Mixed instance types (CPU/GPU)

### Performance Targets

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Inference Latency (p95) | < 2s | < 5s |
| Throughput | > 1000 req/min/instance | > 500 req/min/instance |
| Model Accuracy (AUC) | > 0.90 | > 0.85 |
| Availability | 99.9% | 99.5% |
| Error Rate | < 0.1% | < 1% |

---

## 🚀 Deployment Architecture

### Multi-Environment Strategy

```
Development
    ↓ (PR merged)
Staging
    ↓ (manual approval + tests pass)
Production
```

### Blue-Green Deployment

```
┌─────────────────────────────────┐
│     Load Balancer               │
└─────────┬───────────────────────┘
          │
          ├──────────────┐
          │              │
     [100%]          [0%]
          │              │
          ▼              ▼
    ┌──────────┐   ┌──────────┐
    │  Blue    │   │  Green   │
    │ (v1.2.0) │   │ (v1.3.0) │
    │ Current  │   │  New     │
    └──────────┘   └──────────┘
                         ↓
                    [Validation]
                         ↓
                    [Switch Traffic]
                         ↓
    ┌──────────┐   ┌──────────┐
    │  Blue    │   │  Green   │
    │ (v1.2.0) │   │ (v1.3.0) │
    │  [0%]    │   │ [100%]   │
    └──────────┘   └──────────┘
```

### Canary Deployment

```
Stage 1: 5% traffic → new version
         Monitor for 1 hour
         ↓ If stable
Stage 2: 25% traffic → new version
         Monitor for 2 hours
         ↓ If stable
Stage 3: 50% traffic → new version
         Monitor for 4 hours
         ↓ If stable
Stage 4: 100% traffic → new version
         Old version kept for rollback
```

---

## 📊 Monitoring & Alerting

### Key Metrics

**Service Health**:
- `xray_service_uptime_seconds`
- `xray_requests_total{endpoint, status}`
- `xray_request_duration_seconds{endpoint}` (histogram)

**Inference Performance**:
- `xray_inference_duration_seconds{model_version, device}`
- `xray_inference_requests_total{model_version}`
- `xray_predictions_total{disease, label}`

**Model Quality**:
- `xray_prediction_confidence{disease}` (histogram)
- `xray_high_confidence_predictions{disease}`
- `xray_low_confidence_predictions{disease}`

**Data Quality**:
- `xray_invalid_inputs_total{reason}`
- `xray_image_quality_warnings{warning_type}`

**Feedback Loop**:
- `xray_feedback_total{radiologist_id}`
- `xray_feedback_agreement{disease, agreement}`
- `xray_feedback_quality_rating` (histogram)

### Alert Rules

```yaml
# High Error Rate
- alert: HighErrorRate
  expr: rate(xray_errors_total[5m]) > 0.01
  for: 10m
  severity: critical

# Slow Inference
- alert: SlowInference
  expr: histogram_quantile(0.95, xray_inference_duration_seconds) > 5
  for: 5m
  severity: warning

# Model Disagreement with Radiologists
- alert: ModelDrift
  expr: rate(xray_feedback_agreement{agreement="disagree"}[1h]) > 0.3
  for: 30m
  severity: warning

# Low Confidence Predictions
- alert: LowConfidencePredictions
  expr: rate(xray_low_confidence_predictions[1h]) > 100
  for: 15m
  severity: info
```

---

## 🗄️ Database Schema

### Core Tables

```sql
-- Inference requests (audit trail)
CREATE TABLE inference_requests (
    id UUID PRIMARY KEY,
    request_id VARCHAR(50) UNIQUE NOT NULL,
    patient_id VARCHAR(100) NOT NULL,
    study_id VARCHAR(100),
    model_version VARCHAR(20) NOT NULL,
    predictions JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_patient (patient_id),
    INDEX idx_created (created_at)
);

-- Radiologist feedback
CREATE TABLE feedback (
    id UUID PRIMARY KEY,
    feedback_id VARCHAR(50) UNIQUE NOT NULL,
    request_id VARCHAR(50) REFERENCES inference_requests(request_id),
    radiologist_id VARCHAR(100) NOT NULL,
    ground_truth JSONB NOT NULL,
    comments TEXT,
    quality_rating INTEGER CHECK (quality_rating BETWEEN 1 AND 5),
    review_time_seconds INTEGER,
    flagged_for_training BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_request (request_id),
    INDEX idx_radiologist (radiologist_id),
    INDEX idx_flagged (flagged_for_training),
    INDEX idx_created (created_at)
);

-- Model versions
CREATE TABLE model_versions (
    id UUID PRIMARY KEY,
    version VARCHAR(20) UNIQUE NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_path TEXT NOT NULL,
    training_dataset VARCHAR(100),
    metrics JSONB,
    status VARCHAR(20) DEFAULT 'development', -- development, staging, production, deprecated
    deployed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit log (immutable)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    user_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

---

## 🧪 Testing Strategy

### Test Pyramid

```
           ┌────────┐
          /  E2E    \    (5%)
         /   Tests   \
        └────────────┘
       ┌──────────────┐
      /  Integration  \   (25%)
     /     Tests       \
    └──────────────────┘
   ┌────────────────────┐
  /     Unit Tests       \  (70%)
 /                        \
└──────────────────────────┘
```

### Test Coverage

**Unit Tests** (70%):
- Model forward pass
- Preprocessing functions
- Calibration methods
- Report generation
- Utility functions

**Integration Tests** (25%):
- API endpoint tests
- Database operations
- Cache operations
- End-to-end pipeline

**E2E Tests** (5%):
- Full user workflows
- Multi-service interactions
- Performance tests

### Test Data

- Sample DICOMs (various modalities)
- Sample X-rays (PNG/JPEG)
- Edge cases (corrupted files, unusual dimensions)
- Synthetic test cases

---

## 📚 API Documentation

### OpenAPI Specification

Automatically generated at `/docs` (Swagger UI) and `/redoc` (ReDoc)

### Key Endpoints

```
POST   /predict          - Disease prediction
POST   /explain          - Grad-CAM visualization
POST   /feedback         - Radiologist feedback
GET    /health           - Health check
GET    /metrics          - Prometheus metrics
GET    /model-info       - Current model metadata
```

### Example Request/Response

See `services/xray-ai-service/README.md` for detailed API examples

---

## 🎓 Best Practices Implemented

1. **Separation of Concerns**: Each component has a single responsibility
2. **Dependency Injection**: FastAPI dependencies for testability
3. **Configuration Management**: Environment-based config with validation
4. **Error Handling**: Comprehensive exception handling with proper HTTP status codes
5. **Logging**: Structured logging with correlation IDs
6. **Monitoring**: Instrumentation at every layer
7. **Documentation**: Code comments, docstrings, README files
8. **Type Hints**: Full Python type annotations
9. **Validation**: Pydantic schemas for all inputs/outputs
10. **Security**: Input validation, rate limiting, auth support

---

## 🔮 Future Roadmap

### Phase 1 (Months 1-3): X-Ray Service Production
- Complete X-Ray AI Service
- Production deployment
- Clinical validation
- FDA submission preparation

### Phase 2 (Months 4-6): Multi-Modality
- CT AI Service
- MRI AI Service
- AI Orchestrator
- Multi-modality ensemble

### Phase 3 (Months 7-9): Advanced Features
- Real-time inference streaming
- 3D visualization
- Multi-language reports
- Mobile app integration

### Phase 4 (Months 10-12): Scale & Optimize
- Global deployment
- Edge computing support
- Federated learning
- ONNX Runtime/Triton optimization

---

## 📖 Documentation Index

1. **Architecture**:
   - `docs/architecture/01-high-level-design.md` - System architecture
   - `docs/architecture/02-system-components.md` - Component details
   - `ARCHITECTURE_SUMMARY.md` - This file

2. **API**:
   - `docs/api/openapi.yaml` - OpenAPI specification
   - `services/xray-ai-service/README.md` - API usage guide

3. **Deployment**:
   - `docs/PRODUCTION_ROADMAP.md` - Production deployment plan
   - `infrastructure/kubernetes/` - Kubernetes manifests

4. **Development**:
   - `IMPLEMENTATION_STATUS.md` - Current progress
   - `services/xray-ai-service/README.md` - Developer guide
   - `docs/TRAINING_PIPELINE.md` - Training workflow

5. **Database**:
   - `database/schemas/001_initial_schema.sql` - Database schema

---

## 💡 Key Innovations

1. **Medical Foundation Model + Task Heads**: More efficient than separate models
2. **Post-hoc Calibration**: Trustworthy confidence scores for clinical use
3. **Inference-Training Separation**: Production stability with continuous learning
4. **HIPAA-Compliant Observability**: Full monitoring without PHI exposure
5. **Modular Microservices**: Easy to add new modalities
6. **Regulatory-Ready Design**: Built for FDA approval from day one

---

## 🤝 Contributing

This is a production medical AI system. All contributions must:
- Include comprehensive tests
- Follow code style guidelines
- Update documentation
- Pass security scans
- Include performance benchmarks

---

## 📧 Contact

- **Project**: MedScanAI
- **Repository**: MedVisionn/orchestrator-model
- **Documentation**: See `docs/` directory
- **Support**: GitHub Issues

---

**Version**: 1.0.0  
**Last Updated**: 2026-07-22  
**Status**: Active Development (60% Complete)
