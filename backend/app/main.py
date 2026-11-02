"""
Punto de entrada de VaultBase.

Este archivo crea la aplicación FastAPI. Uvicorn (el servidor) la busca acá:
    .venv\\Scripts\\python -m uvicorn backend.app.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings

settings = get_settings()

# Ruta a la carpeta "frontend" (dos niveles arriba de este archivo).
# Usamos Path para que funcione igual en Windows y en Linux (el servidor).
BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title=settings.app_name,
    description="API de finanzas personales: ingresos, gastos, metas, "
    "suscripciones, simulador de compras y calculadora de sueldo (Uruguay).",
    version="0.1.0",
)


# --- Rutas de la API ---------------------------------------------------------
# Todas las rutas de la API empiezan con /api para no mezclarse con las páginas.

@app.get("/api/health", tags=["Sistema"])
def health():
    """Chequeo simple para saber si el servidor está vivo."""
    return {"status": "ok", "app": settings.app_name}


# --- Frontend ----------------------------------------------------------------
# Montamos la carpeta frontend en "/" para que FastAPI entregue los HTML/CSS/JS.
# Va AL FINAL: si estuviera antes, "taparía" las rutas /api.
# html=True hace que "/" devuelva automáticamente index.html.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
