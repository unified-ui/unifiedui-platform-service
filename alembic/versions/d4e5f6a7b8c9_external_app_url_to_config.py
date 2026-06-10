"""external_app_url_to_config

Revision ID: d4e5f6a7b8c9
Revises: eec4d3028327
Create Date: 2026-05-23 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql, postgresql

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'eec4d3028327'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PortableJSON = (
    sa.JSON()
    .with_variant(postgresql.JSONB(), "postgresql")
    .with_variant(mssql.JSON(), "mssql")
)


def upgrade() -> None:
    """Replace external_apps.url with a config JSON column.

    This is a breaking change. All existing external_apps rows are deleted
    because the feature is not yet in production use.
    """
    op.execute("DELETE FROM external_apps")
    op.drop_column('external_apps', 'url')
    op.add_column(
        'external_apps',
        sa.Column('config', PortableJSON, nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column('external_apps', 'config', server_default=None)


def downgrade() -> None:
    """Revert external_apps.config back to a url column."""
    op.execute("DELETE FROM external_apps")
    op.drop_column('external_apps', 'config')
    op.add_column(
        'external_apps',
        sa.Column('url', sa.String(length=2000), nullable=False, server_default=''),
    )
    op.alter_column('external_apps', 'url', server_default=None)
