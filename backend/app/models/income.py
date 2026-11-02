"""Ingresos: sueldo, changas, alquileres cobrados, etc."""

import datetime as dt
from enum import Enum

from pydantic import model_validator
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
    # CUÁNDO entra la plata (para "Tu plata hoy"). Solo aplica a ingresos mensuales:
    pay_day: int = Field(default=1, ge=1, le=31)              # día del mes en que se cobra
    # Adelanto: una PARTE fija del ingreso que se cobra antes (ej: el 15).
    # amount_cents sigue siendo el total del mes: el día de cobro llega el resto.
    advance_cents: int | None = Field(default=None, gt=0)
    advance_day: int | None = Field(default=None, ge=1, le=31)


def check_advance(advance_cents: int | None, amount_cents: int | None) -> None:
    """El adelanto es parte del ingreso: no puede ser mayor o igual al total."""
    if advance_cents and amount_cents and advance_cents >= amount_cents:
        raise ValueError("El adelanto tiene que ser menor que el monto total del mes")


class Income(IncomeBase, table=True):
    __tablename__ = "incomes"

    id: int | None = Field(default=None, primary_key=True)
    # foreign_key: cada ingreso "pertenece" a un usuario
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class IncomeCreate(IncomeBase):
    @model_validator(mode="after")
    def _adelanto_valido(self):
        check_advance(self.advance_cents, self.amount_cents)
        return self


class IncomeRead(IncomeBase):
    id: int
    created_at: dt.datetime


class IncomeUpdate(UpdateSchema):
    nullable_fields = {"end_date", "nominal_cents", "aguinaldo_cents", "advance_cents", "advance_day"}

    source: str | None = Field(default=None, min_length=1, max_length=80)
    amount_cents: int | None = Field(default=None, gt=0)
    currency: Currency | None = None
    frequency: IncomeFrequency | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    nominal_cents: int | None = Field(default=None, gt=0)
    aguinaldo_cents: int | None = Field(default=None, ge=0)
    pay_day: int | None = Field(default=None, ge=1, le=31)
    advance_cents: int | None = Field(default=None, gt=0)
    advance_day: int | None = Field(default=None, ge=1, le=31)
