"""Datos y preferencias del usuario logueado."""

from fastapi import APIRouter, HTTPException, Response, status

from ..config import get_settings
from ..deps import CurrentUser, SessionDep
from ..models import Feedback, FeedbackCreate, PasswordChange, Token, User, UserRead, UserUpdate
from ..security import create_access_token, hash_password, verify_password
from ..services.accounts import delete_user_data

router = APIRouter(prefix="/api/users", tags=["Usuario"])


def as_read(user: User) -> UserRead:
    """El usuario para mostrar, con "¿es administrador?" (sale de la configuración)."""
    return UserRead.model_validate(user, update={"is_admin": get_settings().is_admin(user.email)})


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser):
    """Devuelve el usuario dueño del token."""
    return as_read(user)


@router.patch("/me", response_model=UserRead)
def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep):
    """Edita nombre, % de comida o si compartís tus datos. Solo cambia lo que se envía."""
    user.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(user)
    session.commit()
    session.refresh(user)
    return as_read(user)


@router.post("/me/password", response_model=Token)
def change_password(data: PasswordChange, user: CurrentUser, session: SessionDep):
    """
    Cambia tu contraseña (hay que saber la actual) y cierra las sesiones de tus
    otros aparatos. Devuelve un token nuevo para que este aparato siga adentro.
    """
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    user.hashed_password = hash_password(data.new_password)
    user.token_version += 1
    session.add(user)
    session.commit()
    return Token(access_token=create_access_token(user.id, user.token_version))


@router.post("/me/feedback", status_code=status.HTTP_201_CREATED)
def send_feedback(data: FeedbackCreate, user: CurrentUser, session: SessionDep):
    """Un comentario para el administrador: algo que no se entendió, una idea, un error."""
    session.add(Feedback.model_validate(data, update={"user_id": user.id}))
    session.commit()
    return {"ok": True}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUser, session: SessionDep):
    """Borra tu cuenta y TODOS tus datos. No se puede deshacer."""
    delete_user_data(session, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
