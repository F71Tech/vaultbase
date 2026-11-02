"""
Conexión a la base de datos.

El "engine" es el objeto que sabe hablar con la base de datos. Una "session"
es una conversación con ella: abrimos una por cada pedido HTTP, la usamos
para leer/guardar y la cerramos al terminar.

En tu PC usamos SQLite (un archivo). En el servidor, PostgreSQL. El código
es el mismo: solo cambia DATABASE_URL.
"""

from pathlib import Path

from sqlmodel import Session, create_engine

from .config import get_settings

settings = get_settings()

if settings.is_sqlite:
    # SQLite, por defecto, no deja usar la misma conexión desde distintos hilos.
    # FastAPI sí usa varios hilos, así que desactivamos ese chequeo.
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
else:
    # pool_pre_ping: antes de usar una conexión, verifica que siga viva.
    # Neon "duerme" la base cuando no se usa y las conexiones viejas se cortan.
    engine = create_engine(settings.database_url, pool_pre_ping=True)

BASE_DIR = Path(__file__).resolve().parents[2]


def run_migrations() -> None:
    """
    Aplica las migraciones pendientes (alembic upgrade head).
    Se llama al arrancar el servidor: así la base siempre está al día,
    tanto en tu PC como en producción, sin correr comandos a mano.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "backend" / "migrations"))
    command.upgrade(config, "head")


def get_session():
    """
    Dependencia de FastAPI: entrega una sesión a cada endpoint que la pida
    y la cierra automáticamente cuando el pedido termina (gracias al "with").
    """
    with Session(engine) as session:
        yield session
