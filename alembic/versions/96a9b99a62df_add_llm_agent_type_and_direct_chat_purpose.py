"""add_llm_agent_type_and_direct_chat_purpose

Revision ID: 96a9b99a62df
Revises: ab923788c135
Create Date: 2026-04-12 12:00:00.000000

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "96a9b99a62df"
down_revision: Union[str, Sequence[str], None] = "ab923788c135"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add LLM to ChatAgentTypeEnum and DIRECT_CHAT to AIModelPurposeGroupEnum.

    Both enums use native_enum=False with create_constraint=False,
    so values are stored as plain strings. No DB-level ALTER is needed.
    This migration exists for traceability only.
    """
    pass


def downgrade() -> None:
    """Remove LLM agent type and DIRECT_CHAT purpose group.

    No DB-level changes needed since enums are stored as strings.
    Application-level validation handles allowed values.
    """
    pass
