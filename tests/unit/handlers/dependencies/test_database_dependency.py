"""Unit tests for unifiedui/handlers/dependencies/database.py - Database dependency."""
import pytest
import os
from unittest.mock import patch, Mock

from unifiedui.handlers.dependencies.database import get_db_client


class TestGetDbClient:
    """Test suite for get_db_client dependency."""

    def teardown_method(self):
        """Reset global _db_client after each test."""
        import unifiedui.handlers.dependencies.database
        unifiedui.handlers.dependencies.database._db_client = None

    @patch('unifiedui.handlers.dependencies.database.SQLAlchemyClient')
    @patch('unifiedui.handlers.dependencies.database.DatabaseConfig.from_env')
    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"})
    def test_get_db_client_success(self, mock_config, mock_client_class):
        """Test successful database client initialization."""
        mock_config_instance = Mock()
        mock_config.return_value = mock_config_instance
        mock_client_instance = Mock()
        mock_client_class.return_value = mock_client_instance
        
        client = get_db_client()
        
        assert client is mock_client_instance
        mock_config.assert_called_once()
        mock_client_class.assert_called_once_with(config=mock_config_instance)

    @patch('unifiedui.handlers.dependencies.database.SQLAlchemyClient')
    @patch('unifiedui.handlers.dependencies.database.DatabaseConfig.from_env')
    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"})
    def test_get_db_client_cached(self, mock_config, mock_client_class):
        """Test that database client is cached."""
        mock_config_instance = Mock()
        mock_config.return_value = mock_config_instance
        mock_client_instance = Mock()
        mock_client_class.return_value = mock_client_instance
        
        client1 = get_db_client()
        client2 = get_db_client()
        
        assert client1 is client2
        # Config should only be called once due to caching
        assert mock_config.call_count == 1
        assert mock_client_class.call_count == 1

    @patch.dict(os.environ, {}, clear=True)
    def test_get_db_client_missing_config(self):
        """Test error when no database configuration exists."""
        with pytest.raises(RuntimeError) as exc_info:
            get_db_client()
        
        assert "Database configuration is missing" in str(exc_info.value)
        assert "DATABASE_URL" in str(exc_info.value)
        assert "DB_HOST" in str(exc_info.value)

    @patch('unifiedui.handlers.dependencies.database.SQLAlchemyClient')
    @patch('unifiedui.handlers.dependencies.database.DatabaseConfig.from_env')
    @patch.dict(os.environ, {"DB_HOST": "localhost", "DB_PORT": "5432"})
    def test_get_db_client_init_failure(self, mock_config, mock_client_class):
        """Test handling of database client initialization failure."""
        mock_config.return_value = Mock()
        mock_client_class.side_effect = Exception("Connection failed")
        
        with pytest.raises(RuntimeError) as exc_info:
            get_db_client()
        
        assert "Failed to initialize database client" in str(exc_info.value)
        assert "Connection failed" in str(exc_info.value)

    @patch('unifiedui.handlers.dependencies.database.SQLAlchemyClient')
    @patch('unifiedui.handlers.dependencies.database.DatabaseConfig.from_env')
    @patch.dict(os.environ, {"DB_HOST": "localhost"})
    def test_get_db_client_with_db_host(self, mock_config, mock_client_class):
        """Test database client initialization with DB_HOST."""
        mock_config_instance = Mock()
        mock_config.return_value = mock_config_instance
        mock_client_instance = Mock()
        mock_client_class.return_value = mock_client_instance
        
        client = get_db_client()
        
        assert client is mock_client_instance
        mock_config.assert_called_once()
