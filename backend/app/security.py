"""
Seguridad: contraseñas y tokens JWT.

1) Contraseñas: nunca se guardan tal cual. Guardamos un "hash": una huella
   que se calcula a partir de la contraseña, pero de la que NO se puede
   volver atrás. Para verificar un login, calculamos la huella de lo que
   escribió el usuario y la comparamos con la guardada.

2) JWT (JSON Web Token): después del login, el servidor entrega un token
   firmado con la SECRET_KEY. Es como una pulsera de un evento: el frontend
   la muestra en cada pedido y el servidor verifica que la firma sea válida
   (que nadie la haya falsificado) y que no esté vencida.
"""

import datetime as dt

import jwt
from pwdlib import PasswordHash

from .config import get_settings

settings = get_settings()
ALGORITHM = "HS256"  # algoritmo de firma del token

# Usa Argon2, el algoritmo recomendado hoy para hashear contraseñas
password_hash = PasswordHash.recommended()

# Hash "de relleno": se usa cuando el email no existe, para que el login tarde
# lo mismo exista o no el usuario (así no se puede adivinar qué emails existen).
DUMMY_HASH = password_hash.hash("contraseña-de-relleno")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: int, version: int = 0) -> str:
    """Crea un token que identifica al usuario y vence en N minutos."""
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        minutes=settings.access_token_expire_minutes
    )
    # "sub" (subject) = de quién es el token. "exp" = cuándo vence.
    # "ver" = la versión de sesión de la cuenta cuando se creó (ver models/user.py).
    payload = {"sub": str(user_id), "exp": expire, "ver": version}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> tuple[int, int] | None:
    """Devuelve (id del usuario, versión de sesión) si el token es válido; si no, None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        # Los tokens de antes no traen "ver": cuentan como versión 0, así nadie queda afuera
        return int(payload["sub"]), int(payload.get("ver", 0))
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        # Firma inválida, token vencido o con datos raros
        return None
