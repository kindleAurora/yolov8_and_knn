"""stage1 bootstrap

Revision ID: 20260406_0001
Revises:
Create Date: 2026-04-06 19:30:00
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260406_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
