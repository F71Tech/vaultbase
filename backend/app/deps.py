"""
Dependencias reutilizables de FastAPI.

Una "dependencia" es algo que un endpoint necesita y que FastAPI le prepara
antes de ejecutarlo. Por ejemplo, si un endpoint declara `user: CurrentUser`,
FastAPI primero lee el token, busca al usuario y recién ahí llama al endpoint.
Si el token no es válido, responde 401 y el endpoint ni se ejecuta.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from .database import get_session
from .models import User
from .security import decode_access_token

# Le indica a FastAPI (y al botón "Authorize" de /docs) dónde se hace el login
# y que el token viaja en el header:  Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o vencida. Volvé a iniciar sesión.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    decoded = decode_access_token(token)
    if decoded is None:
        raise credentials_error
    user_id, version = decoded
    user = session.get(User, user_id)
    if user is None:  # el usuario fue borrado después de recibir el token
        raise credentials_error
    if version != user.token_version:  # cambió la contraseña después de recibir el token
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
