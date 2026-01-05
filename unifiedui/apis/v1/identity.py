from fastapi import APIRouter, Request, status, Query, Depends

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.schema.responses.identity import (
    IdentityUserResponse,
    IdentityGroupResponse,
    IdentityUsersResponse,
    IdentityGroupsResponse
)
from unifiedui.schema.requests.principals import RefreshPrincipalRequest
from unifiedui.schema.responses.principals import PrincipalResponse
from unifiedui.handlers.principals import PrincipalHandler
from unifiedui.handlers.dependencies import get_db_client, get_cache_client
from unifiedui.utils.api_query import APIFilterQuery


router = APIRouter()


@router.get(
    "/me",
    response_model=IdentityUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User",
    description="Returns the authenticated user's identity information"
)
@authenticate()
async def get_current_user(request: Request) -> IdentityUserResponse:
    """
    Get current authenticated user's identity.
    
    Args:
        request: FastAPI request object (contains user in request.state)
    
    Returns:
        UserIdentityResponse: User's identity information
    """
    try:
        user: ContextIdentityUser = request.state.user
        return user.get_me()
    except Exception as e:
        print(f"Error retrieving current user: {e}")
        raise e


@router.get(
    "/users",
    response_model=IdentityUsersResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Users",
    description="Returns a paginated list of users from the identity provider"
)
@authenticate()
async def get_users(
    request: Request,
    search: str = Query(default="", description="Search term to filter users"),
    top: int = Query(default=100, ge=1, le=999, description="Maximum number of items to return"),
    next_link: str = Query(default="", description="Link to the next page of results")
) -> IdentityUsersResponse:
    """
    Get users from the identity provider.
    
    Args:
        request: FastAPI request object (contains user in request.state)
        search: Search term to filter users
        top: Maximum number of items to return
        next_link: Link to the next page of results
    
    Returns:
        Paginated response with identity users and next_link
    """
    user: ContextIdentityUser = request.state.user
    query = APIFilterQuery(search=search, top=top, next_link=next_link)
    users, next_link = user.idp.get_users(query=query)
    return IdentityUsersResponse(value=users, next_link=next_link)


@router.get(
    "/groups",
    response_model=IdentityGroupsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Security Groups",
    description="Returns a paginated list of security groups from the identity provider"
)
@authenticate()
async def get_groups(
    request: Request,
    search: str = Query(default="", description="Search term to filter groups"),
    top: int = Query(default=100, ge=1, le=999, description="Maximum number of items to return"),
    next_link: str = Query(default="", description="Link to the next page of results")
) -> IdentityGroupsResponse:
    """
    Get security groups from the identity provider.
    
    Args:
        request: FastAPI request object (contains user in request.state)
        search: Search term to filter groups
        top: Maximum number of items to return
        next_link: Link to the next page of results
    
    Returns:
        Paginated response with identity groups and next_link
    """
    user: ContextIdentityUser = request.state.user
    query = APIFilterQuery(search=search, top=top, next_link=next_link)
    groups, next_link = user.idp.get_security_groups(query=query)
    return IdentityGroupsResponse(value=groups, next_link=next_link)


@router.get(
    "/users/{user_id}",
    response_model=IdentityUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User by ID",
    description="Returns a specific user from the identity provider by their ID"
)
@authenticate()
async def get_user_by_id(
    request: Request,
    user_id: str
) -> IdentityUserResponse:
    """
    Get a specific user by ID from the identity provider.
    
    Args:
        request: FastAPI request object (contains user in request.state)
        user_id: The ID of the user to retrieve
    
    Returns:
        IdentityUserResponse: User details
    """
    user: ContextIdentityUser = request.state.user
    return user.idp.get_user_by_id(user_id)


@router.get(
    "/groups/{group_id}",
    response_model=IdentityGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Group by ID",
    description="Returns a specific security group from the identity provider by its ID"
)
@authenticate()
async def get_group_by_id(
    request: Request,
    group_id: str
) -> IdentityGroupResponse:
    """
    Get a specific security group by ID from the identity provider.
    
    Args:
        request: FastAPI request object (contains user in request.state)
        group_id: The ID of the group to retrieve
    
    Returns:
        IdentityGroupResponse: Group details
    """
    user: ContextIdentityUser = request.state.user
    return user.idp.get_group_by_id(group_id)


@router.put(
    "/principals/{principal_id}/refresh",
    response_model=PrincipalResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Principal",
    description="Fetches a principal (user or group) from the identity provider and updates or creates the principal record in the database"
)
@authenticate()
async def refresh_principal(
    request: Request,
    principal_id: str,
    body: RefreshPrincipalRequest
) -> PrincipalResponse:
    """
    Refresh a principal from the identity provider.
    
    Fetches the user or group from the identity provider and updates or creates
    the principal record in the database for the specified tenant.
    
    Args:
        request: FastAPI request object (contains user in request.state)
        principal_id: The ID of the principal to refresh
        body: Request body with tenant_id and type (IDENTITY_USER or IDENTITY_GROUP)
    
    Returns:
        PrincipalResponse: The refreshed principal data
    """
    user: ContextIdentityUser = request.state.user
    db_client = get_db_client()
    cache_client = get_cache_client()
    
    handler = PrincipalHandler(db_client=db_client, cache_client=cache_client)
    return handler.refresh_principal(
        tenant_id=body.tenant_id,
        principal_id=principal_id,
        principal_type=body.type,
        user=user
    )

