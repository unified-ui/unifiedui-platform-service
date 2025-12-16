from fastapi import APIRouter, Request, status, Query

from aihub.core.middleware.apis.v1.auth import authenticate
from aihub.core.identity.users import IdentityUser
from aihub.schema.responses.identity import (
    IdentityUserResponse,
    IdentityGroupResponse,
    IdentityUsersResponse,
    IdentityGroupsResponse
)
from aihub.utils.api_query import APIFilterQuery


router = APIRouter()


@router.get(
    "/me",
    response_model=IdentityUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User",
    description="Returns the authenticated user's identity information"
)
@authenticate
async def get_current_user(request: Request) -> IdentityUserResponse:
    """
    Get current authenticated user's identity.
    
    Args:
        request: FastAPI request object (contains user in request.state)
    
    Returns:
        UserIdentityResponse: User's identity information
    """
    try:
        user: IdentityUser = request.state.user
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
@authenticate
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
    user: IdentityUser = request.state.user
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
@authenticate
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
    user: IdentityUser = request.state.user
    query = APIFilterQuery(search=search, top=top, next_link=next_link)
    groups, next_link = user.idp.get_security_groups(query=query)
    return IdentityGroupsResponse(value=groups, next_link=next_link)

