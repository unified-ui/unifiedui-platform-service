"""Kerberos / SPNEGO identity provider with LDAP directory backend.

Provides user and group lookups via an LDAP directory that backs the
Kerberos realm. Kerberos authentication happens at the gateway level
(SPNEGO/GSSAPI); this provider handles directory lookups post-authentication.
"""

import requests

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class KerberosIdentityProvider(BaseIdentityProvider):
    """Kerberos identity provider using an LDAP directory backend for lookups."""

    def __init__(
        self,
        identity_token: BaseIdentityToken,
        ldap_url: str | None = None,
        ldap_base_dn: str = "",
        realm: str = "",
    ):
        """Initialize the Kerberos identity provider.

        Args:
            identity_token: The user's verified identity token.
            ldap_url: LDAP URL for directory lookups (e.g. ldap://dc.example.com).
            ldap_base_dn: Base DN for LDAP searches.
            realm: Kerberos realm name.
        """
        super().__init__(identity_token)
        self._ldap_url = ldap_url
        self._ldap_base_dn = ldap_base_dn
        self._realm = realm

    def get_current_user_security_groups(self, query: APIFilterQuery | None = None) -> list[IdentityGroupResponse]:
        """Get groups the current Kerberos user is a member of.

        Args:
            query: Optional filter/pagination query.

        Returns:
            List of group responses.
        """
        if not self._ldap_url:
            return []

        try:
            import ldap3

            server = ldap3.Server(self._ldap_url, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, auto_bind=True, authentication=ldap3.SASL, sasl_mechanism=ldap3.KERBEROS)

            principal = self.identity_token.get_principal_name()
            username = principal.split("@")[0] if "@" in principal else principal
            search_filter = f"(&(objectClass=group)(member=CN={username},{self._ldap_base_dn}))"

            max_results = query.top if query and query.top else 100

            conn.search(
                search_base=self._ldap_base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "objectGUID", "description"],
                size_limit=max_results,
            )

            groups = []
            for entry in conn.entries:
                groups.append(
                    IdentityGroupResponse(
                        id=str(entry.objectGUID) if hasattr(entry, "objectGUID") else str(entry.entry_dn),
                        display_name=str(entry.cn) if hasattr(entry, "cn") else str(entry.entry_dn),
                    )
                )

            conn.unbind()
            return groups
        except ImportError:
            return []
        except Exception:
            return []

    def get_security_groups(
        self, query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """Get all groups in the Kerberos-backed LDAP directory.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (groups, None).
        """
        if not self._ldap_url:
            return [], None

        try:
            import ldap3

            server = ldap3.Server(self._ldap_url, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, auto_bind=True, authentication=ldap3.SASL, sasl_mechanism=ldap3.KERBEROS)

            query = query or APIFilterQuery()
            search_filter = "(objectClass=group)"

            if query.search:
                search_filter = f"(&(objectClass=group)(cn=*{query.search}*))"

            max_results = query.top if query.top else 100

            conn.search(
                search_base=self._ldap_base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "objectGUID", "description"],
                size_limit=max_results,
            )

            groups = []
            for entry in conn.entries:
                groups.append(
                    IdentityGroupResponse(
                        id=str(entry.objectGUID) if hasattr(entry, "objectGUID") else str(entry.entry_dn),
                        display_name=str(entry.cn) if hasattr(entry, "cn") else str(entry.entry_dn),
                    )
                )

            conn.unbind()
            return groups, None
        except ImportError:
            return [], None
        except Exception:
            return [], None

    def get_users(self, query: APIFilterQuery | None = None) -> tuple[list[IdentityUserResponse], str | None]:
        """Get users in the Kerberos-backed LDAP directory.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (users, None).
        """
        if not self._ldap_url:
            return [], None

        try:
            import ldap3

            server = ldap3.Server(self._ldap_url, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, auto_bind=True, authentication=ldap3.SASL, sasl_mechanism=ldap3.KERBEROS)

            query = query or APIFilterQuery()
            search_filter = "(objectClass=person)"

            if query.search:
                search_filter = f"(&(objectClass=person)(|(cn=*{query.search}*)(mail=*{query.search}*)))"

            max_results = query.top if query.top else 100

            conn.search(
                search_base=self._ldap_base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "sAMAccountName", "mail", "givenName", "sn", "objectGUID"],
                size_limit=max_results,
            )

            users = []
            for entry in conn.entries:
                users.append(
                    IdentityUserResponse(
                        id=str(entry.objectGUID) if hasattr(entry, "objectGUID") else str(entry.entry_dn),
                        identity_provider=self.identity_token.get_identity_provider(),
                        display_name=str(entry.cn) if hasattr(entry, "cn") else "",
                        principal_name=str(entry.sAMAccountName) if hasattr(entry, "sAMAccountName") else None,
                        mail=str(entry.mail) if hasattr(entry, "mail") else None,
                        firstname=str(entry.givenName) if hasattr(entry, "givenName") else None,
                        lastname=str(entry.sn) if hasattr(entry, "sn") else None,
                    )
                )

            conn.unbind()
            return users, None
        except ImportError:
            return [], None
        except Exception:
            return [], None

    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get a single user by sAMAccountName or objectGUID.

        Args:
            user_id: User identifier.

        Returns:
            User identity response.

        Raises:
            requests.RequestException: If the user cannot be found.
        """
        if not self._ldap_url:
            raise requests.RequestException("Kerberos LDAP URL not configured")

        try:
            import ldap3

            server = ldap3.Server(self._ldap_url, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, auto_bind=True, authentication=ldap3.SASL, sasl_mechanism=ldap3.KERBEROS)

            search_filter = f"(&(objectClass=person)(|(sAMAccountName={user_id})(objectGUID={user_id})))"

            conn.search(
                search_base=self._ldap_base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "sAMAccountName", "mail", "givenName", "sn", "objectGUID"],
                size_limit=1,
            )

            if not conn.entries:
                raise requests.RequestException(f"Kerberos user not found: {user_id}")

            entry = conn.entries[0]
            result = IdentityUserResponse(
                id=str(entry.objectGUID) if hasattr(entry, "objectGUID") else str(entry.entry_dn),
                identity_provider=self.identity_token.get_identity_provider(),
                display_name=str(entry.cn) if hasattr(entry, "cn") else "",
                principal_name=str(entry.sAMAccountName) if hasattr(entry, "sAMAccountName") else None,
                mail=str(entry.mail) if hasattr(entry, "mail") else None,
                firstname=str(entry.givenName) if hasattr(entry, "givenName") else None,
                lastname=str(entry.sn) if hasattr(entry, "sn") else None,
            )
            conn.unbind()
            return result
        except ImportError:
            raise requests.RequestException("ldap3 library is not installed")

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get a single group by CN or objectGUID.

        Args:
            group_id: Group identifier.

        Returns:
            Group identity response.

        Raises:
            requests.RequestException: If the group cannot be found.
        """
        if not self._ldap_url:
            raise requests.RequestException("Kerberos LDAP URL not configured")

        try:
            import ldap3

            server = ldap3.Server(self._ldap_url, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, auto_bind=True, authentication=ldap3.SASL, sasl_mechanism=ldap3.KERBEROS)

            search_filter = f"(&(objectClass=group)(|(cn={group_id})(objectGUID={group_id})))"

            conn.search(
                search_base=self._ldap_base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "objectGUID"],
                size_limit=1,
            )

            if not conn.entries:
                raise requests.RequestException(f"Kerberos group not found: {group_id}")

            entry = conn.entries[0]
            result = IdentityGroupResponse(
                id=str(entry.objectGUID) if hasattr(entry, "objectGUID") else str(entry.entry_dn),
                display_name=str(entry.cn) if hasattr(entry, "cn") else str(entry.entry_dn),
            )
            conn.unbind()
            return result
        except ImportError:
            raise requests.RequestException("ldap3 library is not installed")
