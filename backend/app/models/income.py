"""Ingresos: sueldo, changas, alquileres cobrados, etc."""

import datetime as dt
from enum import Enum

from sqlmodel import Field, SQLModel

from .common import Currency, UpdateSchema, enum_column, today_uy, utcnow


class IncomeFrequency(str, Enum):
    weekly = "weekly"        # semanal
    biweekly = "biweekly"    # quincenal
    monthly = "monthly"      # mensual
    annual = "annual"        # anual
    one_time = "one_time"    # una sola vez (ej: un trabajo puntual)


class IncomeBase(SQLModel):
    source: str = Field(min_length=1, max_length=80)  # ej: "Sueldo", "Freelance"
    amount_cents: int = Field(gt=0)
    currency: Currency = Field(default=Currency.UYU, sa_type=enum_column(Currency))
    frequency: IncomeFrequency = Field(default=IncomeFrequency.monthly, sa_type=enum_column(IncomeFrequency))
    # Desde cuándo se cobra (para un ingreso único: el día que se cobró)
    start_date: dt.date = Field(default_factory=today_uy)
    # Hasta cuándo se cobra (vacío = sigue vigente)
    end_date: dt.date | None = None
    # Solo para sueldos (los completa la calculadora de sueldo):
    nominal_cents: int | None = Field(default=None, gt=0)   # sueldo nominal mensual
    aguinaldo_cents: int | None = Field(default=None, ge=0)  # medio aguinaldo LÍQUIDO (junio y diciembre)


class Income(IncomeBase, table=True):
    __tablename__ = "incomes"

    id: int | None = Field(default=None, primary_key=True)
    # foreign_key: cada ingreso "pertenece" a un usuario
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class IncomeCreate(IncomeBase):
    pass


class IncomeRead(IncomeBase):
    id: int
    created_at: dt.datetime


class IncomeUpdate(UpdateSchema):
    nullable_fields = {"end_date", "nominal_cents", "aguinaldo_cents"}

    source: str | None = Field(default=None, min_length=1, max_length=80)
    amount_cents: int | None = Field(default=None, gt=0)
    currency: Currency | None = None
    frequency: IncomeFrequency | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    nominal_cents: int | None = Field(default=None, gt=0)
    aguinaldo_cents: int | None = Field(default=None, ge=0)
