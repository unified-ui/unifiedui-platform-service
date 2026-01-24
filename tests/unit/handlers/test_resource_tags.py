"""Tests for ResourceTagsHandler."""
import uuid
import pytest
from unittest.mock import Mock, patch

from unifiedui.handlers.resource_tags import (
    ResourceTagsHandler,
    RESOURCE_TAG_CONFIG
)
from unifiedui.core.database.models import (
    Tenant, Principal, Application, ApplicationTag, Tag,
    Credential, CredentialTag, AutonomousAgent, AutonomousAgentTag
)
from unifiedui.core.database.enums import PrincipalTypeEnum


class TestResourceTagsHandlerConfig:
    """Tests for ResourceTagsHandler configuration."""
    
    def test_supported_resource_types(self):
        """Test that all expected resource types are configured."""
        expected_types = [
            "application", "autonomous_agent", "chat_widget",
            "credential"
        ]
        for resource_type in expected_types:
            assert resource_type in RESOURCE_TAG_CONFIG

    def test_invalid_resource_type_raises_error(self, test_db_client, test_cache_client):
        """Test that invalid resource type raises ValueError."""
        handler = ResourceTagsHandler(
            db_client=test_db_client,
            cache_client=test_cache_client
        )
        
        with pytest.raises(ValueError, match="Unknown resource type"):
            handler._get_config("invalid_type")
    
    def test_get_supported_resource_types(self):
        """Test getting list of supported resource types."""
        types = ResourceTagsHandler.get_supported_resource_types()
        
        assert "application" in types
        assert "credential" in types
        assert len(types) == 4  # 4 resource types support tags


