"""
Punto de entrada de VaultBase.

Este archivo crea la aplicación FastAPI. Uvicorn (el servidor) la busca acá:
    .venv\\Scripts\\python -m uvicorn backend.app.main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import create_db_and_tables
from .routers import auth, categories, finance, resources, users

settings = get_settings()

# Ruta a la carpeta "frontend" (dos niveles arriba de este archivo).
# Usamos Path para que funcione igual en Windows y en Linux (el servidor).
BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lo que está antes del "yield" corre UNA vez, al arrancar el servidor
    create_db_and_tables()
    yield
    # Lo que esté después del "yield" correría al apagarlo (por ahora, nada)


app = FastAPI(
    title=settings.app_name,
    description="API de finanzas personales: ingresos, gastos, metas, "
    "suscripciones, simulador de compras y calculadora de sueldo (Uruguay).\n\n"
    "**Montos:** todos los campos `*_cents` van en centésimos "
    "(ej: $ 1.500,50 → `150050`).\n\n"
    "**Cómo probar:** registrate en `/api/auth/register`, después tocá "
    "**Authorize** (arriba a la derecha) e ingresá tu email y contraseña.",
    version="0.2.0",
    lifespan=lifespan,
)


# --- Rutas de la API ---------------------------------------------------------
# Todas las rutas de la API empiezan con /api para no mezclarse con las páginas.

@app.get("/api/health", tags=["Sistema"])
def health():
    """Chequeo simple para saber si el servidor está vivo."""
    return {"status": "ok", "app": settings.app_name}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(resources.incomes_router)
app.include_router(resources.expenses_router)
app.include_router(resources.subscriptions_router)
app.include_router(resources.goals_router)
app.include_router(resources.wishlist_router)
app.include_router(finance.router)


# --- Frontend ----------------------------------------------------------------
# Montamos la carpeta frontend en "/" para que FastAPI entregue los HTML/CSS/JS.
# Va AL FINAL: si estuviera antes, "taparía" las rutas /api.
# html=True hace que "/" devuelva automáticamente index.html.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
