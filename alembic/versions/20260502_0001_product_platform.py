"""Initial product platform schema."""

from __future__ import annotations

from alembic import op

from deep_research_from_scratch.product.db import Base
from deep_research_from_scratch.product import models  # noqa: F401


revision = "20260502_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the product schema and pgvector extension."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop the product schema."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
