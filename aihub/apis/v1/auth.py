from fastapi import APIRouter, Request, status

from aihub.core.middleware.apis.v1.auth import authenticate
from aihub.core.identity.user import IdentityUser
from aihub.schema.responses.auth import UserIdentityResponse


router = APIRouter()


@router.get(
    "/me",
    response_model=UserIdentityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User",
    description="Returns the authenticated user's identity information"
)
@authenticate
async def get_current_user(request: Request) -> UserIdentityResponse:
    """
    Get current authenticated user's identity.
    
    Args:
        request: FastAPI request object (contains user in request.state)
    
    Returns:
        UserIdentityResponse: User's identity information
    """
    user: IdentityUser = request.state.user
    user_data = user.identity.to_dict()
    return UserIdentityResponse(**user_data)
