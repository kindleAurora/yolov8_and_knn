"""stage4 alerts rules and history

Revision ID: 20260414_0005
Revises: 20260406_0004
Create Date: 2026-04-14 20:30:00
"""

from collections.abc import Sequence
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260414_0005"
down_revision: str | None = "20260406_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="preset"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("threshold_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("zone_name", sa.String(length=120), nullable=True),
        sa.Column("behavior_type", sa.String(length=64), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("behavior_event_id", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("handled_by_user_id", sa.Integer(), nullable=True),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("rule_source", sa.String(length=32), nullable=False, server_default="preset"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handling_note", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["behavior_event_id"], ["behavior_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["handled_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_index("ix_alert_rules_farm_id", "alert_rules", ["farm_id"])
    op.create_index("ix_alert_rules_device_id", "alert_rules", ["device_id"])
    op.create_index("ix_alert_rules_rule_type", "alert_rules", ["rule_type"])
    op.create_index("ix_alert_rules_severity", "alert_rules", ["severity"])
    op.create_index("ix_alert_rules_source", "alert_rules", ["source"])
    op.create_index("ix_alert_rules_is_enabled", "alert_rules", ["is_enabled"])

    op.create_index("ix_alerts_farm_id", "alerts", ["farm_id"])
    op.create_index("ix_alerts_rule_id", "alerts", ["rule_id"])
    op.create_index("ix_alerts_behavior_event_id", "alerts", ["behavior_event_id"])
    op.create_index("ix_alerts_device_id", "alerts", ["device_id"])
    op.create_index("ix_alerts_handled_by_user_id", "alerts", ["handled_by_user_id"])
    op.create_index("ix_alerts_device_code", "alerts", ["device_code"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_rule_source", "alerts", ["rule_source"])
    op.create_index("ix_alerts_triggered_at", "alerts", ["triggered_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_triggered_at", table_name="alerts")
    op.drop_index("ix_alerts_rule_source", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_device_code", table_name="alerts")
    op.drop_index("ix_alerts_handled_by_user_id", table_name="alerts")
    op.drop_index("ix_alerts_device_id", table_name="alerts")
    op.drop_index("ix_alerts_behavior_event_id", table_name="alerts")
    op.drop_index("ix_alerts_rule_id", table_name="alerts")
    op.drop_index("ix_alerts_farm_id", table_name="alerts")

    op.drop_index("ix_alert_rules_is_enabled", table_name="alert_rules")
    op.drop_index("ix_alert_rules_source", table_name="alert_rules")
    op.drop_index("ix_alert_rules_severity", table_name="alert_rules")
    op.drop_index("ix_alert_rules_rule_type", table_name="alert_rules")
    op.drop_index("ix_alert_rules_device_id", table_name="alert_rules")
    op.drop_index("ix_alert_rules_farm_id", table_name="alert_rules")

    op.drop_table("alerts")
    op.drop_table("alert_rules")
