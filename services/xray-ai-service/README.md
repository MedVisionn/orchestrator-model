# X-Ray AI Service

## Overview

Production-grade microservice for chest X-ray analysis with multi-label disease detection, explainability, and confidence calibration.

## Features

- **DICOM & Image Support**: Handle DICOM, PNG, JPEG formats
- **Medical Foundation Model**: TorchXRayVision DenseNet-121 pretrained on CheXpert, MIMIC-CXR, NIH
- **Multi-Label Classification**: 6 disease heads (Pneumonia, TB, Cardiomegaly, Pleural Effusion, Edema, Fracture)
- **Grad-CAM Explainability**: Visual attention heatmaps per disease
- **Confidence Calibration**: Temperature scaling for calibrated probabilities
- **Clinical Report Generation**: Structured findings with recommendations
- **RESTful API**: FastAPI with OpenAPI documentation
- **Production Ready**: Logging, monitoring, error handling, Docker support

## Technology Stack

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Framework** | FastAPI | Async support, automatic OpenAPI docs, high performance |
| **ML Framework** | PyTorch | Industry standard, strong medical AI ecosystem |
| **Medical AI** | TorchXRayVision | Pretrained on 6+ chest X-ray datasets, validated models |
| **DICOM** | pydicom + MONAI | Medical imaging standards, production-tested |
| **Explainability** | pytorch-grad-cam | Standard Grad-CAM implementation |
| **API Validation** | Pydantic | Type safety, automatic validation |
| **Monitoring** | Prometheus | Industry standard metrics |
| **Logging** | structlog | Structured logging for production |
| **Testing** | pytest | Comprehensive test framework |
| **Containerization** | Docker | Reproducible deployments |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                   │
├─────────────────────────────────────────────────────────┤
│  API Layer                                              │
│  ├─ /predict      - Disease prediction                 │
│  ├─ /explain      - Grad-CAM visualization             │
│  ├─ /feedback     - Radiologist feedback               │
│  ├─ /health       - Health check                       │
│  ├─ /metrics      - Prometheus metrics                 │
│  └─ /model-info   - Model metadata                     │
├─────────────────────────────────────────────────────────┤
│  Business Logic Layer                                   │
│  ├─ PreprocessingService  - DICOM/image processing     │
│  ├─ InferenceService      - Model inference            │
│  ├─ ExplainabilityService - Grad-CAM generation        │
│  ├─ CalibrationService    - Confidence calibration     │
│  └─ ReportService         - Clinical report generation │
├─────────────────────────────────────────────────────────┤
│  Model Layer                                            │
│  ├─ Foundation Model      - TorchXRayVision DenseNet   │
│  ├─ Disease Heads         - 6 binary classifiers       │
│  └─ Model Registry Client - MLflow integration         │
├─────────────────────────────────────────────────────────┤
│  Data Layer                                             │
│  ├─ Redis Cache           - Prediction caching         │
│  ├─ PostgreSQL            - Feedback storage           │
│  └─ S3/MinIO              - Model artifacts            │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
xray-ai-service/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py      # FastAPI dependencies
│   │   ├── middleware.py        # Request/response middleware
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── predict.py       # POST /predict
│   │       ├── explain.py       # POST /explain
│   │       ├── feedback.py      # POST /feedback
│   │       └── health.py        # GET /health, /metrics, /model-info
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Configuration management
│   │   ├── logging.py           # Structured logging setup
│   │   └── monitoring.py        # Prometheus metrics
│   ├── models/
│   │   ├── __init__.py
│   │   ├── foundation.py        # Medical foundation model
│   │   ├── disease_heads.py     # Task-specific heads
│   │   ├── calibration.py       # Confidence calibration
│   │   └── model_loader.py      # Model loading/caching
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── requests.py          # Request models
│   │   ├── responses.py         # Response models
│   │   └── internal.py          # Internal data models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── preprocessing.py     # DICOM/image preprocessing
│   │   ├── inference.py         # Inference orchestration
│   │   ├── explainability.py    # Grad-CAM generation
│   │   ├── report.py            # Report generation
│   │   └── feedback.py          # Feedback handling
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py        # Database connections
│   │   ├── models.py            # SQLAlchemy models
│   │   └── repositories.py      # Data access layer
│   ├── cache/
│   │   ├── __init__.py
│   │   └── redis_client.py      # Redis caching
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── dicom_utils.py       # DICOM utilities
│   │   ├── image_utils.py       # Image processing
│   │   └── validation.py        # Input validation
│   └── main.py                  # Application entry point
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/
│   │   ├── test_preprocessing.py
│   │   ├── test_inference.py
│   │   ├── test_calibration.py
│   │   └── test_models.py
│   ├── integration/
│   │   ├── test_api.py
│   │   └── test_pipeline.py
│   └── fixtures/
│       ├── sample_images/
│       └── sample_dicoms/
├── scripts/
│   ├── download_models.py       # Download pretrained models
│   ├── calibrate_model.py       # Generate calibration parameters
│   └── export_onnx.py           # Export to ONNX
├── config/
│   ├── config.yaml              # Application configuration
│   ├── diseases.yaml            # Disease definitions
│   └── prompts.yaml             # Report generation prompts
├── models/                      # Model artifacts (gitignored)
│   └── .gitkeep
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .dockerignore
├── .gitignore
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- CUDA-capable GPU (optional, for faster inference)

### Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Download pretrained models
python scripts/download_models.py

# 4. Generate calibration parameters (if you have validation data)
python scripts/calibrate_model.py --data-path /path/to/validation

# 5. Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost:5432/medscan"
export REDIS_URL="redis://localhost:6379/0"
export MLFLOW_TRACKING_URI="http://localhost:5000"
export MODEL_PATH="./models"

# 6. Run the service
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Deployment

```bash
# Build image
docker build -t xray-ai-service:latest .

# Run with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f xray-service

# Access API docs
open http://localhost:8000/docs
```

## API Usage

### Predict Endpoint

```bash
# With image file
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@chest_xray.jpg" \
  -F "patient_id=P12345" \
  -F "study_id=S67890"

# With DICOM file
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@chest_xray.dcm" \
  -F "patient_id=P12345"
```

**Response:**
```json
{
  "request_id": "req_abc123",
  "patient_id": "P12345",
  "study_id": "S67890",
  "model_version": "1.2.0",
  "predictions": {
    "pneumonia": {
      "probability": 0.78,
      "confidence": 0.82,
      "label": "positive",
      "threshold": 0.5
    },
    "tuberculosis": {
      "probability": 0.12,
      "confidence": 0.88,
      "label": "negative",
      "threshold": 0.3
    },
    "cardiomegaly": {
      "probability": 0.65,
      "confidence": 0.75,
      "label": "positive",
      "threshold": 0.5
    },
    "pleural_effusion": {
      "probability": 0.23,
      "confidence": 0.91,
      "label": "negative",
      "threshold": 0.4
    },
    "edema": {
      "probability": 0.41,
      "confidence": 0.79,
      "label": "negative",
      "threshold": 0.5
    },
    "fracture": {
      "probability": 0.08,
      "confidence": 0.94,
      "label": "negative",
      "threshold": 0.3
    }
  },
  "clinical_report": {
    "impression": "Findings suggestive of pneumonia and cardiomegaly.",
    "findings": [
      "Consolidation in the right lower lobe consistent with pneumonia (confidence: 82%)",
      "Enlarged cardiac silhouette suggesting cardiomegaly (confidence: 75%)"
    ],
    "recommendations": [
      "Clinical correlation recommended for pneumonia",
      "Consider echocardiography for cardiomegaly assessment"
    ],
    "limitations": "AI-assisted analysis. Requires radiologist confirmation."
  },
  "metadata": {
    "inference_time_ms": 245,
    "preprocessing_time_ms": 68,
    "model_time_ms": 156,
    "postprocessing_time_ms": 21,
    "timestamp": "2026-07-22T10:30:45.123Z",
    "image_properties": {
      "width": 512,
      "height": 512,
      "modality": "DX",
      "view_position": "PA"
    }
  }
}
```

### Explain Endpoint

```bash
curl -X POST "http://localhost:8000/explain" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "req_abc123",
    "diseases": ["pneumonia", "cardiomegaly"]
  }'
```

**Response:**
```json
{
  "request_id": "req_abc123",
  "explanations": {
    "pneumonia": {
      "heatmap_base64": "iVBORw0KGgoAAAANS...",
      "overlay_base64": "iVBORw0KGgoAAAANS...",
      "attention_regions": [
        {
          "x": 256,
          "y": 384,
          "width": 128,
          "height": 96,
          "intensity": 0.92,
          "anatomical_region": "right lower lobe"
        }
      ]
    },
    "cardiomegaly": {
      "heatmap_base64": "iVBORw0KGgoAAAANS...",
      "overlay_base64": "iVBORw0KGgoAAAANS...",
      "attention_regions": [
        {
          "x": 256,
          "y": 256,
          "width": 200,
          "height": 180,
          "intensity": 0.85,
          "anatomical_region": "cardiac silhouette"
        }
      ]
    }
  },
  "generation_time_ms": 423
}
```

### Feedback Endpoint

```bash
curl -X POST "http://localhost:8000/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "req_abc123",
    "radiologist_id": "R789",
    "ground_truth": {
      "pneumonia": true,
      "tuberculosis": false,
      "cardiomegaly": true,
      "pleural_effusion": false,
      "edema": false,
      "fracture": false
    },
    "comments": "Confirmed pneumonia. Cardiomegaly is borderline.",
    "quality_rating": 4
  }'
```

### Health & Monitoring

```bash
# Health check
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8000/metrics

# Model info
curl http://localhost:8000/model-info
```

