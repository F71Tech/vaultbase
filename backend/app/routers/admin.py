"""
Panel del administrador (los emails de ADMIN_EMAILS en la configuración).

Privacidad primero:
  - De todos los usuarios ves solo ESTADÍSTICAS DE USO (cuándo entró, cuántas
    cosas cargó), nunca montos ni descripciones.
  - Los datos financieros de alguien los ves solo si esa persona activó
    "Compartir mis datos con el administrador" en Mi cuenta.
  - Las contraseñas no se pueden ver (son hashes): podés generar un link de un
    solo uso para que la persona elija una nueva.
"""

import datetime as dt
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import func, select

from ..config import get_settings
from ..deps import CurrentUser, SessionDep
from ..models import Commission, Expense, Feedback, Goal, Income, PasswordReset, Subscription, User
from ..models.common import today_uy, utcnow
from ..services import cashflow, finance
from ..services.demo import DEMO_DOMAIN
from .auth import hash_token
from .finance import _load_data, _usd_rate

RESET_HOURS = 24


def require_admin(user: CurrentUser) -> User:
    if not get_settings().is_admin(user.email):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo para el administrador")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
router = APIRouter(prefix="/api/admin", tags=["Administrador"])


class UserUsage(BaseModel):
    id: int
    email: str
    name: str
    created_at: dt.datetime
    last_activity: dt.datetime | None   # lo último que cargó (gasto, ingreso, meta…)
    expenses: int
    incomes: int
    goals: int
    subscriptions: int
    commissions: int
    feedback: int
    shares_data: bool


@router.get("/users", response_model=list[UserUsage])
def users(session: SessionDep, _: AdminUser):
    """Usuarios reales (sin las demos) con estadísticas de uso. Sin montos."""
    result = []
    people = session.exec(select(User).where(~User.email.endswith(f"@{DEMO_DOMAIN}")).order_by(User.created_at.desc()))
    for u in people:
        def count(model):
            return session.exec(select(func.count()).select_from(model).where(model.user_id == u.id)).one()

        def last(model):
            return session.exec(select(func.max(model.created_at)).where(model.user_id == u.id)).one()

        moments = [m for m in (last(Expense), last(Income), last(Goal), last(Subscription), last(Commission)) if m]
        result.append(UserUsage(
            id=u.id, email=u.email, name=u.name, created_at=u.created_at,
            last_activity=max(moments) if moments else None,
            expenses=count(Expense), incomes=count(Income), goals=count(Goal),
            subscriptions=count(Subscription), commissions=count(Commission), feedback=count(Feedback),
            shares_data=u.shares_data,
        ))
    return result


@router.post("/users/{user_id}/reset-link")
def reset_link(user_id: int, request: Request, session: SessionDep, _: AdminUser):
    """
    Genera un link de un solo uso (vence en 24 h) para que la persona elija una
    contraseña nueva. Mandáselo por un canal de confianza (ej: WhatsApp).
    """
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    token = secrets.token_urlsafe(32)   # 32 bytes al azar: imposible de adivinar
    session.add(PasswordReset(user_id=user.id, token_hash=hash_token(token),
                              expires_at=utcnow() + dt.timedelta(hours=RESET_HOURS)))
    session.commit()
    base = str(request.base_url).rstrip("/")
    return {"url": f"{base}/restablecer.html?token={token}", "expires_hours": RESET_HOURS}


@router.get("/users/{user_id}/data")
def user_data(user_id: int, session: SessionDep, _: AdminUser):
    """Los datos de un usuario, SOLO si aceptó compartirlos (para ayudarlo)."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if not user.shares_data:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta persona no compartió sus datos")
    data = _load_data(session, user)
    rate = _usd_rate(session)
    today = today_uy()
    try:
        capacity = finance.savings_capacity(data, today, rate)
        money = cashflow.money_now(data, today, rate)
    except finance.RateMissing:
        capacity = money = None
    expenses = sorted(data.expenses, key=lambda e: e.date, reverse=True)[:60]
    return {
        "user": {"name": user.name, "email": user.email, "created_at": user.created_at},
        "capacity": capacity, "money": money,
        "incomes": data.incomes, "expenses": expenses, "goals": data.goals,
        "subscriptions": data.subscriptions, "commissions": data.commissions, "pay_records": data.pay_records,
    }


@router.get("/feedback")
def feedback(session: SessionDep, _: AdminUser):
    """Los comentarios que mandaron los usuarios, del más nuevo al más viejo."""
    rows = session.exec(
        select(Feedback, User.email, User.name).join(User, User.id == Feedback.user_id)
        .order_by(Feedback.created_at.desc()).limit(200)
    ).all()
    return [{"id": f.id, "message": f.message, "page": f.page, "created_at": f.created_at,
             "email": email, "name": name} for f, email, name in rows]
