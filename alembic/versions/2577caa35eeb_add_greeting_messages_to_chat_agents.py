"""add_greeting_messages_to_chat_agents

Revision ID: 2577caa35eeb
Revises: d822759fdc55
Create Date: 2026-03-14 18:58:58.756420

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2577caa35eeb'
down_revision: Union[str, Sequence[str], None] = 'd822759fdc55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chat_agents', sa.Column('greeting_messages', sa.JSON().with_variant(mssql.JSON(), 'mssql').with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False, server_default='[]'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_agents', 'greeting_messages')
