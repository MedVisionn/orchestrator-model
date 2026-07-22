# MedScanAI - Quick Reference Guide

## 🚀 Quick Start Commands

### Local Development
```bash
# Setup
cd orchestrator-model/services/xray-ai-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Test
pytest tests/ -v --cov=src
```

### Docker
```bash
# Build
docker build -t xray-ai-service:latest .

# Run
docker-compose up -d

# Logs
docker-compose logs -f xray-service

# Stop
docker-compose down
```

### Kubernetes
```bash
# Deploy
kubectl apply -f infrastructure/kubernetes/base/

# Status
kubectl get pods -n medscan
kubectl get svc -n medscan

# Logs
kubectl logs -f deployment/xray-ai-service -n medscan

# Scale
kubectl scale deployment xray-ai-service --replicas=10 -n medscan
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI application entry point |
| `src/core/config.py` | Configuration management |
| `src/api/routes/predict.py` | Prediction endpoint |
| `src/models/foundation.py` | Medical foundation model |
| `src/services/inference.py` | Inference orchestration |
| `Dockerfile` | Container image definition |
| `docker-compose.yml` | Local development stack |
| `pyproject.toml` | Project configuration |
| `.env.example` | Environment variables template |

---

## 🔗 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/predict` | Disease prediction from X-ray |
| POST | `/explain` | Grad-CAM visualizations |
| POST | `/feedback` | Submit radiologist feedback |
| GET | `/health` | Health check |
| GET | `/readiness` | Kubernetes readiness probe |
| GET | `/liveness` | Kubernetes liveness probe |
| GET | `/model-info` | Model metadata |
| GET | `/metrics` | Prometheus metrics |
| GET | `/docs` | Interactive API documentation |

---

## 🧪 Testing

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# With coverage
pytest --cov=src --cov-report=html

# Specific test
pytest tests/unit/test_preprocessing.py::TestPreprocessingService::test_initialization
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false

# Model
MODEL_VERSION=1.0.0
DEVICE=cpu  # or cuda

# Database
DATABASE_URL=postgresql://user:pass@host:5432/medscan

# Redis
REDIS_URL=redis://host:6379/0
```

See `.env.example` for full list.

---

## 📊 Monitoring

### Prometheus Metrics

```bash
# Scrape metrics
curl http://localhost:8000/metrics

# Key metrics
xray_inference_requests_total
xray_inference_duration_seconds
xray_predictions_total
xray_errors_total
```

### Health Checks

```bash
# Service health
curl http://localhost:8000/health

# Readiness
curl http://localhost:8000/readiness

# Liveness
curl http://localhost:8000/liveness
```

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs xray-service

# Check database
docker-compose ps postgres
docker-compose logs postgres

# Check Redis
docker-compose ps redis
docker-compose logs redis
```

### Model Loading Error

```bash
# Check model path
ls -la models/

# Download models
python scripts/download_models.py

# Check device
python -c "import torch; print(torch.cuda.is_available())"
```

### Database Connection Error

```bash
# Test connection
psql $DATABASE_URL

# Check service
docker-compose ps postgres

# Recreate database
docker-compose down -v
docker-compose up -d postgres
```

---

## 📖 Documentation

| Document | Location |
|----------|----------|
| **Architecture** | `ARCHITECTURE_SUMMARY.md` |
| **Implementation Status** | `IMPLEMENTATION_STATUS.md` |
| **Final Summary** | `FINAL_DELIVERY_SUMMARY.md` |
| **API Docs** | `http://localhost:8000/docs` |
| **Service README** | `services/xray-ai-service/README.md` |
| **Training Pipeline** | `docs/TRAINING_PIPELINE.md` |
| **Production Roadmap** | `docs/PRODUCTION_ROADMAP.md` |

---

## 🔐 Security

### Best Practices Implemented

- ✅ Non-root container user
- ✅ Read-only root filesystem
- ✅ Secrets via environment variables
- ✅ Input validation (Pydantic)
- ✅ Rate limiting
- ✅ CORS configuration
- ✅ PHI redaction in logs

### Security Checklist

- [ ] Use secrets manager (AWS Secrets Manager, Vault)
- [ ] Enable JWT authentication
- [ ] Configure TLS/SSL
- [ ] Set up WAF
- [ ] Enable audit logging
- [ ] Regular security scans
- [ ] Dependency updates

---

## 🎯 Common Tasks

### Add New Disease

1. Update `src/core/config.py` → add to `diseases` list
2. Update `src/models/disease_heads.py` → add head
3. Update `src/services/report.py` → add description
4. Retrain model with new head
5. Deploy new version

### Update Model

1. Train new model
2. Save to MLflow registry
3. Update `MODEL_VERSION` in config
4. Deploy with CI/CD pipeline
5. Monitor performance

### Scale Service

```bash
# Kubernetes
kubectl scale deployment xray-ai-service --replicas=20 -n medscan

# Auto-scaling (HPA)
kubectl autoscale deployment xray-ai-service \
  --cpu-percent=70 \
  --min=3 \
  --max=50 \
  -n medscan
```

---

## 💻 Development

### Code Style

```bash
# Format
black src/ tests/
isort src/ tests/

# Lint
flake8 src/ tests/
mypy src/

# All checks
black --check src/ && isort --check src/ && flake8 src/ && mypy src/
```

### Pre-commit

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## 🚀 Deployment

### CI/CD

Automatic deployment via GitHub Actions:

1. **Push to `main`** → Runs CI tests
2. **Create tag `v*.*.*`** → Deploys to production
3. **Push to `develop`** → Deploys to staging

### Manual Deploy

```bash
# Build image
docker build -t xray-ai-service:v1.0.0 .

# Push to registry
docker push ghcr.io/medvisionn/xray-ai-service:v1.0.0

# Update Kubernetes
kubectl set image deployment/xray-ai-service \
  xray-service=ghcr.io/medvisionn/xray-ai-service:v1.0.0 \
  -n medscan

# Wait for rollout
kubectl rollout status deployment/xray-ai-service -n medscan
```

---

## 📞 Support

**Issues**: [GitHub Issues](https://github.com/MedVisionn/orchestrator-model/issues)  
**Docs**: `docs/` directory  
**Email**: tech@medscanai.com

---

## ⚡ Performance Tips

1. **Use GPU** for faster inference
   - Set `DEVICE=cuda` in config
   - Use GPU-enabled Docker image

2. **Enable ONNX** for 2-3x speedup
   - Export model to ONNX
   - Set `USE_ONNX=true`

3. **Enable Caching**
   - Redis caching enabled by default
   - Adjust `CACHE_TTL` as needed

4. **Batch Processing**
   - Use `/predict/batch` endpoint
   - Group requests when possible

5. **Scale Horizontally**
   - Add more replicas
   - Use HPA for auto-scaling

---

**Last Updated**: 2026-07-22  
**Version**: 1.0.0
