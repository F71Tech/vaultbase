"""
Usuario y esquemas relacionados con el login.

Patrón que vas a ver en todos los modelos:
  - XBase:   campos que comparten todas las versiones.
  - X:       la TABLA real (table=True). Tiene id y datos internos.
  - XCreate: lo que el cliente manda para crear.
  - XRead:   lo que la API devuelve (nunca incluye datos sensibles).
  - XUpdate: lo que el cliente manda para editar (todo opcional).
"""

import datetime as dt

from pydantic import EmailStr, field_validator
from sqlmodel import Field, SQLModel

from .common import UpdateSchema, utcnow


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    name: str = Field(min_length=1, max_length=80)


class User(UserBase, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    # Guardamos el HASH de la contraseña, nunca la contraseña en sí.
    hashed_password: str
    # % del ingreso disponible destinado a comida (configurable por usuario)
    food_budget_pct: int = Field(default=30, ge=0, le=100)
    # El usuario aceptó que el administrador vea sus datos (para ayudarlo).
    # Sin esto, el administrador solo ve estadísticas de uso, nunca montos.
    shares_data: bool = False
    # Ya vio el tutorial (se guarda en la cuenta: sale solo la primera vez, en cualquier aparato)
    tour_done: bool = False
    # Sube al cambiar la contraseña: las sesiones firmadas con un número anterior dejan de valer.
    token_version: int = 0
    created_at: dt.datetime = Field(default_factory=utcnow)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        # "Ana@Mail.com" y "ana@mail.com" deben ser el mismo usuario
        return value.strip().lower()


class UserRead(UserBase):
    id: int
    food_budget_pct: int
    shares_data: bool
    tour_done: bool
    is_admin: bool = False    # no se guarda: sale de la configuración (ADMIN_EMAILS)
    created_at: dt.datetime


class UserUpdate(UpdateSchema):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    food_budget_pct: int | None = Field(default=None, ge=0, le=100)
    shares_data: bool | None = None
    tour_done: bool | None = None


class PasswordChange(SQLModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetIn(SQLModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class Token(SQLModel):
    """Respuesta del login: el token que el frontend guarda y reenvía."""

    access_token: str
    token_type: str = "bearer"
