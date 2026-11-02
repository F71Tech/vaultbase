"""Datos y preferencias del usuario logueado."""

from fastapi import APIRouter, Response, status

from ..deps import CurrentUser, SessionDep
from ..models import UserRead, UserUpdate
from ..models.common import utcnow
from ..services.accounts import delete_user_data

router = APIRouter(prefix="/api/users", tags=["Usuario"])


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser):
    """Devuelve el usuario dueño del token."""
    return user


@router.patch("/me", response_model=UserRead)
def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep):
    """Edita nombre, % de comida o tu saldo actual. Solo cambia lo que se envía."""
    changes = data.model_dump(exclude_unset=True)
    if "balance_cents" in changes:
        # El momento exacto importa: los gastos anotados DESPUÉS se restan del saldo
        changes["balance_at"] = utcnow() if changes["balance_cents"] is not None else None
    user.sqlmodel_update(changes)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUser, session: SessionDep):
    """Borra tu cuenta y TODOS tus datos. No se puede deshacer."""
    delete_user_data(session, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
