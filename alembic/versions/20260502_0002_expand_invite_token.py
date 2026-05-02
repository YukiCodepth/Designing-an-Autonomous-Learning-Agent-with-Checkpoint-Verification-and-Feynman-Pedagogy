"""Expand workspace invite token storage."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260502_0002"
down_revision = "20260502_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow longer signed invite tokens."""
    op.alter_column(
        "workspace_invites",
        "invite_token",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Restore the original invite token column width."""
    op.alter_column(
        "workspace_invites",
        "invite_token",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
