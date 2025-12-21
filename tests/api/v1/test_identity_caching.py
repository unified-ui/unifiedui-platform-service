"""Tests for identity endpoint caching behavior."""
import uuid
from fastapi import status


class TestIdentityCaching:
    """Test suite for identity endpoint caching behavior."""
    
    def test_current_user_cached(self, test_client, fake_redis_client):
        """Test that current user information is cached."""
        user_token = test_client.create_test_user("cache-me-user", "Cache Me User")
        headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        # First request - should cache
        response1 = test_client.get(
            "/api/v1/identity/me",
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        
        # Second request - should use cache
        response2 = test_client.get(
            "/api/v1/identity/me",
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        
        # Data should be identical
        assert data1 == data2
        assert data1["id"] == "cache-me-user"
    
    def test_current_user_cache_disabled(self, test_client, fake_redis_client):
        """Test that current user cache can be disabled with header."""
        user_token = test_client.create_test_user("no-cache-me", "No Cache Me")
        headers = {
            "Authorization": f"Bearer {user_token.get_token()}",
            "X-Use-Cache": "false"
        }
        
        # Both requests should work without cache
        response1 = test_client.get("/api/v1/identity/me", headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        
        response2 = test_client.get("/api/v1/identity/me", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
    
    def test_user_groups_cached(self, test_client, fake_redis_client):
        """Test that user groups are cached correctly."""
        user_token = test_client.create_test_user(
            "cache-groups-user",
            "Cache Groups User",
            idp_groups=["group-a", "group-b", "group-c"]
        )
        headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        # Create tenant to trigger group cache
        create_response = test_client.post(
            "/api/v1/tenants",
            json={"name": "Groups Cache Test", "description": "Test"},
            headers=headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Grant permission to identity group
        grant_response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={
                "principal_id": "group-a",
                "principal_type": "IDENTITY_GROUP",
                "role": "READER"
            },
            headers=headers
        )
        assert grant_response.status_code == status.HTTP_200_OK
        
        # First access - should cache groups
        response1 = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Second access - should use cached groups
        response2 = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
    
    def test_users_list_not_cached_by_default(self, test_client, fake_redis_client):
        """Test that users list is not cached (external data source)."""
        user_token = test_client.create_test_user("users-list-test", "Users List Test")
        headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        # Multiple requests should work (not cached since it's external data)
        response1 = test_client.get("/api/v1/identity/users", headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        
        response2 = test_client.get("/api/v1/identity/users", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
    
    def test_groups_list_not_cached_by_default(self, test_client, fake_redis_client):
        """Test that groups list is not cached (external data source)."""
        user_token = test_client.create_test_user("groups-list-test", "Groups List Test")
        headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        # Multiple requests should work (not cached since it's external data)
        response1 = test_client.get("/api/v1/identity/groups", headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        
        response2 = test_client.get("/api/v1/identity/groups", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
    
    def test_user_by_id_response_consistency(self, test_client, fake_redis_client):
        """Test that getting user by ID returns consistent data."""
        user_token = test_client.create_test_user("consistency-test", "Consistency Test")
        headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        user_id = "test-user-456"
        
        # First request
        response1 = test_client.get(
            f"/api/v1/identity/users/{user_id}",
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        
        # Second request
        response2 = test_client.get(
            f"/api/v1/identity/users/{user_id}",
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        
        # Should return same data
        assert data1["id"] == data2["id"] == user_id
    
    def test_group_by_id_response_consistency(self, test_client, fake_redis_client):
        """Test that getting group by ID returns consistent data."""
        user_token = test_client.create_test_user("group-consistency", "Group Consistency")
        headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        group_id = "test-group-789"
        
        # First request
        response1 = test_client.get(
            f"/api/v1/identity/groups/{group_id}",
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        
        # Second request
        response2 = test_client.get(
            f"/api/v1/identity/groups/{group_id}",
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        
        # Should return same data
        assert data1["id"] == data2["id"] == group_id
    
    def test_cache_isolated_between_users(self, test_client, fake_redis_client):
        """Test that cache is properly isolated between different users."""
        # Create two users
        user1_token = test_client.create_test_user("cache-iso-1", "Cache Isolation 1")
        user2_token = test_client.create_test_user("cache-iso-2", "Cache Isolation 2")
        
        headers1 = {"Authorization": f"Bearer {user1_token.get_token()}"}
        headers2 = {"Authorization": f"Bearer {user2_token.get_token()}"}
        
        # User 1 gets their info (cached)
        response1 = test_client.get("/api/v1/identity/me", headers=headers1)
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["id"] == "cache-iso-1"
        
        # User 2 gets their info (should not see user 1's cached data)
        response2 = test_client.get("/api/v1/identity/me", headers=headers2)
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["id"] == "cache-iso-2"
        
        # Verify isolation
        assert response1.json()["id"] != response2.json()["id"]
    
    def test_identity_groups_cache_invalidated_on_permission_change(self, test_client, fake_redis_client):
        """Test that identity groups cache is invalidated when group permissions change."""
        # Create admin and user with groups
        admin_token = test_client.create_test_user("cache-admin-grp", "Cache Admin Groups")
        admin_headers = {"Authorization": f"Bearer {admin_token.get_token()}"}
        
        user_token = test_client.create_test_user(
            "cache-user-grp",
            "Cache User Groups",
            idp_groups=["test-group-cache"]
        )
        user_headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        # Admin creates tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json={"name": "Group Cache Invalidation Test", "description": "Test"},
            headers=admin_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # User has no access initially (caches no permission)
        response_before = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=user_headers
        )
        assert response_before.status_code == status.HTTP_403_FORBIDDEN
        
        # Admin grants permission to user's identity group
        grant_response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={
                "principal_id": "test-group-cache",
                "principal_type": "IDENTITY_GROUP",
                "role": "READER"
            },
            headers=admin_headers
        )
        assert grant_response.status_code == status.HTTP_200_OK
        
        # User should NOW have access (cache must be invalidated)
        response_after = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=user_headers
        )
        assert response_after.status_code == status.HTTP_200_OK
        assert response_after.json()["id"] == tenant_id
    
    def test_identity_groups_cache_invalidated_on_permission_removal(self, test_client, fake_redis_client):
        """Test that identity groups cache is invalidated when group permissions are removed."""
        # Create admin and user with groups
        admin_token = test_client.create_test_user("cache-admin-rmv", "Cache Admin Remove")
        admin_headers = {"Authorization": f"Bearer {admin_token.get_token()}"}
        
        user_token = test_client.create_test_user(
            "cache-user-rmv",
            "Cache User Remove",
            idp_groups=["remove-group-cache"]
        )
        user_headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        # Admin creates tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json={"name": "Group Remove Cache Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Admin grants permission to user's group
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={
                "principal_id": "remove-group-cache",
                "principal_type": "IDENTITY_GROUP",
                "role": "GLOBAL_ADMIN"
            },
            headers=admin_headers
        )
        
        # User CAN access (cache this)
        response_with_access = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=user_headers
        )
        assert response_with_access.status_code == status.HTTP_200_OK
        
        # Admin revokes group permission
        revoke_response = test_client.request(
            "DELETE",
            f"/api/v1/tenants/{tenant_id}/principals",
            json={
                "principal_id": "remove-group-cache",
                "principal_type": "IDENTITY_GROUP",
                "role": "GLOBAL_ADMIN"
            },
            headers=admin_headers
        )
        assert revoke_response.status_code == status.HTTP_200_OK
        
        # User should NO LONGER have access (cache must be invalidated)
        response_no_access = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=user_headers
        )
        assert response_no_access.status_code == status.HTTP_403_FORBIDDEN
    
    def test_different_users_different_group_caches(self, test_client, fake_redis_client):
        """Test that different users have different group caches."""
        # User 1 with group A
        user1_token = test_client.create_test_user(
            "multi-cache-1",
            "Multi Cache 1",
            idp_groups=["group-alpha"]
        )
        headers1 = {"Authorization": f"Bearer {user1_token.get_token()}"}
        
        # User 2 with group B
        user2_token = test_client.create_test_user(
            "multi-cache-2",
            "Multi Cache 2",
            idp_groups=["group-beta"]
        )
        headers2 = {"Authorization": f"Bearer {user2_token.get_token()}"}
        
        # Admin creates two tenants
        admin_token = test_client.create_test_user("multi-admin", "Multi Admin")
        admin_headers = {"Authorization": f"Bearer {admin_token.get_token()}"}
        
        # Tenant 1 - group-alpha has access
        tenant1_response = test_client.post(
            "/api/v1/tenants",
            json={"name": "Tenant Alpha", "description": "For group alpha"},
            headers=admin_headers
        )
        tenant1_id = tenant1_response.json()["id"]
        
        test_client.put(
            f"/api/v1/tenants/{tenant1_id}/principals",
            json={
                "principal_id": "group-alpha",
                "principal_type": "IDENTITY_GROUP",
                "role": "READER"
            },
            headers=admin_headers
        )
        
        # Tenant 2 - group-beta has access
        tenant2_response = test_client.post(
            "/api/v1/tenants",
            json={"name": "Tenant Beta", "description": "For group beta"},
            headers=admin_headers
        )
        tenant2_id = tenant2_response.json()["id"]
        
        test_client.put(
            f"/api/v1/tenants/{tenant2_id}/principals",
            json={
                "principal_id": "group-beta",
                "principal_type": "IDENTITY_GROUP",
                "role": "READER"
            },
            headers=admin_headers
        )
        
        # User 1 can access tenant 1 but not tenant 2
        user1_tenant1 = test_client.get(f"/api/v1/tenants/{tenant1_id}", headers=headers1)
        assert user1_tenant1.status_code == status.HTTP_200_OK
        
        user1_tenant2 = test_client.get(f"/api/v1/tenants/{tenant2_id}", headers=headers1)
        assert user1_tenant2.status_code == status.HTTP_403_FORBIDDEN
        
        # User 2 can access tenant 2 but not tenant 1
        user2_tenant1 = test_client.get(f"/api/v1/tenants/{tenant1_id}", headers=headers2)
        assert user2_tenant1.status_code == status.HTTP_403_FORBIDDEN
        
        user2_tenant2 = test_client.get(f"/api/v1/tenants/{tenant2_id}", headers=headers2)
        assert user2_tenant2.status_code == status.HTTP_200_OK
    
    def test_pagination_parameters_dont_affect_cache_isolation(self, test_client, fake_redis_client):
        """Test that different pagination parameters don't cause cache collision."""
        user_token = test_client.create_test_user("page-cache", "Page Cache")
        headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        # Request with different pagination
        response1 = test_client.get("/api/v1/identity/users?top=10", headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        
        response2 = test_client.get("/api/v1/identity/users?top=20", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        
        # Both should work independently
        assert "value" in response1.json()
        assert "value" in response2.json()
    
    def test_search_parameters_dont_affect_cache_isolation(self, test_client, fake_redis_client):
        """Test that different search parameters don't cause cache collision."""
        user_token = test_client.create_test_user("search-cache", "Search Cache")
        headers = {"Authorization": f"Bearer {user_token.get_token()}"}
        
        # Request with different search terms
        response1 = test_client.get("/api/v1/identity/groups?search=admin", headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        
        response2 = test_client.get("/api/v1/identity/groups?search=user", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        
        # Both should work independently
        assert "value" in response1.json()
        assert "value" in response2.json()
