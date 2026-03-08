"""Unit tests for unifiedui/identity/aws_cognito/provider.py - AWS Cognito Identity Provider."""

from unittest.mock import MagicMock, patch

from unifiedui.identity.aws_cognito.provider import AWSCognitoIdentityProvider
from unifiedui.identity.aws_cognito.token import AWSCognitoIdentityTokenSerializer
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class TestAWSCognitoIdentityProvider:
    """Test suite for AWSCognitoIdentityProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deserialized = {
            "sub": "cognito-user-123",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "email": "user@company.com",
            "name": "Test User",
            "cognito:username": "testuser",
        }
        self.token = AWSCognitoIdentityTokenSerializer("cognito-token", self.deserialized)

    def test_initialization(self):
        """Test provider initialization."""
        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_TestPool",
        )

        assert provider.identity_token == self.token
        assert provider._aws_region == "us-east-1"
        assert provider._user_pool_id == "us-east-1_TestPool"
        assert provider._boto_client is None

    def test_initialization_with_credentials(self):
        """Test provider initialization with explicit AWS credentials."""
        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="eu-west-1",
            user_pool_id="eu-west-1_Pool",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )

        assert provider._aws_access_key_id == "AKIAIOSFODNN7EXAMPLE"
        assert provider._aws_secret_access_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

    @patch("unifiedui.identity.aws_cognito.provider.boto3", create=True)
    def test_get_boto_client_lazy_init(self, mock_boto3_module):
        """Test that boto3 client is lazily initialized."""
        mock_client = MagicMock()
        mock_boto3_module.client.return_value = mock_client

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_TestPool",
        )

        with patch.dict("sys.modules", {"boto3": mock_boto3_module}):
            client = provider._get_boto_client()

        assert client is not None

    def test_get_current_user_security_groups(self):
        """Test getting groups for the current user."""
        mock_client = MagicMock()
        mock_client.admin_list_groups_for_user.return_value = {
            "Groups": [
                {"GroupName": "admins", "Description": "Admin Group"},
                {"GroupName": "developers", "Description": "Developer Group"},
            ]
        }

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_TestPool",
        )
        provider._boto_client = mock_client

        result = provider.get_current_user_security_groups()

        assert len(result) == 2
        assert isinstance(result[0], IdentityGroupResponse)
        assert result[0].id == "admins"
        assert result[0].display_name == "Admin Group"
        assert result[1].id == "developers"

        mock_client.admin_list_groups_for_user.assert_called_once_with(
            UserPoolId="us-east-1_TestPool",
            Username="user@company.com",
        )

    def test_get_current_user_security_groups_no_username(self):
        """Test getting groups returns empty when no principal name."""
        empty_token = AWSCognitoIdentityTokenSerializer("token", {"sub": "user-123"})
        provider = AWSCognitoIdentityProvider(
            identity_token=empty_token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )

        result = provider.get_current_user_security_groups()

        assert result == []

    def test_get_current_user_security_groups_api_error(self):
        """Test getting groups returns empty on API error."""
        mock_client = MagicMock()
        mock_client.admin_list_groups_for_user.side_effect = Exception("Access denied")

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        result = provider.get_current_user_security_groups()

        assert result == []

    def test_get_security_groups(self):
        """Test listing all groups in the user pool."""
        mock_client = MagicMock()
        mock_client.list_groups.return_value = {
            "Groups": [
                {"GroupName": "admins", "Description": "Admin Group"},
                {"GroupName": "users", "Description": "Regular Users"},
            ],
            "NextToken": "next-page-token",
        }

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        groups, next_token = provider.get_security_groups()

        assert len(groups) == 2
        assert next_token == "next-page-token"
        assert groups[0].id == "admins"

    def test_get_security_groups_with_pagination(self):
        """Test listing groups with pagination query."""
        mock_client = MagicMock()
        mock_client.list_groups.return_value = {"Groups": [{"GroupName": "team-a", "Description": "Team A"}]}

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        query = APIFilterQuery(top=10, next_link="prev-token")
        groups, _ = provider.get_security_groups(query=query)

        assert len(groups) == 1
        mock_client.list_groups.assert_called_once_with(
            UserPoolId="us-east-1_Pool",
            Limit=10,
            NextToken="prev-token",
        )

    def test_get_security_groups_api_error(self):
        """Test listing groups returns empty on API error."""
        mock_client = MagicMock()
        mock_client.list_groups.side_effect = Exception("Error")

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        groups, next_token = provider.get_security_groups()

        assert groups == []
        assert next_token is None

    def test_get_users(self):
        """Test listing users in the user pool."""
        mock_client = MagicMock()
        mock_client.list_users.return_value = {
            "Users": [
                {
                    "Username": "alice",
                    "Attributes": [
                        {"Name": "sub", "Value": "sub-alice"},
                        {"Name": "email", "Value": "alice@company.com"},
                        {"Name": "name", "Value": "Alice Smith"},
                    ],
                },
                {
                    "Username": "bob",
                    "Attributes": [
                        {"Name": "sub", "Value": "sub-bob"},
                        {"Name": "email", "Value": "bob@company.com"},
                    ],
                },
            ],
            "PaginationToken": "user-page-2",
        }

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        users, next_token = provider.get_users()

        assert len(users) == 2
        assert isinstance(users[0], IdentityUserResponse)
        assert users[0].display_name == "Alice Smith"
        assert next_token == "user-page-2"

    def test_get_users_with_search(self):
        """Test listing users with email search filter."""
        mock_client = MagicMock()
        mock_client.list_users.return_value = {
            "Users": [
                {
                    "Username": "alice",
                    "Attributes": [
                        {"Name": "sub", "Value": "sub-alice"},
                        {"Name": "email", "Value": "alice@company.com"},
                    ],
                }
            ]
        }

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        query = APIFilterQuery(search="alice", top=5)
        users, _ = provider.get_users(query=query)

        assert len(users) == 1
        mock_client.list_users.assert_called_once_with(
            UserPoolId="us-east-1_Pool",
            Limit=5,
            Filter='email ^= "alice"',
        )

    def test_get_users_api_error(self):
        """Test listing users returns empty on API error."""
        mock_client = MagicMock()
        mock_client.list_users.side_effect = Exception("Error")

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        users, next_token = provider.get_users()

        assert users == []
        assert next_token is None

    def test_get_user_by_id(self):
        """Test getting a single user by username."""
        mock_client = MagicMock()
        mock_client.admin_get_user.return_value = {
            "Username": "alice",
            "UserAttributes": [
                {"Name": "sub", "Value": "sub-alice"},
                {"Name": "email", "Value": "alice@company.com"},
                {"Name": "name", "Value": "Alice Smith"},
                {"Name": "given_name", "Value": "Alice"},
                {"Name": "family_name", "Value": "Smith"},
            ],
        }

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        user = provider.get_user_by_id("alice")

        assert isinstance(user, IdentityUserResponse)
        assert user.id == "sub-alice"
        assert user.display_name == "Alice Smith"
        assert user.mail == "alice@company.com"
        assert user.firstname == "Alice"
        assert user.lastname == "Smith"

    def test_get_group_by_id(self):
        """Test getting a single group by name."""
        mock_client = MagicMock()
        mock_client.get_group.return_value = {
            "Group": {
                "GroupName": "admins",
                "Description": "Admin Group",
                "UserPoolId": "us-east-1_Pool",
            }
        }

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        group = provider.get_group_by_id("admins")

        assert isinstance(group, IdentityGroupResponse)
        assert group.id == "admins"
        assert group.display_name == "Admin Group"

    def test_get_security_groups_limit_capped_at_60(self):
        """Test that group listing limit is capped at 60 (Cognito API limit)."""
        mock_client = MagicMock()
        mock_client.list_groups.return_value = {"Groups": []}

        provider = AWSCognitoIdentityProvider(
            identity_token=self.token,
            aws_region="us-east-1",
            user_pool_id="us-east-1_Pool",
        )
        provider._boto_client = mock_client

        query = APIFilterQuery(top=100)
        provider.get_security_groups(query=query)

        mock_client.list_groups.assert_called_once_with(
            UserPoolId="us-east-1_Pool",
            Limit=60,
        )
