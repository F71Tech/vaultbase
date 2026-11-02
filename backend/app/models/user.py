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
    # "Tu plata hoy": cuánta plata dijo tener (cuentas + efectivo) y CUÁNDO lo dijo.
    # Desde ese momento la app suma cobros y resta gastos para estimar el saldo actual.
    balance_cents: int | None = None
    balance_at: dt.datetime | None = None
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
    balance_cents: int | None
    balance_at: dt.datetime | None
    created_at: dt.datetime


class UserUpdate(UpdateSchema):
    nullable_fields = {"balance_cents"}  # null = "dejar de usar Tu plata hoy"

    name: str | None = Field(default=None, min_length=1, max_length=80)
    food_budget_pct: int | None = Field(default=None, ge=0, le=100)
    # Puede ser negativo (ej: tarjeta o cuenta en rojo)
    balance_cents: int | None = Field(default=None, ge=-100_000_000_000, le=100_000_000_000)


class Token(SQLModel):
    """Respuesta del login: el token que el frontend guarda y reenvía."""

    access_token: str
    token_type: str = "bearer"
