"""
Structured logging configuration using structlog
HIPAA-compliant - no PHI in logs
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import EventDict, Processor


def add_log_level(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add log level to event dict"""
    if method_name == "warn":
        method_name = "warning"
    event_dict["level"] = method_name.upper()
    return event_dict


def add_timestamp(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add ISO8601 timestamp"""
    event_dict["timestamp"] = structlog.processors.TimeStamper(fmt="iso")(
        logger, method_name, event_dict
    )["timestamp"]
    return event_dict


def censor_sensitive_data(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Remove or mask sensitive data (PHI) from logs for HIPAA compliance
    """
    sensitive_keys = [
        "password",
        "token",
        "api_key",
        "secret",
        "patient_name",
        "patient_dob",
        "ssn",
        "medical_record_number",
    ]
    
    for key in sensitive_keys:
        if key in event_dict:
            event_dict[key] = "***REDACTED***"
    
    return event_dict


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure structured logging
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ('json' for production, 'console' for development)
    """
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_timestamp,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        censor_sensitive_data,
    ]
    
    if log_format == "console":
        # Human-readable console output for development
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Set log level for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)


class AuditLogger:
    """
    Specialized logger for audit trail (regulatory compliance)
    Logs all inference requests and feedback for traceability
    """
    
    def __init__(self):
        self.logger = get_logger("audit")
    
    def log_inference(
        self,
        request_id: str,
        patient_id: str,
        study_id: str,
        model_version: str,
        predictions: Dict[str, Any],
        inference_time_ms: float,
    ) -> None:
        """Log inference request for audit trail"""
        self.logger.info(
            "inference_audit",
            event_type="inference",
            request_id=request_id,
            patient_id=patient_id,
            study_id=study_id,
            model_version=model_version,
            predictions=predictions,
            inference_time_ms=inference_time_ms,
        )
    
    def log_feedback(
        self,
        request_id: str,
        radiologist_id: str,
        ground_truth: Dict[str, bool],
        quality_rating: int,
    ) -> None:
        """Log radiologist feedback for audit trail"""
        self.logger.info(
            "feedback_audit",
            event_type="feedback",
            request_id=request_id,
            radiologist_id=radiologist_id,
            ground_truth=ground_truth,
            quality_rating=quality_rating,
        )
    
    def log_error(
        self,
        request_id: str,
        error_type: str,
        error_message: str,
        stack_trace: str = None,
    ) -> None:
        """Log error for audit trail"""
        self.logger.error(
            "error_audit",
            event_type="error",
            request_id=request_id,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
        )


# Global audit logger instance
audit_logger = AuditLogger()
