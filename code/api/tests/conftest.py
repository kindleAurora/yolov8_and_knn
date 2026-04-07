from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.models import Device, Farm, Role, User, UserRole, Zone
from app.core.security import hash_password
from app.main import app


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    farm = Farm(
        id=1,
        name="Test Farm",
        location="Test Ranch",
        timezone="Asia/Shanghai",
        status="active",
    )
    admin_role = Role(id=1, code="admin", name="Administrator")
    viewer_role = Role(id=2, code="viewer", name="Viewer")
    admin = User(
        id=1,
        farm_id=1,
        username="admin",
        password_hash=hash_password("admin123", salt="test-admin-salt"),
        display_name="Admin User",
        email="admin@test.local",
        status="active",
    )
    viewer = User(
        id=2,
        farm_id=1,
        username="viewer",
        password_hash=hash_password("viewer123", salt="test-viewer-salt"),
        display_name="Viewer User",
        email="viewer@test.local",
        status="active",
    )
    device = Device(
        id=1,
        farm_id=1,
        code="CAM-TEST-001",
        name="Test Camera",
        device_type="camera",
        stream_url="rtsp://test/cam-1",
        install_location="Yard A",
        status="online",
        is_enabled=True,
        config={"resolution": "1080p"},
    )
    zone = Zone(
        id=1,
        farm_id=1,
        device_id=1,
        name="Water Zone",
        zone_type="water",
        shape_type="polygon",
        points=[
            {"x": 0.1, "y": 0.1},
            {"x": 0.4, "y": 0.1},
            {"x": 0.4, "y": 0.4},
        ],
        is_enabled=True,
    )

    session.add_all(
        [
            farm,
            admin_role,
            viewer_role,
            admin,
            viewer,
            UserRole(user=admin, role=admin_role),
            UserRole(user=viewer, role=viewer_role),
            device,
            zone,
        ]
    )
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
