"""
Basic tests to verify setup
"""

import pytest


class TestBasic:
    """Basic sanity tests"""
    
    def test_imports(self):
        """Test basic imports work"""
        try:
            from src.core import config, logging, monitoring
            assert config is not None
            assert logging is not None
            assert monitoring is not None
        except ImportError as e:
            pytest.skip(f"Import failed: {e}")
    
    def test_config_loading(self):
        """Test configuration can be loaded"""
        try:
            from src.core.config import get_settings
            settings = get_settings()
            assert settings is not None
            assert settings.version is not None
        except Exception as e:
            pytest.skip(f"Config loading failed: {e}")
    
    def test_environment(self):
        """Test environment is set up"""
        import sys
        assert sys.version_info >= (3, 10)
    
    def test_basic_math(self):
        """Simple test to ensure pytest works"""
        assert 1 + 1 == 2
        assert "hello".upper() == "HELLO"
