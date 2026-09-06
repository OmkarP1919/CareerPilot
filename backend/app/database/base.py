from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

_connect_args: dict = {}
if make_url(settings.DATABASE_URL).get_backend_name() == "postgresql":
    # Bound connection attempts so health/readiness probes (and every other
    # caller) fail fast when the database host is unreachable, instead of
    # hanging on the OS TCP timeout. Pool behavior and lifecycle are unchanged.
    _connect_args["connect_timeout"] = 3

engine = create_engine(
    settings.DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args
)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
