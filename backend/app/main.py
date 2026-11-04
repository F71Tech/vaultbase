"""
Punto de entrada de VaultBase.

Este archivo crea la aplicación FastAPI. Uvicorn (el servidor) la busca acá:
    .venv\\Scripts\\python -m uvicorn backend.app.main:app --reload
"""

import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlmodel import select

from .config import get_settings
from .database import run_migrations
from .deps import SessionDep
from .routers import admin, auth, categories, finance, resources, salary, users

settings = get_settings()

# El "manifest" de la app instalable (PWA): Python no conoce esta extensión en
# todos los sistemas, y el celular lo quiere con su tipo correcto.
mimetypes.add_type("application/manifest+json", ".webmanifest")

# Ruta a la carpeta "frontend" (dos niveles arriba de este archivo).
# Usamos Path para que funcione igual en Windows y en Linux (el servidor).
BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lo que está antes del "yield" corre UNA vez, al arrancar el servidor:
    # aplicamos las migraciones pendientes para que la base esté al día.
    run_migrations()
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
def health(session: SessionDep):
    """
    Chequeo de salud: el servidor responde Y la base de datos contesta.
    Render lo consulta para saber si el deploy salió bien.
    """
    session.exec(select(1))  # si la base no responde, esto lanza un error (500)
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


# --- Encabezados de seguridad ------------------------------------------------
# Un "middleware" es código que corre en TODAS las respuestas. Acá agregamos
# encabezados que le piden al navegador ser más estricto:
#   - nosniff: no "adivinar" el tipo de archivo (evita ejecutar algo como script)
#   - DENY: que ninguna otra web pueda meter VaultBase adentro de un iframe
#     (evita "clickjacking": botones invisibles encima de la app)
#   - Referrer-Policy: no mandar la URL completa a otros sitios
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # "no-cache" NO significa "no guardar": significa "antes de usar tu copia, preguntame si
    # cambió". Si no cambió, el servidor responde en un instante sin mandar el archivo de nuevo.
    # Sin esto, el navegador podía seguir usando una versión vieja de la app por horas.
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(resources.incomes_router)
app.include_router(resources.commissions_router)
app.include_router(resources.pay_records_router)
app.include_router(resources.expenses_router)
app.include_router(resources.subscriptions_router)
app.include_router(resources.goals_router)
app.include_router(resources.wishlist_router)
app.include_router(finance.router)
app.include_router(salary.router)
app.include_router(admin.router)


# --- Frontend ----------------------------------------------------------------
# Montamos la carpeta frontend en "/" para que FastAPI entregue los HTML/CSS/JS.
# Va AL FINAL: si estuviera antes, "taparía" las rutas /api.
# html=True hace que "/" devuelva automáticamente index.html.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
