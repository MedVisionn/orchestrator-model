"""
Prometheus metrics for monitoring and observability
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# Service Information
service_info = Info("xray_service", "X-Ray AI Service information")
service_info.info({
    "version": "1.0.0",
    "service": "xray-ai-service",
    "description": "Chest X-ray disease detection service"
})

# Service Health
service_starts = Counter(
    "xray_service_starts_total",
    "Total number of service starts"
)

service_uptime = Gauge(
    "xray_service_uptime_seconds",
    "Service uptime in seconds"
)

# Request Metrics
requests_total = Counter(
    "xray_requests_total",
    "Total number of requests",
    ["endpoint", "method", "status"]
)

requests_in_progress = Gauge(
    "xray_requests_in_progress",
    "Number of requests currently being processed",
    ["endpoint"]
)

request_duration = Histogram(
    "xray_request_duration_seconds",
    "Request duration in seconds",
    ["endpoint", "method"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

# Inference Metrics
inference_requests = Counter(
    "xray_inference_requests_total",
    "Total number of inference requests",
    ["model_version"]
)

inference_duration = Histogram(
    "xray_inference_duration_seconds",
    "Inference duration in seconds",
    ["model_version", "device"],
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0)
)

preprocessing_duration = Histogram(
    "xray_preprocessing_duration_seconds",
    "Preprocessing duration in seconds",
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1.0)
)

postprocessing_duration = Histogram(
    "xray_postprocessing_duration_seconds",
    "Postprocessing duration in seconds",
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1.0)
)

# Prediction Metrics
predictions_total = Counter(
    "xray_predictions_total",
    "Total predictions by disease and label",
    ["disease", "label"]
)

prediction_confidence = Histogram(
    "xray_prediction_confidence",
    "Prediction confidence scores",
    ["disease"],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)

high_confidence_predictions = Counter(
    "xray_high_confidence_predictions_total",
    "Predictions with confidence > 0.8",
    ["disease"]
)

low_confidence_predictions = Counter(
    "xray_low_confidence_predictions_total",
    "Predictions with confidence < 0.6",
    ["disease"]
)

# Explainability Metrics
gradcam_requests = Counter(
    "xray_gradcam_requests_total",
    "Total Grad-CAM generation requests"
)

gradcam_duration = Histogram(
    "xray_gradcam_duration_seconds",
    "Grad-CAM generation duration",
    buckets=(0.1, 0.2, 0.5, 1.0, 2.0, 5.0)
)

# Feedback Metrics
feedback_total = Counter(
    "xray_feedback_total",
    "Total feedback submissions",
    ["radiologist_id"]
)

feedback_agreement = Counter(
    "xray_feedback_agreement_total",
    "Agreement between model and radiologist",
    ["disease", "agreement"]
)

feedback_quality_rating = Histogram(
    "xray_feedback_quality_rating",
    "Quality ratings from radiologists",
    buckets=(1, 2, 3, 4, 5)
)

# Cache Metrics
cache_hits = Counter(
    "xray_cache_hits_total",
    "Total cache hits"
)

cache_misses = Counter(
    "xray_cache_misses_total",
    "Total cache misses"
)

cache_size = Gauge(
    "xray_cache_size_bytes",
    "Current cache size in bytes"
)

# Error Metrics
errors = Counter(
    "xray_errors_total",
    "Total errors by type",
    ["error_type"]
)

inference_failures = Counter(
    "xray_inference_failures_total",
    "Failed inferences by reason",
    ["reason"]
)

# Model Metrics
model_loaded = Gauge(
    "xray_model_loaded",
    "Whether model is loaded (1=loaded, 0=not loaded)"
)

model_memory_usage = Gauge(
    "xray_model_memory_bytes",
    "Model memory usage in bytes"
)

model_version_info = Info(
    "xray_model_version",
    "Current model version information"
)

# Database Metrics
db_connection_pool_size = Gauge(
    "xray_db_connection_pool_size",
    "Database connection pool size"
)

db_connection_pool_available = Gauge(
    "xray_db_connection_pool_available",
    "Available database connections"
)

db_query_duration = Histogram(
    "xray_db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)
)

# File Upload Metrics
file_uploads = Counter(
    "xray_file_uploads_total",
    "Total file uploads",
    ["file_type", "status"]
)

file_size = Histogram(
    "xray_file_size_bytes",
    "Uploaded file sizes",
    ["file_type"],
    buckets=(1024, 10240, 102400, 1024000, 10240000)
)

# Resource Metrics
cpu_usage = Gauge(
    "xray_cpu_usage_percent",
    "CPU usage percentage"
)

memory_usage = Gauge(
    "xray_memory_usage_bytes",
    "Memory usage in bytes"
)

gpu_memory_usage = Gauge(
    "xray_gpu_memory_usage_bytes",
    "GPU memory usage in bytes"
)

# Data Quality Metrics
invalid_inputs = Counter(
    "xray_invalid_inputs_total",
    "Invalid input files",
    ["reason"]
)

image_quality_warnings = Counter(
    "xray_image_quality_warnings_total",
    "Image quality warnings",
    ["warning_type"]
)


class MetricsCollector:
    """Utility class for collecting and managing metrics"""
    
    @staticmethod
    def record_inference(
        model_version: str,
        device: str,
        duration: float,
        predictions: dict,
    ) -> None:
        """Record inference metrics"""
        inference_requests.labels(model_version=model_version).inc()
        inference_duration.labels(
            model_version=model_version,
            device=device
        ).observe(duration)
        
        # Record predictions
        for disease, result in predictions.items():
            label = result.get("label", "unknown")
            confidence = result.get("confidence", 0.0)
            
            predictions_total.labels(disease=disease, label=label).inc()
            prediction_confidence.labels(disease=disease).observe(confidence)
            
            if confidence > 0.8:
                high_confidence_predictions.labels(disease=disease).inc()
            elif confidence < 0.6:
                low_confidence_predictions.labels(disease=disease).inc()
    
    @staticmethod
    def record_feedback(
        radiologist_id: str,
        predictions: dict,
        ground_truth: dict,
        quality_rating: int,
    ) -> None:
        """Record feedback metrics"""
        feedback_total.labels(radiologist_id=radiologist_id).inc()
        feedback_quality_rating.observe(quality_rating)
        
        # Record agreement
        for disease in predictions.keys():
            if disease in ground_truth:
                model_pred = predictions[disease].get("label") == "positive"
                actual = ground_truth[disease]
                agreement = "agree" if model_pred == actual else "disagree"
                feedback_agreement.labels(disease=disease, agreement=agreement).inc()
    
    @staticmethod
    def record_cache_access(hit: bool) -> None:
        """Record cache access"""
        if hit:
            cache_hits.inc()
        else:
            cache_misses.inc()
    
    @staticmethod
    def record_error(error_type: str) -> None:
        """Record error"""
        errors.labels(error_type=error_type).inc()


# Global metrics collector instance
metrics = MetricsCollector()
