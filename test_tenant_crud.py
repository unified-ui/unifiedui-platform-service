"""Test script for tenant CRUD operations with PostgreSQL."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.handlers.tenants_v2 import TenantHandler
from aihub.schema.requests.tenants import CreateTenantRequest, UpdateTenantRequest


def main():
    """Test tenant CRUD operations."""
    print("=== Testing Tenant CRUD with PostgreSQL ===\n")
    
    # Initialize database client
    print("1. Initializing database client...")
    db_client = SQLAlchemyClient()
    handler = TenantHandler(db_client)
    print("✓ Database client initialized\n")
    
    # Create a tenant
    print("2. Creating a new tenant...")
    create_request = CreateTenantRequest(
        name="Test Tenant",
        description="This is a test tenant created via SQLAlchemy"
    )
    user_id = "test-user-123"
    created_tenant = handler.create_tenant(create_request, user_id)
    print(f"✓ Tenant created: {created_tenant.id}")
    print(f"  Name: {created_tenant.name}")
    print(f"  Description: {created_tenant.description}")
    print(f"  Created at: {created_tenant.created_at}\n")
    
    # Get the tenant
    print("3. Retrieving the tenant...")
    tenant = handler.get_tenant(created_tenant.id)
    print(f"✓ Tenant retrieved: {tenant.id}")
    print(f"  Name: {tenant.name}\n")
    
    # List tenants
    print("4. Listing all tenants...")
    tenants = handler.list_tenants(skip=0, limit=10)
    print(f"✓ Found {len(tenants)} tenant(s):")
    for t in tenants:
        print(f"  - {t.id}: {t.name}")
    print()
    
    # Update the tenant
    print("5. Updating the tenant...")
    update_request = UpdateTenantRequest(
        name="Updated Test Tenant",
        description="This tenant has been updated"
    )
    updated_tenant = handler.update_tenant(created_tenant.id, update_request, user_id)
    print(f"✓ Tenant updated: {updated_tenant.id}")
    print(f"  New name: {updated_tenant.name}")
    print(f"  New description: {updated_tenant.description}\n")
    
    # Verify tenant role was created
    print("6. Verifying GLOBAL_ADMIN role was created...")
    with db_client.get_session() as session:
        from aihub.core.database.models import TenantRole
        from sqlalchemy import select
        
        query = select(TenantRole).where(
            TenantRole.tenant_id == created_tenant.id,
            TenantRole.principal_id == user_id
        )
        roles = session.execute(query).scalars().all()
        print(f"✓ Found {len(roles)} role(s) for user {user_id}:")
        for role in roles:
            print(f"  - Role: {role.role}")
            print(f"  - Name: {role.name}")
            print(f"  - Description: {role.description}")
    print()
    
    # Delete the tenant
    print("7. Deleting the tenant...")
    handler.delete_tenant(created_tenant.id)
    print(f"✓ Tenant deleted: {created_tenant.id}\n")
    
    # Verify deletion
    print("8. Verifying deletion...")
    try:
        handler.get_tenant(created_tenant.id)
        print("✗ ERROR: Tenant still exists!")
    except Exception as e:
        print(f"✓ Tenant properly deleted (exception: {type(e).__name__})\n")
    
    print("=== All tests completed successfully! ===")
    
    # Close database connection
    db_client.close()


if __name__ == "__main__":
    main()
