"""
Conexión a la base de datos.

El "engine" es el objeto que sabe hablar con la base de datos. Una "session"
es una conversación con ella: abrimos una por cada pedido HTTP, la usamos
para leer/guardar y la cerramos al terminar.
"""

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

settings = get_settings()

# SQLite, por defecto, no deja usar la misma conexión desde distintos hilos.
# FastAPI sí usa varios hilos, así que desactivamos ese chequeo (solo SQLite).
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)


def create_db_and_tables() -> None:
    """Crea las tablas que todavía no existen (no borra datos)."""
    from . import models  # noqa: F401  (importarlos "registra" las tablas)

    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Dependencia de FastAPI: entrega una sesión a cada endpoint que la pida
    y la cierra automáticamente cuando el pedido termina (gracias al "with").
    """
    with Session(engine) as session:
        yield session
