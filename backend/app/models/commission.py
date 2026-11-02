"""
Comisiones semanales (para sueldos con parte variable).

Cómo funciona en la vida real (y acá):
  - Cada semana (lunes a domingo) vendés y generás una comisión.
  - No sabés el monto exacto hasta el recibo, pero podés estimar un RANGO
    ("entre $ 14.000 y $ 19.000"). Cuando sepas el real, lo cargás en actual_cents.
  - Si la comisión de una semana no llega al bono mínimo semanal del sueldo
    (Income.commission_floor_cents, ej: $ 3.000), cobrás el bono.
  - Las semanas se cobran junto con el sueldo del mes en que TERMINAN
    (la semana del 26/10 al 1/11 termina en noviembre: se cobra con el sueldo de noviembre).
"""

import datetime as dt

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from .common import UpdateSchema, utcnow


def check_range(min_cents: int | None, max_cents: int | None) -> None:
    if min_cents is not None and max_cents is not None and min_cents > max_cents:
        raise ValueError("El mínimo no puede ser mayor que el máximo")


class CommissionBase(SQLModel):
    week_start: dt.date                              # el lunes de esa semana
    min_cents: int = Field(ge=0)                     # lo menos que esperás cobrar
    max_cents: int = Field(ge=0)                     # lo más que esperás cobrar
    actual_cents: int | None = Field(default=None, ge=0)  # lo que cobraste de verdad (cuando lo sepas)
    note: str | None = Field(default=None, max_length=120)  # ej: "356% de la meta"


class Commission(CommissionBase, table=True):
    __tablename__ = "commissions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class CommissionCreate(CommissionBase):
    @model_validator(mode="after")
    def _rango_valido(self):
        check_range(self.min_cents, self.max_cents)
        # Guardamos siempre el lunes: así "la semana del 28/10" y "del 26/10" son la misma
        self.week_start = self.week_start - dt.timedelta(days=self.week_start.weekday())
        return self


class CommissionRead(CommissionBase):
    id: int
    created_at: dt.datetime


class CommissionUpdate(UpdateSchema):
    nullable_fields = {"actual_cents", "note"}

    week_start: dt.date | None = None
    min_cents: int | None = Field(default=None, ge=0)
    max_cents: int | None = Field(default=None, ge=0)
    actual_cents: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=120)
