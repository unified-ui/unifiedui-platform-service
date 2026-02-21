"""Unit tests for unifiedui/utils/api_client.py"""

from unifiedui.utils.api_client import APIJSONBearerClient


class TestAPIJSONBearerClient:
    """Test suite for APIJSONBearerClient."""

    def test_init_sets_base_url(self):
        """Test that initialization sets the base URL correctly."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        assert client._base_url == base_url

    def test_url_with_leading_slash(self):
        """Test _url() method with endpoint having leading slash."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        endpoint = "/users/123"
        result = client._url(endpoint)

        assert result == "https://api.example.com/users/123"

    def test_url_without_leading_slash(self):
        """Test _url() method with endpoint without leading slash."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        endpoint = "users/123"
        result = client._url(endpoint)

        assert result == "https://api.example.com/users/123"

    def test_url_with_trailing_slash_in_base_url(self):
        """Test _url() method when base URL has trailing slash."""
        base_url = "https://api.example.com/"
        client = APIJSONBearerClient(base_url)

        endpoint = "/users/123"
        result = client._url(endpoint)

        assert result == "https://api.example.com//users/123"

    def test_url_with_empty_endpoint(self):
        """Test _url() method with empty endpoint."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        endpoint = ""
        result = client._url(endpoint)

        assert result == "https://api.example.com/"

    def test_url_with_complex_endpoint(self):
        """Test _url() method with complex endpoint path."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        endpoint = "/v1/tenants/abc123/users/456"
        result = client._url(endpoint)

        assert result == "https://api.example.com/v1/tenants/abc123/users/456"

    def test_get_headers_returns_correct_structure(self):
        """Test that _get_headers() returns correct header structure."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        token = "test-token-123"
        headers = client._get_headers(token)

        assert isinstance(headers, dict)
        assert "Authorization" in headers
        assert "Content-Type" in headers

    def test_get_headers_includes_bearer_prefix(self):
        """Test that _get_headers() includes 'Bearer' prefix."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        token = "test-token-123"
        headers = client._get_headers(token)

        assert headers["Authorization"] == "Bearer test-token-123"

    def test_get_headers_sets_json_content_type(self):
        """Test that _get_headers() sets JSON content type."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        token = "test-token-123"
        headers = client._get_headers(token)

        assert headers["Content-Type"] == "application/json"

    def test_get_headers_with_empty_token(self):
        """Test _get_headers() with empty token."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        token = ""
        headers = client._get_headers(token)

        assert headers["Authorization"] == "Bearer "
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_with_long_token(self):
        """Test _get_headers() with very long token."""
        base_url = "https://api.example.com"
        client = APIJSONBearerClient(base_url)

        token = "a" * 1000  # Very long token
        headers = client._get_headers(token)

        assert headers["Authorization"] == f"Bearer {token}"
        assert len(headers["Authorization"]) == 1007  # "Bearer " + 1000 chars