class TestResourceTagsHandlerOperations:
    """Tests for ResourceTagsHandler CRUD operations."""
    
    @pytest.fixture
    def handler(self, test_db_client, test_cache_client):
        """Create handler instance."""
        return ResourceTagsHandler(
            db_client=test_db_client,
            cache_client=test_cache_client
        )
    
    @pytest.fixture
    def setup_tenant_and_application(self, test_db_client, test_db_session):
        """Create a tenant and application for testing."""
        tenant_id = str(uuid.uuid4())
        user_id = f"test-user-{str(uuid.uuid4())[:8]}"
        application_id = str(uuid.uuid4())
        
        # Create tenant
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            description="Test Description",
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(tenant)
        
        # Create principal for user
        principal = Principal(
            tenant_id=tenant_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
            display_name="Test User",
            principal_name="test@example.com",
            mail="test@example.com"
        )
        test_db_session.add(principal)
        
        # Create application
        application = Application(
            id=application_id,
            tenant_id=tenant_id,
            name="Test Application",
            description="Test Description",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(application)
        test_db_session.commit()
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "application_id": application_id
        }
    
    def test_get_resource_tags_empty(self, handler, setup_tenant_and_application):
        """Test getting tags when none exist."""
        data = setup_tenant_and_application
        
        result = handler.get_resource_tags(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=False
        )
        
        assert result["resource_id"] == data["application_id"]
        assert result["resource_type"] == "application"
        assert result["tenant_id"] == data["tenant_id"]
        assert result["tags"] == []
    
    def test_get_resource_tags_resource_not_found(self, handler, setup_tenant_and_application):
        """Test getting tags for non-existent resource."""
        data = setup_tenant_and_application
        
        with pytest.raises(ValueError, match="not found"):
            handler.get_resource_tags(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id="non-existent-id",
                use_cache=False
            )
    
    def test_add_resource_tag(self, handler, setup_tenant_and_application):
        """Test adding a tag to a resource."""
        data = setup_tenant_and_application
        
        # Create mock user
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        result = handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="TEST-TAG",
            user=mock_user
        )
        
        assert result["name"] == "TEST-TAG"
        assert result["id"] is not None
        
        # Verify tag is listed
        tags_result = handler.get_resource_tags(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=False
        )
        
        assert len(tags_result["tags"]) == 1
        assert tags_result["tags"][0]["name"] == "TEST-TAG"
    
    def test_add_resource_tag_creates_new_tag(self, handler, setup_tenant_and_application, test_db_session):
        """Test that adding a tag creates the tag if it doesn't exist."""
        data = setup_tenant_and_application
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        # Add tag
        result = handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="new-tag",
            user=mock_user
        )
        
        # Verify tag was created in database
        from sqlalchemy import select
        tag = test_db_session.execute(
            select(Tag).where(
                Tag.tenant_id == data["tenant_id"],
                Tag.name == "NEW-TAG"  # Tag names are automatically converted to uppercase
            )
        ).scalar_one_or_none()
        
        assert tag is not None
        assert tag.id == result["id"]
    
    def test_add_resource_tag_reuses_existing_tag(self, handler, setup_tenant_and_application, test_db_session):
        """Test that adding an existing tag reuses it."""
        data = setup_tenant_and_application
        
        # Create tag first
        tag = Tag(
            tenant_id=data["tenant_id"],
            name="EXISTING-TAG",
            created_by=data["user_id"],
            updated_by=data["user_id"]
        )
        test_db_session.add(tag)
        test_db_session.commit()
        tag_id = tag.id
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        # Add same tag name to resource
        result = handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="EXISTING-TAG",
            user=mock_user
        )
        
        assert result["id"] == tag_id
        assert result["name"] == "EXISTING-TAG"
    
    def test_add_resource_tag_idempotent(self, handler, setup_tenant_and_application):
        """Test that adding the same tag twice is idempotent."""
        data = setup_tenant_and_application
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        # Add tag twice
        handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="IDEMPOTENT-TAG",
            user=mock_user
        )
        handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="IDEMPOTENT-TAG",
            user=mock_user
        )
        
        # Verify only one tag association exists
        tags_result = handler.get_resource_tags(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=False
        )
        
        assert len(tags_result["tags"]) == 1
    
    def test_set_resource_tags_replaces_existing(self, handler, setup_tenant_and_application):
        """Test that set_resource_tags replaces existing tags."""
        data = setup_tenant_and_application
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        # Add initial tags
        handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="TAG1",
            user=mock_user
        )
        handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="TAG2",
            user=mock_user
        )
        
        # Replace with new set of tags
        result = handler.set_resource_tags(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_names=["TAG3", "TAG4"],
            user=mock_user
        )
        
        assert len(result["tags"]) == 2
        tag_names = [t["name"] for t in result["tags"]]
        assert "TAG3" in tag_names
        assert "TAG4" in tag_names
        assert "TAG1" not in tag_names
        assert "TAG2" not in tag_names
    
    def test_set_resource_tags_empty_clears_all(self, handler, setup_tenant_and_application):
        """Test that setting empty tag list clears all tags."""
        data = setup_tenant_and_application
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        # Add initial tags
        handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="to-be-removed",
            user=mock_user
        )
        
        # Clear all tags
        result = handler.set_resource_tags(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_names=[],
            user=mock_user
        )
        
        assert result["tags"] == []
    
    def test_remove_resource_tag(self, handler, setup_tenant_and_application):
        """Test removing a tag from a resource."""
        data = setup_tenant_and_application
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        # Add tag
        tag_result = handler.add_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_name="removable-tag",
            user=mock_user
        )
        tag_id = tag_result["id"]
        
        # Remove tag
        handler.remove_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_id=tag_id
        )
        
        # Verify tag is removed
        tags_result = handler.get_resource_tags(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=False
        )
        
        assert len(tags_result["tags"]) == 0
    
    def test_remove_resource_tag_nonexistent_does_not_raise(self, handler, setup_tenant_and_application):
        """Test removing a non-existent tag doesn't raise an error."""
        data = setup_tenant_and_application
        
        # Should not raise even if tag doesn't exist
        handler.remove_resource_tag(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            tag_id=99999
        )


