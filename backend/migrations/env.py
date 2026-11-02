"""
Configuración de Alembic (migraciones).

Una MIGRACIÓN es un archivo con instrucciones para cambiar la estructura de
la base ("agregá la columna X a la tabla Y") sin perder los datos. Alembic
lleva la cuenta de cuáles ya se aplicaron, en una tablita llamada
alembic_version.

Comandos útiles (desde la carpeta del proyecto):
  Crear una migración después de cambiar un modelo:
    .venv\\Scripts\\alembic revision --autogenerate -m "describí el cambio"
  Aplicar las pendientes (también se hace solo al arrancar el servidor):
    .venv\\Scripts\\alembic upgrade head
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from backend.app import models  # noqa: F401  (registra todas las tablas)
from backend.app.config import get_settings

config = context.config
# Usamos la MISMA base de datos que la app (sale de DATABASE_URL / .env)
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Alembic compara estas tablas (nuestros modelos) con la base real
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (modo 'offline')."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Se conecta a la base y aplica las migraciones."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite no sabe modificar columnas directamente: "batch" recrea
            # la tabla por detrás. En PostgreSQL no hace falta, pero no molesta.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
