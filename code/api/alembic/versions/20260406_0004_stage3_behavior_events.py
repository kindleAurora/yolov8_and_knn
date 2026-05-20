"""stage3 inference events

Revision ID: 20260406_0004
Revises: 20260406_0003
Create Date: 2026-04-06 22:40:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260406_0004"
down_revision: str | None = "20260406_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("device_code", sa.String(length=64), nullable=True),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="source"),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "behavior_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("zone_id", sa.Integer(), nullable=True),
        sa.Column("media_asset_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("zone_name", sa.String(length=120), nullable=True),
        sa.Column("behavior_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cow_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("inference_source", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("frame_uri", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="SET NULL"),
    )

    op.create_index("ix_media_assets_farm_id", "media_assets", ["farm_id"])
    op.create_index("ix_media_assets_device_id", "media_assets", ["device_id"])
    op.create_index("ix_media_assets_device_code", "media_assets", ["device_code"])

    op.create_index("ix_behavior_events_farm_id", "behavior_events", ["farm_id"])
    op.create_index("ix_behavior_events_device_id", "behavior_events", ["device_id"])
    op.create_index("ix_behavior_events_zone_id", "behavior_events", ["zone_id"])
    op.create_index("ix_behavior_events_media_asset_id", "behavior_events", ["media_asset_id"])
    op.create_index("ix_behavior_events_request_id", "behavior_events", ["request_id"])
    op.create_index("ix_behavior_events_device_code", "behavior_events", ["device_code"])
    op.create_index("ix_behavior_events_behavior_type", "behavior_events", ["behavior_type"])
    op.create_index("ix_behavior_events_occurred_at", "behavior_events", ["occurred_at"])

    media_assets_table = sa.table(
        "media_assets",
        sa.column("id", sa.Integer()),
        sa.column("farm_id", sa.Integer()),
        sa.column("device_id", sa.Integer()),
        sa.column("device_code", sa.String()),
        sa.column("asset_type", sa.String()),
        sa.column("role", sa.String()),
        sa.column("uri", sa.String()),
        sa.column("captured_at", sa.DateTime(timezone=True)),
        sa.column("metadata", sa.JSON()),
    )
    behavior_events_table = sa.table(
        "behavior_events",
        sa.column("id", sa.Integer()),
        sa.column("farm_id", sa.Integer()),
        sa.column("device_id", sa.Integer()),
        sa.column("zone_id", sa.Integer()),
        sa.column("media_asset_id", sa.Integer()),
        sa.column("request_id", sa.String()),
        sa.column("device_code", sa.String()),
        sa.column("zone_name", sa.String()),
        sa.column("behavior_type", sa.String()),
        sa.column("occurred_at", sa.DateTime(timezone=True)),
        sa.column("cow_count", sa.Integer()),
        sa.column("confidence", sa.Float()),
        sa.column("model_name", sa.String()),
        sa.column("model_version", sa.String()),
        sa.column("inference_source", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("source_uri", sa.String()),
        sa.column("frame_uri", sa.String()),
        sa.column("notes", sa.String()),
        sa.column("raw_metadata", sa.JSON()),
    )

    op.bulk_insert(
        media_assets_table,
        [
            {
                "id": 1,
                "farm_id": 1,
                "device_id": 1,
                "device_code": "CAM-001",
                "asset_type": "video",
                "role": "source",
                "uri": "demo://stage3/cam-001-sample.mp4",
                "captured_at": datetime.now(timezone.utc),
                "metadata": {"pipeline_mode": "demo", "source_type": "video"},
            }
        ],
    )
    op.bulk_insert(
        behavior_events_table,
        [
            {
                "id": 1,
                "farm_id": 1,
                "device_id": 1,
                "zone_id": 1,
                "media_asset_id": 1,
                "request_id": "seed-stage3-demo",
                "device_code": "CAM-001",
                "zone_name": "饮水区",
                "behavior_type": "饮水",
                "occurred_at": datetime.now(timezone.utc),
                "cow_count": 3,
                "confidence": 0.94,
                "model_name": "yolo-knn-stage3-demo",
                "model_version": "0.3.0",
                "inference_source": "demo-pipeline",
                "source_type": "video",
                "source_uri": "demo://stage3/cam-001-sample.mp4",
                "frame_uri": None,
                "notes": "阶段 3 演示事件样例",
                "raw_metadata": {"seed": True, "pipeline_mode": "demo"},
            }
        ],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in ["media_assets", "behavior_events"]:
            op.execute(
                sa.text(
                    f"""
                    SELECT setval(
                      pg_get_serial_sequence('{table_name}', 'id'),
                      COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                      true
                    )
                    """
                )
            )


def downgrade() -> None:
    op.drop_index("ix_behavior_events_occurred_at", table_name="behavior_events")
    op.drop_index("ix_behavior_events_behavior_type", table_name="behavior_events")
    op.drop_index("ix_behavior_events_device_code", table_name="behavior_events")
    op.drop_index("ix_behavior_events_request_id", table_name="behavior_events")
    op.drop_index("ix_behavior_events_media_asset_id", table_name="behavior_events")
    op.drop_index("ix_behavior_events_zone_id", table_name="behavior_events")
    op.drop_index("ix_behavior_events_device_id", table_name="behavior_events")
    op.drop_index("ix_behavior_events_farm_id", table_name="behavior_events")

    op.drop_index("ix_media_assets_device_code", table_name="media_assets")
    op.drop_index("ix_media_assets_device_id", table_name="media_assets")
    op.drop_index("ix_media_assets_farm_id", table_name="media_assets")

    op.drop_table("behavior_events")
    op.drop_table("media_assets")
