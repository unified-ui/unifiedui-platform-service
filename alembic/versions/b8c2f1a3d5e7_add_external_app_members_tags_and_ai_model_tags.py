"""add external_app_members, external_app_tags, and tenant_ai_model_tags

Revision ID: b8c2f1a3d5e7
Revises: a75f474e1ca6
Create Date: 2026-06-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from unifiedui.core.database.models import HighPrecisionDateTime

revision: str = 'b8c2f1a3d5e7'
down_revision: Union[str, None] = 'a75f474e1ca6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create external_app_members, external_app_tags, and tenant_ai_model_tags tables."""
    op.create_table('external_app_members',
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('external_app_id', sa.String(length=36), nullable=False),
    sa.Column('principal_id', sa.String(length=50), nullable=False),
    sa.Column('role', sa.Enum('READ', 'WRITE', 'ADMIN', name='permission_action', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', HighPrecisionDateTime(), nullable=False),
    sa.Column('updated_at', HighPrecisionDateTime(), nullable=False),
    sa.Column('created_by', sa.String(length=50), nullable=True),
    sa.Column('updated_by', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['external_app_id'], ['unifiedui.external_apps.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id', 'principal_id'], ['unifiedui.principals.tenant_id', 'unifiedui.principals.principal_id'], name='fk_external_app_members_principal', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('external_app_id', 'principal_id', name='uq_external_app_members'),
    schema='unifiedui'
    )
    op.create_index('ix_eam_external_app', 'external_app_members', ['external_app_id'], unique=False, schema='unifiedui')
    op.create_index('ix_eam_principal', 'external_app_members', ['principal_id'], unique=False, schema='unifiedui')

    op.create_table('external_app_tags',
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.Column('external_app_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', HighPrecisionDateTime(), nullable=False),
    sa.Column('updated_at', HighPrecisionDateTime(), nullable=False),
    sa.Column('created_by', sa.String(length=50), nullable=True),
    sa.Column('updated_by', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['external_app_id'], ['unifiedui.external_apps.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['unifiedui.tags.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'external_app_id'),
    schema='unifiedui'
    )
    op.create_index('ix_eat_external_app', 'external_app_tags', ['external_app_id'], unique=False, schema='unifiedui')
    op.create_index('ix_eat_tag', 'external_app_tags', ['tag_id'], unique=False, schema='unifiedui')

    op.create_table('tenant_ai_model_tags',
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.Column('tenant_ai_model_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', HighPrecisionDateTime(), nullable=False),
    sa.Column('updated_at', HighPrecisionDateTime(), nullable=False),
    sa.Column('created_by', sa.String(length=50), nullable=True),
    sa.Column('updated_by', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['tenant_ai_model_id'], ['unifiedui.tenant_ai_models.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['unifiedui.tags.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'tenant_ai_model_id'),
    schema='unifiedui'
    )
    op.create_index('ix_tamt_ai_model', 'tenant_ai_model_tags', ['tenant_ai_model_id'], unique=False, schema='unifiedui')
    op.create_index('ix_tamt_tag', 'tenant_ai_model_tags', ['tag_id'], unique=False, schema='unifiedui')


def downgrade() -> None:
    """Drop external_app_members, external_app_tags, and tenant_ai_model_tags tables."""
    op.drop_index('ix_tamt_tag', table_name='tenant_ai_model_tags', schema='unifiedui')
    op.drop_index('ix_tamt_ai_model', table_name='tenant_ai_model_tags', schema='unifiedui')
    op.drop_table('tenant_ai_model_tags', schema='unifiedui')

    op.drop_index('ix_eat_tag', table_name='external_app_tags', schema='unifiedui')
    op.drop_index('ix_eat_external_app', table_name='external_app_tags', schema='unifiedui')
    op.drop_table('external_app_tags', schema='unifiedui')

    op.drop_index('ix_eam_principal', table_name='external_app_members', schema='unifiedui')
    op.drop_index('ix_eam_external_app', table_name='external_app_members', schema='unifiedui')
    op.drop_table('external_app_members', schema='unifiedui')
