"""
Custom middleware for request/response processing
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.logging import get_logger
from src.core.monitoring import request_duration, requests_in_progress, requests_total

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        
        # Store in request state
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Track request timing and record metrics"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract endpoint
        endpoint = request.url.path
        method = request.method
        
        # Increment in-progress counter
        requests_in_progress.labels(endpoint=endpoint).inc()
        
        # Start timer
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            request_duration.labels(
                endpoint=endpoint,
                method=method,
            ).observe(duration)
            
            requests_total.labels(
                endpoint=endpoint,
                method=method,
                status=response.status_code,
            ).inc()
            
            # Add timing header
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            return response
            
        finally:
            # Decrement in-progress counter
            requests_in_progress.labels(endpoint=endpoint).dec()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get request ID
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log request
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )
        
        # Process request
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration * 1000,
            )
            
            return response
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            
            logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=duration * 1000,
                exc_info=True,
            )
            
            raise
