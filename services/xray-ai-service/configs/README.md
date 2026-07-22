# Configuration Files

This directory contains YAML configuration files for the X-Ray AI Service.

## Files

### config.yaml
Main application configuration including:
- Server settings (host, port, workers)
- Model configuration (device, batch size, precision)
- Feature flags
- Monitoring settings
- Security settings
- Cache configuration

Environment variables override these settings.

### diseases.yaml
Disease-specific configuration including:
- Classification thresholds
- Clinical significance levels
- ICD-10 codes
- Common findings
- Follow-up recommendations
- ROI focus areas for explainability

### prompts.yaml
Report generation templates including:
- Clinical report templates per disease
- System prompts for AI report generation
- Differential diagnoses
- Follow-up recommendations
- FHIR mappings
- Severity descriptors

## Usage

These files are automatically loaded by the application at startup. You can override specific settings using environment variables:

```bash
# Override model device
export DEVICE=cuda

# Override log level
export LOG_LEVEL=DEBUG

# Override cache TTL
export CACHE_TTL=7200
```

## Configuration Priority

1. Environment variables (highest priority)
2. YAML configuration files
3. Default values in code (lowest priority)

## Production Deployment

In production:
- Store sensitive values (SECRET_KEY, DATABASE_URL, REDIS_URL) in environment variables or secrets manager
- Do not commit sensitive data to version control
- Use different config files per environment (dev, staging, prod)
- Consider using Kubernetes ConfigMaps and Secrets for K8s deployments

## Validation

Configuration is validated at startup using Pydantic models in `src/core/config.py`.
Invalid configurations will prevent the application from starting.

## Example: Custom Disease Threshold

To adjust the threshold for pneumonia detection:

```yaml
# diseases.yaml
diseases:
  pneumonia:
    threshold: 0.6  # Change from default 0.5 to 0.6
```

## Example: Enable GPU Inference

```yaml
# config.yaml
model:
  device: cuda
  use_amp: true  # Enable automatic mixed precision
```
