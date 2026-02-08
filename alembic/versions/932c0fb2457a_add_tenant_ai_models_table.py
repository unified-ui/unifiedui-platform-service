"""add_tenant_ai_models_table

Revision ID: 932c0fb2457a
Revises: 7a68f0fc2759
Create Date: 2026-02-08 12:37:15.435406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '932c0fb2457a'
down_revision: Union[str, Sequence[str], None] = '7a68f0fc2759'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('tenant_ai_models',
    sa.Column('type', sa.Enum('LLM_MODEL', 'EMBEDDING_MODEL', name='ai_model_type', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('provider', sa.Enum('AZURE_OPENAI', 'OPENAI', 'ANTHROPIC', 'GOOGLE_GENAI', 'OLLAMA', 'MISTRAL', 'GROQ', name='ai_model_provider', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('purpose_groups', sa.JSON().with_variant(mssql.JSON(), 'mssql').with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('config', sa.JSON().with_variant(mssql.JSON(), 'mssql').with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('credential_id', sa.String(length=36), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=2000), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.String(length=50), nullable=True),
    sa.Column('updated_by', sa.String(length=50), nullable=True),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['credential_id'], ['credentials.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tenant_ai_models_tenant', 'tenant_ai_models', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_tenant_ai_models_tenant', table_name='tenant_ai_models')
    op.drop_table('tenant_ai_models')