class TestResourceTagsHandlerMultipleResourceTypes:
    """Tests for different resource types."""
    
    @pytest.fixture
    def handler(self, test_db_client, test_cache_client):
        """Create handler instance."""
        return ResourceTagsHandler(
            db_client=test_db_client,
            cache_client=test_cache_client
        )
    
    @pytest.fixture
    def setup_tenant_with_resources(self, test_db_client, test_db_session):
        """Create tenant with multiple resource types."""
        tenant_id = str(uuid.uuid4())
        user_id = f"test-user-{str(uuid.uuid4())[:8]}"
        
        # Create tenant
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            description="Test Description",
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(tenant)
        
        # Create principal
        principal = Principal(
            tenant_id=tenant_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
            display_name="Test User",
            principal_name="test@example.com"
        )
        test_db_session.add(principal)
        
        # Create credential
        credential_id = str(uuid.uuid4())
        credential = Credential(
            id=credential_id,
            tenant_id=tenant_id,
            name="Test Credential",
            description="Test",
            type="API_KEY",
            source="manual",
            credential_uri="test://uri",
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(credential)
        
        # Create autonomous agent
        agent_id = str(uuid.uuid4())
        agent = AutonomousAgent(
            id=agent_id,
            tenant_id=tenant_id,
            name="Test Agent",
            description="Test",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(agent)
        
        test_db_session.commit()
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "credential_id": credential_id,
            "agent_id": agent_id
        }
    
    def test_get_resource_tags_credential(self, handler, setup_tenant_with_resources):
        """Test getting tags for credential resource type."""
        data = setup_tenant_with_resources
        
        result = handler.get_resource_tags(
            resource_type="credential",
            tenant_id=data["tenant_id"],
            resource_id=data["credential_id"],
            use_cache=False
        )
        
        assert result["resource_type"] == "credential"
        assert result["resource_id"] == data["credential_id"]
    
    def test_add_tag_to_credential(self, handler, setup_tenant_with_resources):
        """Test adding tag to credential resource type."""
        data = setup_tenant_with_resources
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        result = handler.add_resource_tag(
            resource_type="credential",
            tenant_id=data["tenant_id"],
            resource_id=data["credential_id"],
            tag_name="CREDENTIAL-TAG",
            user=mock_user
        )
        
        assert result["name"] == "CREDENTIAL-TAG"
        
        # Verify tag is listed
        tags_result = handler.get_resource_tags(
            resource_type="credential",
            tenant_id=data["tenant_id"],
            resource_id=data["credential_id"],
            use_cache=False
        )
        
        assert len(tags_result["tags"]) == 1
    
    def test_add_tag_to_autonomous_agent(self, handler, setup_tenant_with_resources):
        """Test adding tag to autonomous agent resource type."""
        data = setup_tenant_with_resources
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        result = handler.add_resource_tag(
            resource_type="autonomous_agent",
            tenant_id=data["tenant_id"],
            resource_id=data["agent_id"],
            tag_name="AGENT-TAG",
            user=mock_user
        )
        
        assert result["name"] == "AGENT-TAG"
    
    def test_same_tag_different_resources(self, handler, setup_tenant_with_resources):
        """Test that the same tag can be applied to different resource types."""
        data = setup_tenant_with_resources
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        # Add same tag to different resources
        cred_result = handler.add_resource_tag(
            resource_type="credential",
            tenant_id=data["tenant_id"],
            resource_id=data["credential_id"],
            tag_name="SHARED-TAG",
            user=mock_user
        )
        
        agent_result = handler.add_resource_tag(
            resource_type="autonomous_agent",
            tenant_id=data["tenant_id"],
            resource_id=data["agent_id"],
            tag_name="SHARED-TAG",
            user=mock_user
        )
        
        # Both should use the same tag ID
        assert cred_result["id"] == agent_result["id"]
        assert cred_result["name"] == "SHARED-TAG"


class TestResourceTagsHandlerCaching:
    """Tests for caching behavior."""
    
    @pytest.fixture
    def handler(self, test_db_client, test_cache_client):
        """Create handler instance."""
        return ResourceTagsHandler(
            db_client=test_db_client,
            cache_client=test_cache_client
        )
    
    @pytest.fixture
    def setup_tenant_and_application(self, test_db_client, test_db_session):
        """Create a tenant and application for testing."""
        tenant_id = str(uuid.uuid4())
        user_id = f"test-user-{str(uuid.uuid4())[:8]}"
        application_id = str(uuid.uuid4())
        
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            description="Test",
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(tenant)
        
        principal = Principal(
            tenant_id=tenant_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
            display_name="Test User",
            principal_name="test@example.com"
        )
        test_db_session.add(principal)
        
        application = Application(
            id=application_id,
            tenant_id=tenant_id,
            name="Test Application",
            description="Test",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(application)
        test_db_session.commit()
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "application_id": application_id
        }
    
    def test_get_resource_tags_uses_cache(self, handler, setup_tenant_and_application):
        """Test that get_resource_tags uses cache when available."""
        data = setup_tenant_and_application
        
        # First call should populate cache
        result1 = handler.get_resource_tags(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=True
        )
        
        # Second call should use cache (same result)
        result2 = handler.get_resource_tags(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=True
        )
        
        assert result1 == result2
