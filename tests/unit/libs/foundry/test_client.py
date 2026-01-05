"""Tests for Microsoft Foundry client."""
import pytest
from unittest.mock import patch, Mock
import requests

from unifiedui.libs.foundry.client import (
    MicrosoftFoundryClient,
    MicrosoftFoundryError,
)


class TestMicrosoftFoundryClient:
    """Tests for MicrosoftFoundryClient."""
    
    def test_init(self):
        """Test client initialization."""
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="test-token",
            api_version="2025-11-15-preview"
        )
        
        assert client.project_endpoint == "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2"
        assert client.api_token == "test-token"
        assert client.api_version == "2025-11-15-preview"
        assert client.headers["Authorization"] == "Bearer test-token"
        assert client.headers["Content-Type"] == "application/json"
    
    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from endpoint."""
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2/",
            api_token="test-token"
        )
        
        assert client.project_endpoint == "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2"
    
    def test_init_default_api_version(self):
        """Test default API version."""
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="test-token"
        )
        
        assert client.api_version == "2025-11-15-preview"
    
    @patch('unifiedui.libs.foundry.client.requests.post')
    def test_create_conversation_success(self, mock_post):
        """Test successful conversation creation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "conv_12345",
            "object": "conversation",
            "created_at": 1767639772,
            "metadata": {}
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="test-token"
        )
        
        result = client.create_conversation()
        
        assert result["id"] == "conv_12345"
        assert result["object"] == "conversation"
        
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "openai/conversations" in call_args[0][0]
        assert "api-version=2025-11-15-preview" in call_args[0][0]
    
    @patch('unifiedui.libs.foundry.client.requests.post')
    def test_create_conversation_with_metadata(self, mock_post):
        """Test conversation creation with metadata."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "conv_12345",
            "metadata": {"custom": "data"}
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="test-token"
        )
        
        result = client.create_conversation(metadata={"custom": "data"})
        
        assert result["id"] == "conv_12345"
        call_args = mock_post.call_args
        assert call_args[1]["json"] == {"custom": "data"}
    
    @patch('unifiedui.libs.foundry.client.requests.post')
    def test_create_conversation_http_error(self, mock_post):
        """Test conversation creation with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value = mock_response
        
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="invalid-token"
        )
        
        with pytest.raises(MicrosoftFoundryError) as exc_info:
            client.create_conversation()
        
        assert exc_info.value.status_code == 401
        assert "HTTP 401" in exc_info.value.message
    
    @patch('unifiedui.libs.foundry.client.requests.post')
    def test_create_conversation_request_exception(self, mock_post):
        """Test conversation creation with request exception."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="test-token"
        )
        
        with pytest.raises(MicrosoftFoundryError) as exc_info:
            client.create_conversation()
        
        assert "Connection refused" in exc_info.value.message
    
    @patch('unifiedui.libs.foundry.client.requests.post')
    def test_get_conversation_id_success(self, mock_post):
        """Test get_conversation_id returns just the ID."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "conv_12345",
            "object": "conversation"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="test-token"
        )
        
        result = client.get_conversation_id()
        
        assert result == "conv_12345"
    
    @patch('unifiedui.libs.foundry.client.requests.post')
    def test_get_conversation_id_missing_id(self, mock_post):
        """Test get_conversation_id raises error when ID is missing."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "object": "conversation"
            # No id field
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = MicrosoftFoundryClient(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="test-token"
        )
        
        with pytest.raises(MicrosoftFoundryError) as exc_info:
            client.get_conversation_id()
        
        assert "missing conversation ID" in exc_info.value.message


class TestMicrosoftFoundryError:
    """Tests for MicrosoftFoundryError."""
    
    def test_error_with_all_fields(self):
        """Test error with all fields."""
        error = MicrosoftFoundryError(
            message="Test error",
            status_code=500,
            response_body='{"error": "Internal error"}'
        )
        
        assert error.message == "Test error"
        assert error.status_code == 500
        assert error.response_body == '{"error": "Internal error"}'
        assert str(error) == "Test error"
    
    def test_error_with_minimal_fields(self):
        """Test error with only message."""
        error = MicrosoftFoundryError(message="Simple error")
        
        assert error.message == "Simple error"
        assert error.status_code is None
        assert error.response_body is None
