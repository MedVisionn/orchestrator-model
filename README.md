# MedScanAI - AI Medical Imaging Platform

## Overview
Enterprise-grade AI-powered medical imaging platform designed for regulatory approval and production deployment at scale.

**Current Status**: V1 - Chest X-Ray AI Service  
**Target Scale**: Millions of medical studies  
**Compliance**: HIPAA, GDPR, FDA/CE regulatory ready

## Platform Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway / Load Balancer               │
│                    (Kong / NGINX / AWS ALB)                      │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├─────────────────────────────────────────────────────┐
             │                                                     │
┌────────────▼──────────────┐                    ┌────────────────▼─────────┐
│   AI Orchestrator Service │                    │  Admin & Monitoring UI   │
│   (Future - Route requests)│                    │  (Grafana / Custom)      │
└────────────┬──────────────┘                    └──────────────────────────┘
             │
             │
┌────────────▼──────────────────────────────────────────────────────────────┐
│                        X-Ray AI Service (V1)                              │
│  ┌─────────────┬──────────────┬─────────────┬──────────────────────────┐ │
│  │  Inference  │ Explainability│  Feedback   │      Health/Metrics      │ │
│  │  Pipeline   │    Service    │   Service   │                          │ │
│  └──────┬──────┴───────┬──────┴──────┬──────┴──────────┬───────────────┘ │
└─────────┼──────────────┼─────────────┼─────────────────┼─────────────────┘
          │              │             │                 │
          ▼              ▼             ▼                 ▼
┌─────────────────┐  ┌─────────┐  ┌──────────┐   ┌─────────────┐
│  Model Registry │  │  Redis  │  │PostgreSQL│   │ Prometheus  │
│    (MLflow)     │  │  Cache  │  │ Feedback │   │  + Grafana  │
└─────────────────┘  └─────────┘  └──────────┘   └─────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                    Offline Training Infrastructure                       │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐                 │
│  │   DVC + S3   │→ │ Training      │→ │  Validation  │                 │
│  │   Dataset    │  │ Pipeline      │  │  & Testing   │                 │
│  │  Versioning  │  │ (PyTorch)     │  │              │                 │
│  └──────────────┘  └───────┬───────┘  └──────┬───────┘                 │
│                            │                   │                         │
│                            ▼                   ▼                         │
│                    ┌────────────────┐  ┌──────────────┐                 │
│                    │ Model Registry │  │ Experiment   │                 │
│                    │   (MLflow)     │  │  Tracking    │                 │
│                    └────────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack & Rationale

### Core ML Framework
- **PyTorch 2.x**: Industry standard, excellent medical imaging support, dynamic graphs
- **TorchXRayVision**: Medical imaging foundation models (DenseNet, ResNet pretrained on CheXpert, MIMIC-CXR)
- **MONAI**: Medical imaging transforms, DICOM handling, production-ready preprocessing

### Model Serving
- **FastAPI**: Async, automatic OpenAPI docs, type validation, high performance
- **ONNX Runtime**: 2-3x inference speedup, hardware optimization
- **NVIDIA Triton** (Future): Multi-model serving, dynamic batching, model ensembles

### MLOps
- **MLflow**: Model registry, experiment tracking, model versioning, deployment tracking
- **DVC**: Dataset versioning, pipeline orchestration, reproducibility
- **Weights & Biases** (Alternative): Superior experiment visualization

### Data Storage
- **PostgreSQL**: Feedback, metadata, audit logs (ACID compliance for regulatory)
- **Redis**: Model cache, rate limiting, session management
- **MinIO/S3**: DICOM storage, model artifacts, training datasets

### Monitoring & Observability
- **Prometheus**: Time-series metrics, alerting
- **Grafana**: Visualization, dashboards
- **OpenTelemetry**: Distributed tracing
- **Sentry**: Error tracking, performance monitoring

### Infrastructure
- **Docker**: Containerization
- **Kubernetes**: Orchestration, auto-scaling, self-healing
- **Helm**: K8s package management
- **ArgoCD**: GitOps continuous deployment

### Security & Compliance
- **HashiCorp Vault**: Secrets management
- **Keycloak**: Identity & access management
- **Open Policy Agent**: Policy enforcement
- **Audit Logging**: PostgreSQL + ELK stack

## Repository Structure

