from collections.abc import Generator
from urllib.error import URLError
from urllib.request import urlopen

from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine_options: dict[str, object] = {
    "pool_pre_ping": True,
}

if settings.database_url.startswith("postgresql"):
    engine_options["connect_args"] = {"connect_timeout": 2}

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database() -> tuple[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "up", "数据库连接正常"
    except Exception as exc:  # pragma: no cover - runtime health branch
        return "down", str(exc)


def check_redis() -> tuple[str, str]:
    try:
        client = Redis.from_url(settings.redis_url)
        client.ping()
        return "up", "Redis 连接正常"
    except Exception as exc:  # pragma: no cover - runtime health branch
        return "down", str(exc)


def check_inference_service() -> tuple[str, str]:
    try:
        with urlopen(f"{settings.inference_service_url}/health", timeout=2) as response:
            return "up", f"推理服务响应状态 {response.status}"
    except URLError as exc:  # pragma: no cover - runtime health branch
        return "down", str(exc.reason)
    except Exception as exc:  # pragma: no cover - runtime health branch
        return "down", str(exc)
