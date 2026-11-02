"""
Configuración compartida de los tests (pytest la carga sola).

Los "fixtures" son preparativos que un test pide por nombre. Por ejemplo, un
test que recibe `client` obtiene un cliente HTTP listo para hablar con la API.

Clave: los tests usan una base de datos EN MEMORIA, nueva para cada test.
Así nunca tocan tu vaultbase.db real y cada test arranca de cero.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.app import models  # noqa: F401  (registra las tablas)
from backend.app.database import get_session
from backend.app.main import app

PASSWORD = "clave-segura-123"
FAKE_USD_RATE = 40.0


@pytest.fixture(autouse=True)
def fake_rate_sources(monkeypatch):
    """
    autouse=True: se aplica a TODOS los tests sin pedirlo.
    Reemplaza las fuentes de cotización por una falsa: los tests nunca salen
    a internet (serían lentos y fallarían sin conexión o si el BCU está caído).
    """
    from backend.app.services import exchange

    def fake_bcu(until):
        return exchange.RateQuote(rate=FAKE_USD_RATE, rate_date=until, source="BCU")

    monkeypatch.setattr(exchange, "fetch_bcu", fake_bcu)
    monkeypatch.setattr(exchange, "fetch_open_er", lambda until: None)


@pytest.fixture
def session():
    # "sqlite://" sin archivo = base de datos que vive solo en la memoria RAM
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session):
    # Reemplazamos la sesión real por la de memoria ("dependency override")
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(client):
    """Devuelve una función que registra un usuario y devuelve sus headers con token."""

    def _make(email: str = "ana@example.com") -> dict:
        client.post(
            "/api/auth/register", json={"email": email, "name": "Ana", "password": PASSWORD}
        )
        res = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _make


@pytest.fixture
def auth(make_user):
    """Headers de un usuario ya logueado, listo para usar."""
    return make_user()
