"""stage2 auth and master data

Revision ID: 20260406_0002
Revises: 20260406_0001
Create Date: 2026-04-06 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260406_0002"
down_revision: str | None = "20260406_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "farms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("name", name="uq_farms_name"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("device_type", sa.String(length=32), nullable=False, server_default="camera"),
        sa.Column("stream_url", sa.Text(), nullable=False),
        sa.Column("install_location", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="offline"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_devices_code"),
    )
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("zone_type", sa.String(length=32), nullable=False),
        sa.Column("shape_type", sa.String(length=32), nullable=False, server_default="polygon"),
        sa.Column("points", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_index("ix_users_farm_id", "users", ["farm_id"])
    op.create_index("ix_devices_farm_id", "devices", ["farm_id"])
    op.create_index("ix_zones_farm_id", "zones", ["farm_id"])
    op.create_index("ix_zones_device_id", "zones", ["device_id"])
    op.create_index("ix_audit_logs_farm_id", "audit_logs", ["farm_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    farms_table = sa.table(
        "farms",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("location", sa.String()),
        sa.column("timezone", sa.String()),
        sa.column("status", sa.String()),
    )
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("farm_id", sa.Integer()),
        sa.column("username", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("email", sa.String()),
        sa.column("status", sa.String()),
    )
    user_roles_table = sa.table(
        "user_roles",
        sa.column("user_id", sa.Integer()),
        sa.column("role_id", sa.Integer()),
    )
    devices_table = sa.table(
        "devices",
        sa.column("id", sa.Integer()),
        sa.column("farm_id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("device_type", sa.String()),
        sa.column("stream_url", sa.String()),
        sa.column("install_location", sa.String()),
        sa.column("status", sa.String()),
        sa.column("is_enabled", sa.Boolean()),
        sa.column("config", sa.JSON()),
    )
    zones_table = sa.table(
        "zones",
        sa.column("id", sa.Integer()),
        sa.column("farm_id", sa.Integer()),
        sa.column("device_id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("zone_type", sa.String()),
        sa.column("shape_type", sa.String()),
        sa.column("points", sa.JSON()),
        sa.column("is_enabled", sa.Boolean()),
    )

    op.bulk_insert(
        farms_table,
        [
            {
                "id": 1,
                "name": "Demo Farm",
                "location": "Harbin Research Ranch",
                "timezone": "Asia/Shanghai",
                "status": "active",
            }
        ],
    )
    op.bulk_insert(
        roles_table,
        [
            {"id": 1, "code": "admin", "name": "Administrator", "description": "Full access for stage 2"},
            {"id": 2, "code": "viewer", "name": "Viewer", "description": "Read devices and manage zones"},
        ],
    )
    op.bulk_insert(
        users_table,
        [
            {
                "id": 1,
                "farm_id": 1,
                "username": "admin",
                "password_hash": "pbkdf2_sha256$600000$stage2-admin-salt$9f6348846b8c9abdc6b201c259d445bda80f6028dbe66a1e30e65cc202fa0cbf",
                "display_name": "Stage 2 Admin",
                "email": "admin@example.com",
                "status": "active",
            },
            {
                "id": 2,
                "farm_id": 1,
                "username": "viewer",
                "password_hash": "pbkdf2_sha256$600000$stage2-viewer-salt$d4b17d6b52bf9c1a4ef1e3eb92b015b915648f76290a5fdf7348ff4742b4ef92",
                "display_name": "Stage 2 Viewer",
                "email": "viewer@example.com",
                "status": "active",
            },
        ],
    )
    op.bulk_insert(
        user_roles_table,
        [
            {"user_id": 1, "role_id": 1},
            {"user_id": 2, "role_id": 2},
        ],
    )
    op.bulk_insert(
        devices_table,
        [
            {
                "id": 1,
                "farm_id": 1,
                "code": "CAM-001",
                "name": "Barn Gate Camera",
                "device_type": "camera",
                "stream_url": "rtsp://demo.local/cam-001",
                "install_location": "Barn Gate",
                "status": "online",
                "is_enabled": True,
                "config": {"resolution": "1080p", "model_binding": "stub-pipeline"},
            },
            {
                "id": 2,
                "farm_id": 1,
                "code": "CAM-002",
                "name": "Feeding Area Camera",
                "device_type": "camera",
                "stream_url": "rtsp://demo.local/cam-002",
                "install_location": "Feeding Area",
                "status": "offline",
                "is_enabled": True,
                "config": {"resolution": "720p", "model_binding": "stub-pipeline"},
            },
        ],
    )
    op.bulk_insert(
        zones_table,
        [
            {
                "id": 1,
                "farm_id": 1,
                "device_id": 1,
                "name": "Water Trough",
                "zone_type": "water",
                "shape_type": "polygon",
                "points": [
                    {"x": 0.12, "y": 0.18},
                    {"x": 0.34, "y": 0.16},
                    {"x": 0.36, "y": 0.32},
                    {"x": 0.14, "y": 0.35},
                ],
                "is_enabled": True,
            },
            {
                "id": 2,
                "farm_id": 1,
                "device_id": 2,
                "name": "Feeding Lane",
                "zone_type": "feeding",
                "shape_type": "polygon",
                "points": [
                    {"x": 0.2, "y": 0.2},
                    {"x": 0.8, "y": 0.22},
                    {"x": 0.78, "y": 0.48},
                    {"x": 0.22, "y": 0.46},
                ],
                "is_enabled": True,
            },
        ],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in ["farms", "roles", "users", "devices", "zones"]:
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
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_farm_id", table_name="audit_logs")
    op.drop_index("ix_zones_device_id", table_name="zones")
    op.drop_index("ix_zones_farm_id", table_name="zones")
    op.drop_index("ix_devices_farm_id", table_name="devices")
    op.drop_index("ix_users_farm_id", table_name="users")

    op.drop_table("audit_logs")
    op.drop_table("zones")
    op.drop_table("devices")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("farms")
