"""LDAP identity provider using ldap3 library.

Provides user and group lookups via LDAP directory queries.
Requires an LDAP server URL, bind credentials, and base DN.
"""

import requests

from unifiedui.core.identity.providers import BaseIdentityProvider, BaseIdentityToken
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.utils.api_query import APIFilterQuery


class LDAPIdentityProvider(BaseIdentityProvider):
    """LDAP identity provider for directory user and group lookups."""

    def __init__(
        self,
        identity_token: BaseIdentityToken,
        server_url: str,
        bind_dn: str | None = None,
        bind_password: str | None = None,
        base_dn: str = "",
        user_search_filter: str = "(objectClass=person)",
        group_search_filter: str = "(objectClass=groupOfNames)",
        use_ssl: bool = True,
    ):
        """Initialize the LDAP identity provider.

        Args:
            identity_token: The user's verified identity token.
            server_url: LDAP server URL (e.g. ldap://ldap.example.com:389).
            bind_dn: Distinguished name for bind authentication.
            bind_password: Password for bind authentication.
            base_dn: Base DN for searches (e.g. dc=example,dc=com).
            user_search_filter: LDAP filter for user searches.
            group_search_filter: LDAP filter for group searches.
            use_ssl: Whether to use LDAPS.
        """
        super().__init__(identity_token)
        self._server_url = server_url
        self._bind_dn = bind_dn
        self._bind_password = bind_password
        self._base_dn = base_dn
        self._user_search_filter = user_search_filter
        self._group_search_filter = group_search_filter
        self._use_ssl = use_ssl

    def get_current_user_security_groups(self, query: APIFilterQuery | None = None) -> list[IdentityGroupResponse]:
        """Get groups the current LDAP user is a member of.

        Args:
            query: Optional filter/pagination query.

        Returns:
            List of group responses.
        """
        try:
            import ldap3

            server = ldap3.Server(self._server_url, use_ssl=self._use_ssl, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self._bind_dn, password=self._bind_password, auto_bind=True)

            user_dn = self.identity_token.get_identity_tenant_id()
            search_filter = f"(&{self._group_search_filter}(member={user_dn}))"

            max_results = query.top if query and query.top else 100

            conn.search(
                search_base=self._base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "entryUUID", "description"],
                size_limit=max_results,
            )

            groups = []
            for entry in conn.entries:
                groups.append(
                    IdentityGroupResponse(
                        id=str(entry.entryUUID) if hasattr(entry, "entryUUID") else str(entry.entry_dn),
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
        """Get all groups in the LDAP directory.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (groups, next_page_cookie).
        """
        try:
            import ldap3

            server = ldap3.Server(self._server_url, use_ssl=self._use_ssl, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self._bind_dn, password=self._bind_password, auto_bind=True)

            query = query or APIFilterQuery()
            search_filter = self._group_search_filter

            if query.search:
                search_filter = f"(&{self._group_search_filter}(cn=*{query.search}*))"

            max_results = query.top if query.top else 100

            conn.search(
                search_base=self._base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "entryUUID", "description"],
                size_limit=max_results,
            )

            groups = []
            for entry in conn.entries:
                groups.append(
                    IdentityGroupResponse(
                        id=str(entry.entryUUID) if hasattr(entry, "entryUUID") else str(entry.entry_dn),
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
        """Get users in the LDAP directory.

        Args:
            query: Optional filter/pagination query.

        Returns:
            Tuple of (users, next_page_cookie).
        """
        try:
            import ldap3

            server = ldap3.Server(self._server_url, use_ssl=self._use_ssl, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self._bind_dn, password=self._bind_password, auto_bind=True)

            query = query or APIFilterQuery()
            search_filter = self._user_search_filter

            if query.search:
                search_filter = f"(&{self._user_search_filter}(|(cn=*{query.search}*)(mail=*{query.search}*)))"

            max_results = query.top if query.top else 100

            conn.search(
                search_base=self._base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "uid", "mail", "givenName", "sn", "entryUUID"],
                size_limit=max_results,
            )

            users = []
            for entry in conn.entries:
                users.append(
                    IdentityUserResponse(
                        id=str(entry.entryUUID) if hasattr(entry, "entryUUID") else str(entry.entry_dn),
                        identity_provider=self.identity_token.get_identity_provider(),
                        display_name=str(entry.cn) if hasattr(entry, "cn") else "",
                        principal_name=str(entry.uid) if hasattr(entry, "uid") else None,
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
        """Get a single LDAP user by UID or DN.

        Args:
            user_id: LDAP user UID or DN.

        Returns:
            User identity response.

        Raises:
            requests.RequestException: If the user cannot be found.
        """
        try:
            import ldap3

            server = ldap3.Server(self._server_url, use_ssl=self._use_ssl, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self._bind_dn, password=self._bind_password, auto_bind=True)

            search_filter = f"(&{self._user_search_filter}(|(uid={user_id})(entryUUID={user_id})))"

            conn.search(
                search_base=self._base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "uid", "mail", "givenName", "sn", "entryUUID"],
                size_limit=1,
            )

            if not conn.entries:
                raise requests.RequestException(f"LDAP user not found: {user_id}")

            entry = conn.entries[0]
            result = IdentityUserResponse(
                id=str(entry.entryUUID) if hasattr(entry, "entryUUID") else str(entry.entry_dn),
                identity_provider=self.identity_token.get_identity_provider(),
                display_name=str(entry.cn) if hasattr(entry, "cn") else "",
                principal_name=str(entry.uid) if hasattr(entry, "uid") else None,
                mail=str(entry.mail) if hasattr(entry, "mail") else None,
                firstname=str(entry.givenName) if hasattr(entry, "givenName") else None,
                lastname=str(entry.sn) if hasattr(entry, "sn") else None,
            )
            conn.unbind()
            return result
        except ImportError:
            raise requests.RequestException("ldap3 library is not installed")

    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get a single LDAP group by CN or DN.

        Args:
            group_id: LDAP group CN or DN.

        Returns:
            Group identity response.

        Raises:
            requests.RequestException: If the group cannot be found.
        """
        try:
            import ldap3

            server = ldap3.Server(self._server_url, use_ssl=self._use_ssl, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self._bind_dn, password=self._bind_password, auto_bind=True)

            search_filter = f"(&{self._group_search_filter}(|(cn={group_id})(entryUUID={group_id})))"

            conn.search(
                search_base=self._base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["cn", "entryUUID"],
                size_limit=1,
            )

            if not conn.entries:
                raise requests.RequestException(f"LDAP group not found: {group_id}")

            entry = conn.entries[0]
            result = IdentityGroupResponse(
                id=str(entry.entryUUID) if hasattr(entry, "entryUUID") else str(entry.entry_dn),
                display_name=str(entry.cn) if hasattr(entry, "cn") else str(entry.entry_dn),
            )
            conn.unbind()
            return result
        except ImportError:
            raise requests.RequestException("ldap3 library is not installed")
