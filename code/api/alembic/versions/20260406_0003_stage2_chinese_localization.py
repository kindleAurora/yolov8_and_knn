"""stage2 chinese localization

Revision ID: 20260406_0003
Revises: 20260406_0002
Create Date: 2026-04-06 21:55:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260406_0003"
down_revision: str | None = "20260406_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE farms SET name = '示范农场' WHERE id = 1"))
    op.execute(sa.text("UPDATE users SET display_name = '系统管理员' WHERE username = 'admin'"))
    op.execute(sa.text("UPDATE users SET display_name = '普通用户' WHERE username = 'viewer'"))
    op.execute(
        sa.text(
            """
            UPDATE devices
            SET
              name = '牛舍入口摄像头',
              device_type = '摄像头',
              install_location = '牛舍入口'
            WHERE id = 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE devices
            SET
              name = '采食区摄像头',
              device_type = '摄像头',
              install_location = '采食区'
            WHERE id = 2
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE zones
            SET
              name = '饮水区',
              zone_type = '饮水区'
            WHERE id = 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE zones
            SET
              name = '采食通道',
              zone_type = '采食区'
            WHERE id = 2
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE farms SET name = 'Demo Farm' WHERE id = 1"))
    op.execute(sa.text("UPDATE users SET display_name = 'Stage 2 Admin' WHERE username = 'admin'"))
    op.execute(sa.text("UPDATE users SET display_name = 'Stage 2 Viewer' WHERE username = 'viewer'"))
    op.execute(
        sa.text(
            """
            UPDATE devices
            SET
              name = 'Barn Gate Camera',
              device_type = 'camera',
              install_location = 'Barn Gate'
            WHERE id = 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE devices
            SET
              name = 'Feeding Area Camera',
              device_type = 'camera',
              install_location = 'Feeding Area'
            WHERE id = 2
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE zones
            SET
              name = 'Water Trough',
              zone_type = 'water'
            WHERE id = 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE zones
            SET
              name = 'Feeding Lane',
              zone_type = 'feeding'
            WHERE id = 2
            """
        )
    )
