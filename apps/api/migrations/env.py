from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings

url = get_settings().database_url.get_secret_value()
if not url:
    raise RuntimeError("DATABASE_URL must be configured")

if context.is_offline_mode():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
