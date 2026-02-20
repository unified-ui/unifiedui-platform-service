"""add_embed_allowed_origins_to_applications

Revision ID: h2b3c4d5e6f7
Revises: 15a44fdbf615
Create Date: 2025-07-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'h2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = '15a44fdbf615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('applications', sa.Column('embed_allowed_origins', sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column('applications', 'embed_allowed_origins')
