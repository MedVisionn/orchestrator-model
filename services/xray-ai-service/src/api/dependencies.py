"""
FastAPI dependencies for dependency injection
"""

from typing import Optional

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.redis_client import get_redis_client, RedisClient
from src.core.config import get_settings
from src.database.connection import get_db
from src.models.model_loader import get_model_loader
from src.services.inference import InferenceService
from src.services.preprocessing import PreprocessingService

settings = get_settings()


async def get_preprocessing_service() -> PreprocessingService:
    """Get preprocessing service instance"""
    return PreprocessingService()


async def get_inference_service() -> InferenceService:
    """Get inference service instance"""
    return InferenceService()


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Get current user from JWT token
    Returns None if auth is disabled
    """
    if not settings.enable_auth:
        return None
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    
    # Parse JWT token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
            )
        
        # TODO: Validate JWT token and extract user
        # For now, return a placeholder
        user_id = "user_placeholder"
        
        return user_id
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )


async def get_api_key(
    x_api_key: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Validate API key
    Returns None if auth is disabled
    """
    if not settings.enable_auth:
        return None
    
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    
    # TODO: Validate API key against database
    # For now, accept any non-empty key
    
    return x_api_key


async def check_rate_limit(
    redis: RedisClient = Depends(get_redis_client),
    api_key: Optional[str] = Depends(get_api_key),
) -> None:
    """
    Check rate limit for the current user/API key
    """
    if not settings.enable_rate_limit:
        return
    
    # Use API key or IP as identifier
    identifier = api_key or "default"
    
    # Check rate limit
    key = f"rate_limit:{identifier}"
    
    try:
        current = await redis.incr(key)
        
        if current == 1:
            # First request, set expiry
            await redis.expire(key, settings.rate_limit_window)
        
        if current > settings.rate_limit_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {settings.rate_limit_requests} requests per {settings.rate_limit_window} seconds",
            )
    except Exception as e:
        # If Redis is down, allow the request
        pass


async def validate_file_size(
    content_length: int = Header(...),
) -> None:
    """Validate uploaded file size"""
    if content_length > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.max_file_size_mb}MB",
        )
