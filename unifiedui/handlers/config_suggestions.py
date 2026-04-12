"""Business logic handler for config suggestions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from unifiedui.core.database.enums import ChatAgentTypeEnum, WorkflowTypeEnum
from unifiedui.core.database.models import ChatAgent, Workflow
from unifiedui.schema.responses.config_suggestions import ConfigSuggestionsResponse

if TYPE_CHECKING:
    from unifiedui.core.database.client import SQLAlchemyClient

CHAT_AGENT_CONFIG_FIELDS: dict[str, list[str]] = {
    ChatAgentTypeEnum.N8N: ["chat_url", "workflow_endpoint"],
    ChatAgentTypeEnum.MICROSOFT_FOUNDRY: ["project_endpoint"],
    ChatAgentTypeEnum.REST_API: ["invoke_endpoint", "create_conversation_endpoint"],
}

WORKFLOW_CONFIG_FIELDS: dict[str, list[str]] = {
    WorkflowTypeEnum.N8N: ["workflow_endpoint"],
}


class ConfigSuggestionsHandler:
    """Handler for retrieving config field suggestions from existing resources."""

    def __init__(self, db_client: SQLAlchemyClient) -> None:
        """Initialize the handler.

        Args:
            db_client: Database client for querying resources.
        """
        self._db_client = db_client

    def get_suggestions(
        self,
        tenant_id: str,
        platform_type: str,
        query: str | None = None,
    ) -> ConfigSuggestionsResponse:
        """Return distinct config field values for a given platform type within a tenant.

        Args:
            tenant_id: Tenant scope for the query.
            platform_type: Platform type to filter by (e.g. N8N, MICROSOFT_FOUNDRY, REST_API).
            query: Optional substring filter applied to suggestion values.

        Returns:
            Config suggestions grouped by field name.
        """
        suggestions: dict[str, set[str]] = {}

        chat_agent_fields = CHAT_AGENT_CONFIG_FIELDS.get(platform_type, [])
        if chat_agent_fields:
            self._collect_from_table(
                tenant_id=tenant_id,
                model=ChatAgent,
                agent_type=platform_type,
                fields=chat_agent_fields,
                suggestions=suggestions,
            )

        workflow_fields = WORKFLOW_CONFIG_FIELDS.get(platform_type, [])
        if workflow_fields:
            self._collect_from_table(
                tenant_id=tenant_id,
                model=Workflow,
                agent_type=platform_type,
                fields=workflow_fields,
                suggestions=suggestions,
            )

        result: dict[str, list[str]] = {}
        for field_name, values in suggestions.items():
            filtered = sorted(values)
            if query:
                query_lower = query.lower()
                filtered = [v for v in filtered if query_lower in v.lower()]
            result[field_name] = filtered

        return ConfigSuggestionsResponse(suggestions=result)

    def _collect_from_table(
        self,
        tenant_id: str,
        model: type[ChatAgent] | type[Workflow],
        agent_type: str,
        fields: list[str],
        suggestions: dict[str, set[str]],
    ) -> None:
        """Extract distinct config field values from a resource table.

        Args:
            tenant_id: Tenant scope.
            model: SQLAlchemy model class (ChatAgent or Workflow).
            agent_type: Platform type value to filter rows.
            fields: Config JSON keys to extract values from.
            suggestions: Mutable dict to collect results into.
        """
        stmt = select(model.config).where(
            model.tenant_id == tenant_id,
            model.type == agent_type,
        )

        with self._db_client.get_session() as session:
            rows = session.execute(stmt).scalars().all()

        for config in rows:
            if not isinstance(config, dict):
                continue
            for field_name in fields:
                value = config.get(field_name)
                if isinstance(value, str) and value.strip():
                    suggestions.setdefault(field_name, set()).add(value.strip())
