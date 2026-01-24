"""remove_development_platforms

Revision ID: e68a779863bf
Revises: d9e2f3a4b5c6
Create Date: 2026-01-24 21:54:37.025177

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e68a779863bf'
down_revision: Union[str, Sequence[str], None] = 'd9e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Remove development_platforms and related tables."""
    # Drop dependent tables first (in correct order)
    op.drop_index(op.f('ix_dpuf_development_platform'), table_name='development_platform_user_favorites')
    op.drop_index(op.f('ix_dpuf_user'), table_name='development_platform_user_favorites')
    op.drop_table('development_platform_user_favorites')
    
    op.drop_index(op.f('ix_dpm_development_platform'), table_name='development_platform_members')
    op.drop_index(op.f('ix_dpm_principal'), table_name='development_platform_members')
    op.drop_table('development_platform_members')
    
    op.drop_index(op.f('ix_dpt_development_platform'), table_name='development_platform_tags')
    op.drop_index(op.f('ix_dpt_tag'), table_name='development_platform_tags')
    op.drop_table('development_platform_tags')
    
    # Now drop the main table
    op.drop_index(op.f('ix_development_platforms_tenant'), table_name='development_platforms')
    op.drop_table('development_platforms')


def downgrade() -> None:
    """Downgrade schema - Recreate development_platforms and related tables."""
    # Recreate main table first
    op.create_table('development_platforms',
        sa.Column('type', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
        sa.Column('iframe_url', sa.VARCHAR(length=2000), autoincrement=False, nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column('description', sa.VARCHAR(length=2000), autoincrement=False, nullable=True),
        sa.Column('id', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column('created_by', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column('updated_by', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column('tenant_id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('development_platforms_tenant_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('development_platforms_pkey'))
    )
    op.create_index(op.f('ix_development_platforms_tenant'), 'development_platforms', ['tenant_id'], unique=False)
    
    # Recreate dependent tables
    op.create_table('development_platform_tags',
        sa.Column('tenant_id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column('tag_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('development_platform_id', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column('created_by', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column('updated_by', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['development_platform_id'], ['development_platforms.id'], name=op.f('development_platform_tags_development_platform_id_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('development_platform_tags_tag_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'development_platform_id', name=op.f('development_platform_tags_pkey'))
    )
    op.create_index(op.f('ix_dpt_tag'), 'development_platform_tags', ['tag_id'], unique=False)
    op.create_index(op.f('ix_dpt_development_platform'), 'development_platform_tags', ['development_platform_id'], unique=False)
    
    op.create_table('development_platform_members',
        sa.Column('tenant_id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column('development_platform_id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column('principal_id', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column('role', sa.VARCHAR(length=5), autoincrement=False, nullable=False),
        sa.Column('id', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column('created_by', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column('updated_by', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.CheckConstraint("role::text = ANY (ARRAY['READ'::character varying, 'WRITE'::character varying, 'ADMIN'::character varying]::text[])", name=op.f('permission_action')),
        sa.ForeignKeyConstraint(['development_platform_id'], ['development_platforms.id'], name=op.f('development_platform_members_development_platform_id_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id', 'principal_id'], ['principals.tenant_id', 'principals.principal_id'], name=op.f('fk_development_platform_members_principal'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('development_platform_members_pkey')),
        sa.UniqueConstraint('development_platform_id', 'principal_id', name=op.f('uq_development_platform_members'))
    )
    op.create_index(op.f('ix_dpm_principal'), 'development_platform_members', ['principal_id'], unique=False)
    op.create_index(op.f('ix_dpm_development_platform'), 'development_platform_members', ['development_platform_id'], unique=False)
    
    op.create_table('development_platform_user_favorites',
        sa.Column('tenant_id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column('user_id', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column('development_platform_id', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column('created_by', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column('updated_by', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['development_platform_id'], ['development_platforms.id'], name=op.f('development_platform_user_favorite_development_platform_id_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id', 'user_id'], ['principals.tenant_id', 'principals.principal_id'], name=op.f('fk_development_platform_user_favorites_principal'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('development_platform_user_favorites_tenant_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'user_id', 'development_platform_id', name=op.f('development_platform_user_favorites_pkey'))
    )
    op.create_index(op.f('ix_dpuf_user'), 'development_platform_user_favorites', ['user_id'], unique=False)
    op.create_index(op.f('ix_dpuf_development_platform'), 'development_platform_user_favorites', ['development_platform_id'], unique=False)
