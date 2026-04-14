from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Farm(TimestampMixin, Base):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    users: Mapped[list[User]] = relationship(back_populates="farm")
    devices: Mapped[list[Device]] = relationship(back_populates="farm")
    zones: Mapped[list[Zone]] = relationship(back_populates="farm")
    media_assets: Mapped[list[MediaAsset]] = relationship(back_populates="farm")
    behavior_events: Mapped[list[BehaviorEvent]] = relationship(back_populates="farm")
    alert_rules: Mapped[list[AlertRule]] = relationship(back_populates="farm")
    alerts: Mapped[list[Alert]] = relationship(back_populates="farm")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="farm")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user_links: Mapped[list[UserRole]] = relationship(back_populates="role")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="users")
    role_links: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")
    handled_alerts: Mapped[list[Alert]] = relationship(back_populates="handled_by_user")

    @property
    def roles(self) -> list[Role]:
        return [link.role for link in self.role_links]

    @property
    def role_codes(self) -> list[str]:
        return [role.code for role in self.roles]

    def has_role(self, code: str) -> bool:
        return code in self.role_codes


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="role_links")
    role: Mapped[Role] = relationship(back_populates="user_links")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="camera")
    stream_url: Mapped[str] = mapped_column(Text, nullable=False)
    install_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="offline")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="devices")
    zones: Mapped[list[Zone]] = relationship(back_populates="device", cascade="all, delete-orphan")
    media_assets: Mapped[list[MediaAsset]] = relationship(back_populates="device")
    behavior_events: Mapped[list[BehaviorEvent]] = relationship(back_populates="device")
    alert_rules: Mapped[list[AlertRule]] = relationship(back_populates="device")
    alerts: Mapped[list[Alert]] = relationship(back_populates="device")


class Zone(TimestampMixin, Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(32), nullable=False)
    shape_type: Mapped[str] = mapped_column(String(32), nullable=False, default="polygon")
    points: Mapped[list[dict[str, float]]] = mapped_column(JSON, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    farm: Mapped[Farm] = relationship(back_populates="zones")
    device: Mapped[Device] = relationship(back_populates="zones")
    behavior_events: Mapped[list[BehaviorEvent]] = relationship(back_populates="zone")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    device_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="source")
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    asset_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    farm: Mapped[Farm] = relationship(back_populates="media_assets")
    device: Mapped[Device | None] = relationship(back_populates="media_assets")
    behavior_events: Mapped[list[BehaviorEvent]] = relationship(back_populates="media_asset")


class BehaviorEvent(TimestampMixin, Base):
    __tablename__ = "behavior_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    media_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    zone_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    behavior_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    cow_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    inference_source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    frame_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="behavior_events")
    device: Mapped[Device | None] = relationship(back_populates="behavior_events")
    zone: Mapped[Zone | None] = relationship(back_populates="behavior_events")
    media_asset: Mapped[MediaAsset | None] = relationship(back_populates="behavior_events")
    alerts: Mapped[list[Alert]] = relationship(back_populates="behavior_event")


class AlertRule(TimestampMixin, Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium", index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="preset", index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    threshold_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    zone_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    behavior_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="alert_rules")
    device: Mapped[Device | None] = relationship(back_populates="alert_rules")
    alerts: Mapped[list[Alert]] = relationship(back_populates="rule")


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    behavior_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("behavior_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    handled_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    device_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    rule_source: Mapped[str] = mapped_column(String(32), nullable=False, default="preset", index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handling_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="alerts")
    rule: Mapped[AlertRule | None] = relationship(back_populates="alerts")
    behavior_event: Mapped[BehaviorEvent | None] = relationship(back_populates="alerts")
    device: Mapped[Device | None] = relationship(back_populates="alerts")
    handled_by_user: Mapped[User | None] = relationship(back_populates="handled_alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    farm: Mapped[Farm | None] = relationship(back_populates="audit_logs")
    user: Mapped[User | None] = relationship(back_populates="audit_logs")
