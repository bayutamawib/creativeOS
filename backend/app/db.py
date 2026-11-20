from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine

from app.config import settings


@lru_cache
def engine() -> Engine:
    return create_engine(
        settings().database_url,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )


@lru_cache
def migration_head() -> str | None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    return ScriptDirectory.from_config(config).get_current_head()


def database_ready() -> bool:
    with engine().connect() as connection:
        return MigrationContext.configure(connection).get_current_revision() == migration_head()
