"""add files table

Revision ID: c9d3e2f4a6b8
Revises: b8c2f1a3d5e7
Create Date: 2026-06-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from unifiedui.core.database.models import HighPrecisionDateTime

revision: str = 'c9d3e2f4a6b8'
down_revision: Union[str, None] = 'b8c2f1a3d5e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create files table for persistent file storage."""
    op.create_table('files',
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('file_name', sa.String(length=500), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=False),
    sa.Column('content_type', sa.String(length=255), nullable=False),
    sa.Column('storage_path', sa.String(length=1000), nullable=False),
    sa.Column('context_type', sa.Enum('CHAT_ATTACHMENT', 'APP_IMAGE', name='file_context_type', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('context_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', HighPrecisionDateTime(), nullable=False),
    sa.Column('updated_at', HighPrecisionDateTime(), nullable=False),
    sa.Column('created_by', sa.String(length=50), nullable=True),
    sa.Column('updated_by', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['unifiedui.tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_path', name='uq_files_storage_path'),
    schema='unifiedui'
    )
    op.create_index('ix_files_tenant', 'files', ['tenant_id'], unique=False, schema='unifiedui')
    op.create_index('ix_files_context', 'files', ['tenant_id', 'context_type', 'context_id'], unique=False, schema='unifiedui')
    op.create_index('ix_files_storage_path', 'files', ['storage_path'], unique=True, schema='unifiedui')


def downgrade() -> None:
    """Drop files table."""
    op.drop_index('ix_files_storage_path', table_name='files', schema='unifiedui')
    op.drop_index('ix_files_context', table_name='files', schema='unifiedui')
    op.drop_index('ix_files_tenant', table_name='files', schema='unifiedui')
    op.drop_table('files', schema='unifiedui')
