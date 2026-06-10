"""Unit tests for ContextIdentityUser profile resolution."""

from unittest.mock import MagicMock

from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.schema.responses.identity import IdentityUserResponse


def test_get_user_profile_fetches_current_user_by_id_when_token_has_no_profile_claims():
    """OIDC directory lookups must not treat the first user search result as current user."""
    current_user = IdentityUserResponse(
        id="maikel-sub",
        identity_provider="OIDC",
        display_name="Maikel Fritz",
        principal_name="maikel@example.com",
        mail="maikel@example.com",
    )
    first_directory_user = IdentityUserResponse(
        id="enrico-sub",
        identity_provider="OIDC",
        display_name="Enrico Goerlitz",
        principal_name="enrico@example.com",
        mail="enrico@example.com",
    )

    user = ContextIdentityUser.__new__(ContextIdentityUser)
    user._user_profile = None
    user.identity = MagicMock()
    user.identity.get_display_name.return_value = ""
    user.identity.get_mail.return_value = ""
    user.identity.get_id.return_value = "maikel-sub"
    user.identity.get_identity_provider.return_value = "OIDC"
    user.identity.get_principal_name.return_value = ""
    user.identity.get_firstname.return_value = ""
    user.identity.get_lastname.return_value = ""
    user.idp = MagicMock()
    user.idp.get_user_by_id.return_value = current_user
    user.idp.get_users.return_value = ([first_directory_user], None)

    profile = user._get_user_profile()

    assert profile.id == "maikel-sub"
    assert profile.display_name == "Maikel Fritz"
    user.idp.get_user_by_id.assert_called_once_with("maikel-sub")
    user.idp.get_users.assert_not_called()
