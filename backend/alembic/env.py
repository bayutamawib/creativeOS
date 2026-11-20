from alembic import context
from app import operations_models, project_models  # noqa: F401
from app.db import engine
from app.models import Base

with engine().begin() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    context.run_migrations()