## Configuration

Edit `config/config.yaml`:

```yaml
model:
  name: "densenet121-res224-all"
  version: "1.2.0"
  input_size: [224, 224]
  device: "cuda"  # or "cpu"
  batch_size: 1
  enable_onnx: false

diseases:
  - name: "pneumonia"
    threshold: 0.5
    clinical_significance: "high"
  - name: "tuberculosis"
    threshold: 0.3
    clinical_significance: "critical"
  # ... more diseases

inference:
  timeout_seconds: 30
  enable_caching: true
  cache_ttl_seconds: 3600

calibration:
  method: "temperature_scaling"
  temperature: 1.5

monitoring:
  enable_prometheus: true
  log_level: "INFO"
  log_predictions: true
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_inference.py

# Run integration tests only
pytest tests/integration/

# Run with verbose output
pytest -v -s
```

## Performance

### Benchmarks (Single Instance)

| Metric | GPU (NVIDIA T4) | CPU (8 cores) |
|--------|-----------------|---------------|
| Inference Latency (p50) | 180 ms | 850 ms |
| Inference Latency (p95) | 245 ms | 1200 ms |
| Throughput | 400 req/min | 70 req/min |
| Memory Usage | 4 GB | 2 GB |

### Optimization Strategies

1. **Model Optimization**: Export to ONNX for 2-3x speedup
2. **Batch Processing**: Group requests for higher throughput
3. **Caching**: Redis cache for duplicate studies
4. **Async I/O**: FastAPI async handlers for I/O-bound operations
5. **Horizontal Scaling**: Deploy multiple replicas with load balancer

## Monitoring & Observability

### Key Metrics

- `xray_inference_requests_total` - Total inference requests
- `xray_inference_duration_seconds` - Inference latency histogram
- `xray_predictions_by_disease` - Prediction distribution per disease
- `xray_model_errors_total` - Error count by type
- `xray_cache_hit_ratio` - Cache effectiveness
- `xray_feedback_total` - Feedback submissions

### Grafana Dashboard

Import `../monitoring/grafana/xray-service-dashboard.json` for pre-built dashboard.

## Security

- **Input Validation**: Pydantic schemas with strict validation
- **File Upload Limits**: Max 10MB per request
- **Rate Limiting**: Redis-based rate limiter
- **Authentication**: JWT token support (configure via middleware)
- **HIPAA Compliance**: PHI logging disabled, audit trail enabled
- **Secure Headers**: CORS, CSP, HSTS configured

## Deployment

### Kubernetes

```bash
# Apply Kubernetes manifests
kubectl apply -f ../infrastructure/kubernetes/xray-service/

# Check deployment
kubectl get pods -l app=xray-ai-service

# View logs
kubectl logs -f deployment/xray-ai-service

# Scale replicas
kubectl scale deployment xray-ai-service --replicas=10
```

### Production Checklist

- [ ] Configure proper resource limits (CPU, memory, GPU)
- [ ] Set up horizontal pod autoscaler
- [ ] Configure health check endpoints
- [ ] Set up monitoring alerts
- [ ] Enable request tracing
- [ ] Configure backup for feedback database
- [ ] Set up model registry integration
- [ ] Configure CI/CD pipeline
- [ ] Load test with production-like data
- [ ] Document incident response procedures

## Continuous Learning Pipeline

This service does NOT retrain models. For continuous learning:

1. **Feedback Collection**: POST /feedback stores radiologist corrections
2. **Dataset Aggregation**: Scheduled job queries feedback database
3. **Dataset Versioning**: DVC tracks dataset versions
4. **Offline Training**: Kubernetes training jobs with GPU nodes
5. **Validation**: Automated validation on hold-out set
6. **Model Registry**: MLflow stores validated models
7. **Deployment**: CI/CD deploys new model version
8. **A/B Testing**: Shadow mode or canary deployment
9. **Monitoring**: Track performance metrics
10. **Promotion**: Promote to production if metrics improve

See `../../docs/TRAINING_PIPELINE.md` for details.

## Troubleshooting

### Common Issues

**Issue**: CUDA out of memory
```bash
# Solution: Use CPU or reduce batch size
export DEVICE=cpu
# or in config.yaml: device: "cpu"
```

**Issue**: Model download fails
```bash
# Solution: Download manually
python scripts/download_models.py --force
```

**Issue**: DICOM parsing errors
```bash
# Check DICOM file validity
python -c "import pydicom; pydicom.dcmread('file.dcm')"
```

## Contributing

1. Follow PEP 8 style guide
2. Write unit tests for new features
3. Update API documentation
4. Run pre-commit hooks
5. Ensure all tests pass

## License

Proprietary - MedScanAI Inc.

## Support

- Technical Issues: tech@medscanai.com
- Clinical Questions: clinical@medscanai.com
- Documentation: https://docs.medscanai.com