```
orchestrator-model/
├── README.md
├── docs/
│   ├── architecture/
│   │   ├── 01-high-level-design.md
│   │   ├── 02-system-components.md
│   │   ├── 03-data-flow.md
│   │   ├── 04-security-architecture.md
│   │   └── diagrams/
│   ├── api/
│   │   ├── openapi.yaml
│   │   └── postman-collection.json
│   ├── deployment/
│   │   ├── deployment-guide.md
│   │   ├── kubernetes-setup.md
│   │   └── ci-cd-pipeline.md
│   ├── compliance/
│   │   ├── hipaa-compliance.md
│   │   ├── gdpr-compliance.md
│   │   └── fda-510k-considerations.md
│   └── runbooks/
│       ├── incident-response.md
│       └── maintenance.md
├── services/
│   └── xray-ai-service/           # V1 Implementation
│       ├── README.md
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── poetry.lock
│       ├── .env.example
│       ├── src/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── config/
│       │   │   ├── __init__.py
│       │   │   ├── settings.py
│       │   │   └── logging_config.py
│       │   ├── api/
│       │   │   ├── __init__.py
│       │   │   ├── routes/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── inference.py
│       │   │   │   ├── explainability.py
│       │   │   │   ├── feedback.py
│       │   │   │   ├── health.py
│       │   │   │   └── metrics.py
│       │   │   ├── schemas/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── request.py
│       │   │   │   ├── response.py
│       │   │   │   └── feedback.py
│       │   │   └── middleware/
│       │   │       ├── __init__.py
│       │   │       ├── auth.py
│       │   │       ├── rate_limit.py
│       │   │       ├── audit_log.py
│       │   │       └── error_handler.py
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── foundation/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── base_model.py
│       │   │   │   └── torchxrayvision_wrapper.py
│       │   │   ├── heads/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── base_head.py
│       │   │   │   ├── disease_head.py
│       │   │   │   └── multi_disease_head.py
│       │   │   ├── ensemble.py
│       │   │   └── model_loader.py
│       │   ├── inference/
│       │   │   ├── __init__.py
│       │   │   ├── pipeline.py
│       │   │   ├── preprocessor.py
│       │   │   ├── postprocessor.py
│       │   │   └── batch_inference.py
│       │   ├── explainability/
│       │   │   ├── __init__.py
│       │   │   ├── gradcam.py
│       │   │   ├── attention_maps.py
│       │   │   └── visualization.py
│       │   ├── calibration/
│       │   │   ├── __init__.py
│       │   │   ├── temperature_scaling.py
│       │   │   ├── platt_scaling.py
│       │   │   └── calibration_evaluator.py
│       │   ├── report/
│       │   │   ├── __init__.py
│       │   │   ├── generator.py
│       │   │   └── templates/
│       │   │       ├── standard_report.jinja2
│       │   │       └── detailed_report.jinja2
│       │   ├── dicom/
│       │   │   ├── __init__.py
│       │   │   ├── parser.py
│       │   │   ├── validator.py
│       │   │   └── anonymizer.py
│       │   ├── storage/
│       │   │   ├── __init__.py
│       │   │   ├── cache.py
│       │   │   ├── database.py
│       │   │   └── object_store.py
│       │   ├── monitoring/
│       │   │   ├── __init__.py
│       │   │   ├── metrics.py
│       │   │   ├── health_checks.py
│       │   │   └── performance_tracker.py
│       │   └── utils/
│       │       ├── __init__.py
│       │       ├── image_utils.py
│       │       ├── security.py
│       │       └── validators.py
│       ├── tests/
│       │   ├── __init__.py
│       │   ├── unit/
│       │   │   ├── test_preprocessor.py
│       │   │   ├── test_models.py
│       │   │   ├── test_inference.py
│       │   │   ├── test_explainability.py
│       │   │   └── test_calibration.py
│       │   ├── integration/
│       │   │   ├── test_api.py
│       │   │   ├── test_pipeline.py
│       │   │   └── test_database.py
│       │   ├── e2e/
│       │   │   └── test_workflow.py
│       │   └── fixtures/
│       │       ├── sample_xrays/
│       │       └── mock_data.py
│       ├── scripts/
│       │   ├── download_models.py
│       │   ├── run_calibration.py
│       │   └── benchmark.py
│       └── configs/
│           ├── model_config.yaml
│           ├── disease_taxonomy.yaml
│           └── inference_config.yaml
├── training/
│   ├── README.md
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── dvc.yaml
│   ├── params.yaml
│   ├── src/
│   │   ├── __init__.py
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   ├── datasets.py
│   │   │   ├── dataloaders.py
│   │   │   ├── augmentation.py
│   │   │   └── preprocessing.py
│   │   ├── training/
│   │   │   ├── __init__.py
│   │   │   ├── trainer.py
│   │   │   ├── multi_task_trainer.py
│   │   │   ├── loss_functions.py
│   │   │   └── optimizers.py
│   │   ├── evaluation/
│   │   │   ├── __init__.py
│   │   │   ├── metrics.py
│   │   │   ├── evaluator.py
│   │   │   └── clinical_validation.py
│   │   ├── models/
│   │   │   └── (same structure as service)
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── mlflow_utils.py
│   │       └── checkpoint_utils.py
│   ├── configs/
│   │   ├── training_config.yaml
│   │   ├── model_architecture.yaml
│   │   └── hyperparameters/
│   │       ├── default.yaml
│   │       └── production.yaml
│   ├── scripts/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   ├── calibrate.py
│   │   ├── export_onnx.py
│   │   └── register_model.py
│   └── notebooks/
│       ├── 01-data-exploration.ipynb
│       ├── 02-model-experimentation.ipynb
│       └── 03-error-analysis.ipynb
├── infrastructure/
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   ├── docker-compose.prod.yml
│   │   └── .dockerignore
│   ├── kubernetes/
│   │   ├── base/
│   │   │   ├── namespace.yaml
│   │   │   ├── configmap.yaml
│   │   │   ├── secret.yaml
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   ├── ingress.yaml
│   │   │   ├── hpa.yaml
│   │   │   └── pdb.yaml
│   │   ├── overlays/
│   │   │   ├── dev/
│   │   │   ├── staging/
│   │   │   └── production/
│   │   └── helm/
│   │       └── xray-service/
│   │           ├── Chart.yaml
│   │           ├── values.yaml
│   │           ├── values-prod.yaml
│   │           └── templates/
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── modules/
│   │   │   ├── eks/
│   │   │   ├── rds/
│   │   │   ├── redis/
│   │   │   └── s3/
│   │   └── environments/
│   │       ├── dev/
│   │       ├── staging/
│   │       └── production/
│   ├── monitoring/
│   │   ├── prometheus/
│   │   │   ├── prometheus.yml
│   │   │   └── alerts.yml
│   │   ├── grafana/
│   │   │   ├── dashboards/
│   │   │   │   ├── inference-metrics.json
│   │   │   │   ├── model-performance.json
│   │   │   │   └── system-health.json
│   │   │   └── provisioning/
│   │   └── loki/
│   │       └── loki-config.yaml
│   └── security/
│       ├── vault/
│       │   └── policies/
│       ├── network-policies.yaml
│       └── rbac.yaml
├── ci-cd/
│   ├── .github/
│   │   └── workflows/
│   │       ├── ci.yml
│   │       ├── cd-staging.yml
│   │       ├── cd-production.yml
│   │       ├── model-training.yml
│   │       └── security-scan.yml
│   ├── .gitlab-ci.yml
│   └── jenkins/
│       └── Jenkinsfile
├── database/
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_feedback_tables.sql
│   │   └── 003_audit_log.sql
│   └── schemas/
│       ├── inference_logs.sql
│       ├── feedback.sql
│       └── model_metadata.sql
└── scripts/
    ├── setup_dev_environment.sh
    ├── run_tests.sh
    ├── deploy.sh
    └── backup_models.sh
```

## Next Steps

This README provides the foundation. The following documents detail each component:

1. **Architecture Documentation** → See `docs/architecture/`
2. **API Specification** → See `docs/api/openapi.yaml`
3. **Deployment Guide** → See `docs/deployment/`
4. **Compliance Documentation** → See `docs/compliance/`

## Quick Start (Development)

```bash
# Clone repository
git clone https://github.com/MedVisionn/orchestrator-model.git
cd orchestrator-model

# Set up X-Ray AI Service
cd services/xray-ai-service
poetry install
poetry run python scripts/download_models.py

# Run locally
docker-compose up

# Run tests
poetry run pytest

# Access API
open http://localhost:8000/docs
```

## License
Proprietary - MedScanAI Inc.
