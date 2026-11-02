"""Registro e inicio de sesión."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from ..deps import SessionDep
from ..models import Token, User, UserCreate, UserRead
from ..security import DUMMY_HASH, create_access_token, hash_password, verify_password
from ..services.demo import create_demo_user

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, session: SessionDep):
    """Crea una cuenta nueva."""
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing:
        # 409 Conflict: el recurso ya existe
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese email")

    # model_validate copia los campos de UserCreate; "update" agrega el hash.
    # La contraseña original NO se guarda en ningún lado.
    user = User.model_validate(data, update={"hashed_password": hash_password(data.password)})
    session.add(user)      # lo prepara para guardar
    session.commit()       # lo guarda de verdad en la base de datos
    session.refresh(user)  # recarga el objeto (ahora tiene id)
    return user


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    """
    Inicia sesión y devuelve un token JWT.

    Usa el formato estándar OAuth2 (formulario con `username` y `password`).
    En `username` va el email.
    """
    email = form.username.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()

    # Siempre verificamos un hash (aunque el usuario no exista) para que la
    # respuesta tarde lo mismo en ambos casos.
    valid = verify_password(form.password, user.hashed_password if user else DUMMY_HASH)
    if not user or not valid:
        # Mismo mensaje para email inexistente y contraseña incorrecta:
        # no le damos pistas a alguien que esté probando cuentas.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.post("/demo", response_model=Token)
def demo(session: SessionDep):
    """
    Crea una cuenta demo con datos de ejemplo y devuelve su token.
    Cada visitante recibe su propia demo; se borran solas a las pocas horas.
    """
    user = create_demo_user(session)
    return Token(access_token=create_access_token(user.id))
