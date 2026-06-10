"""Audit-event emission via structured logger.

Audit events are no longer persisted to a database table; instead they are
emitted as structured log records on the ``unifiedui.audit`` logger. In the
deployed environment these records are forwarded to Azure Log Analytics by
the standard logging pipeline and can be queried via KQL.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import Request

_logger = logging.getLogger("unifiedui.audit")


class AuditActionEnum(StrEnum):
    """Audit action verb."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    MEMBER_ADD = "MEMBER_ADD"
    MEMBER_REMOVE = "MEMBER_REMOVE"
    ROLE_CHANGE = "ROLE_CHANGE"
    EXECUTE = "EXECUTE"


class AuditResourceTypeEnum(StrEnum):
    """Resource type referenced by an audit event."""

    CHAT_AGENT = "CHAT_AGENT"
    WORKFLOW = "WORKFLOW"
    CREDENTIAL = "CREDENTIAL"
    TAG = "TAG"
    PRINCIPAL = "PRINCIPAL"
    CUSTOM_GROUP = "CUSTOM_GROUP"
    AI_MODEL = "AI_MODEL"
    EXTERNAL_APP = "EXTERNAL_APP"
    TENANT_SETTING = "TENANT_SETTING"


def record_audit(
    *,
    request: Request,
    tenant_id: str,
    action: AuditActionEnum | str,
    resource_type: AuditResourceTypeEnum | str,
    resource_id: str,
    resource_name: str | None = None,
    changes: dict[str, Any] | None = None,
) -> None:
    """Emit a structured audit log record.

    Best-effort: never raises. Pulls actor id/email from ``request.state.user``,
    client IP from ``request.client``, user-agent from request headers, and
    forwards everything as ``extra`` fields on a ``unifiedui.audit`` log
    record. The downstream log pipeline (Azure Log Analytics) parses these
    fields for ad-hoc querying.

    Args:
        request: FastAPI request providing user context and client metadata.
        tenant_id: Tenant scope of the audited operation.
        action: Audit action verb.
        resource_type: Type of resource affected.
        resource_id: ID of the affected resource.
        resource_name: Optional human-readable name of the resource.
        changes: Optional dict describing the change payload.
    """
    actor_id: str | None = None
    actor_email: str | None = None
    user = getattr(request.state, "user", None)
    if user is not None:
        identity = getattr(user, "identity", None)
        if identity is not None:
            try:
                actor_id = identity.get_id()
            except Exception:
                actor_id = None
            try:
                actor_email = identity.get_mail()
            except Exception:
                actor_email = None

    client_ip: str | None = None
    if request.client is not None:
        client_ip = request.client.host

    user_agent = request.headers.get("user-agent")

    try:
        _logger.info(
            "audit",
            extra={
                "audit_action": str(action),
                "audit_resource_type": str(resource_type),
                "audit_resource_id": resource_id,
                "audit_resource_name": resource_name,
                "audit_tenant_id": tenant_id,
                "audit_actor_id": actor_id,
                "audit_actor_email": actor_email,
                "audit_client_ip": client_ip,
                "audit_user_agent": user_agent,
                "audit_changes": changes,
            },
        )
    except Exception:
        pass
