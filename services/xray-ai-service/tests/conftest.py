"""
Pytest configuration and fixtures
Shared test utilities and setup
"""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.database.connection import Base, get_db
from src.main import app


# =============================================================================
# Pytest Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Application Fixtures
# =============================================================================

@pytest.fixture
def test_app():
    """Get FastAPI test application"""
    return app


@pytest.fixture
def client(test_app) -> TestClient:
    """Get test client for sync tests"""
    return TestClient(test_app)


@pytest.fixture
async def async_client(test_app) -> AsyncGenerator:
    """Get async test client"""
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/medscan_test",
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for tests"""
    async_session_maker = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def override_get_db(db_session):
    """Override database dependency"""
    async def _get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_model():
    """Mock ML model"""
    model = MagicMock()
    model.eval.return_value = None
    return model


@pytest.fixture
def mock_inference_service():
    """Mock inference service"""
    service = MagicMock()
    return service


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    return redis_mock


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_xray_image() -> bytes:
    """Sample X-ray image (placeholder)"""
    # In real tests, load actual test images
    return b"fake_image_data"


@pytest.fixture
def sample_dicom_file() -> bytes:
    """Sample DICOM file (placeholder)"""
    # In real tests, load actual DICOM files
    return b"fake_dicom_data"


@pytest.fixture
def sample_prediction_response():
    """Sample prediction response"""
    return {
        "request_id": "test_req_123",
        "patient_id": "P12345",
        "study_id": "S67890",
        "model_version": "1.0.0",
        "predictions": {
            "pneumonia": {
                "probability": 0.78,
                "confidence": 0.82,
                "label": "positive",
                "threshold": 0.5,
            },
            "tuberculosis": {
                "probability": 0.12,
                "confidence": 0.88,
                "label": "negative",
                "threshold": 0.3,
            },
        },
        "clinical_report": {
            "impression": "Findings suggestive of pneumonia.",
            "findings": ["Consolidation in right lower lobe"],
            "recommendations": ["Clinical correlation recommended"],
            "limitations": "AI-assisted analysis",
        },
        "metadata": {
            "inference_time_ms": 245.0,
            "preprocessing_time_ms": 68.0,
            "model_time_ms": 156.0,
            "postprocessing_time_ms": 21.0,
        },
    }


@pytest.fixture
def sample_feedback_request():
    """Sample feedback request"""
    return {
        "request_id": "test_req_123",
        "radiologist_id": "R789",
        "ground_truth": {
            "pneumonia": True,
            "tuberculosis": False,
            "cardiomegaly": False,
            "pleural_effusion": False,
            "edema": False,
            "fracture": False,
        },
        "comments": "Confirmed pneumonia",
        "quality_rating": 4,
    }


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def test_config(monkeypatch):
    """Override configuration for tests"""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/medscan_test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("ENABLE_CACHE", "false")
    monkeypatch.setenv("ENABLE_AUTH", "false")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


# =============================================================================
# Cleanup Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Cleanup after each test"""
    yield
    # Add any cleanup logic here
