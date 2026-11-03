"""
Soporte: restablecer contraseñas y comentarios de los usuarios.

Contraseñas: NUNCA se pueden "ver" (se guardan como hash, sin vuelta atrás).
Si alguien la olvida, el administrador genera un LINK de un solo uso que vence
en 24 horas; la persona entra y elige una nueva. Del link guardamos solo su
hash: si alguien leyera la base, no podría usarlo.
"""

import datetime as dt

from sqlmodel import Field, SQLModel

from .common import utcnow


class PasswordReset(SQLModel, table=True):
    __tablename__ = "password_resets"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    token_hash: str = Field(max_length=64, index=True)   # sha256 del token (nunca el token)
    expires_at: dt.datetime
    used_at: dt.datetime | None = None
    created_at: dt.datetime = Field(default_factory=utcnow)


class FeedbackBase(SQLModel):
    message: str = Field(min_length=1, max_length=1000)
    page: str | None = Field(default=None, max_length=120)   # en qué pantalla estaba


class Feedback(FeedbackBase, table=True):
    __tablename__ = "feedback"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class FeedbackCreate(FeedbackBase):
    pass
