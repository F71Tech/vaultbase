"""
Gastos.

- Fijo (fixed): se repite todos los meses desde `date` (alquiler, UTE, internet).
- Variable (variable): ocurre una vez, el día `date` (el súper, un taxi, una salida).
  Los gastos del día a día son variables.
"""

import datetime as dt
from enum import Enum

from sqlmodel import Field, SQLModel

from .common import Currency, UpdateSchema, utcnow


class ExpenseCategory(str, Enum):
    food = "food"                # comida / supermercado
    transport = "transport"      # transporte
    housing = "housing"          # vivienda (alquiler, gastos comunes)
    utilities = "utilities"      # servicios (UTE, OSE, Antel, internet)
    health = "health"            # salud
    education = "education"      # educación
    leisure = "leisure"          # ocio / salidas
    clothing = "clothing"        # ropa
    tech = "tech"                # tecnología
    pets = "pets"                # mascotas
    gifts = "gifts"              # regalos
    other = "other"              # otros


class ExpenseKind(str, Enum):
    fixed = "fixed"
    variable = "variable"


class ExpenseBase(SQLModel):
    category: ExpenseCategory
    amount_cents: int = Field(gt=0)
    currency: Currency = Currency.UYU
    kind: ExpenseKind = ExpenseKind.variable
    date: dt.date = Field(default_factory=dt.date.today)
    # Solo para gastos fijos: hasta cuándo se repiten (vacío = sigue vigente)
    end_date: dt.date | None = None
    description: str | None = Field(default=None, max_length=120)
    # Cotización del dólar el día del gasto (pesos por 1 USD).
    # Guardarla congela el valor histórico: un gasto de marzo no cambia si el
    # dólar sube en noviembre. En la Etapa 2 se completa automáticamente.
    exchange_rate: float | None = Field(default=None, gt=0)


class Expense(ExpenseBase, table=True):
    __tablename__ = "expenses"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseRead(ExpenseBase):
    id: int
    created_at: dt.datetime


class ExpenseUpdate(UpdateSchema):
    nullable_fields = {"end_date", "description", "exchange_rate"}

    category: ExpenseCategory | None = None
    amount_cents: int | None = Field(default=None, gt=0)
    currency: Currency | None = None
    kind: ExpenseKind | None = None
    date: dt.date | None = None
    end_date: dt.date | None = None
    description: str | None = Field(default=None, max_length=120)
    exchange_rate: float | None = Field(default=None, gt=0)
