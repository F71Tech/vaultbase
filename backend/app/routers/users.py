"""Datos y preferencias del usuario logueado."""

from fastapi import APIRouter

from ..deps import CurrentUser, SessionDep
from ..models import UserRead, UserUpdate

router = APIRouter(prefix="/api/users", tags=["Usuario"])


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser):
    """Devuelve el usuario dueño del token."""
    return user


@router.patch("/me", response_model=UserRead)
def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep):
    """Edita nombre o % de presupuesto de comida. Solo cambia lo que se envía."""
    user.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
