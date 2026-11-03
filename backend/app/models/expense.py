"""
Gastos.

- Fijo (fixed): se repite todos los meses desde `date` (alquiler, UTE, internet).
- Variable (variable): los gastos del día a día ("hoy me compré un alfajor",
  el súper, un taxi). Con ellos se calcula "lo que solés gastar por día".
- Puntual (one_off): algo que pasa una vez y no es habitual (una campera, un
  regalo, un arreglo). Cuenta el día que ocurre, pero NO entra en el promedio,
  así un gasto grande y raro no te "infla" el gasto diario. Puede tener fecha
  futura ("el 20 tengo un cumpleaños"): la simulación lo descuenta ese día.

Cada gasto tiene una categoría principal (ej: food) y, opcionalmente, una
subcategoría (ej: snacks). El árbol completo está en categories.py.
"""

import datetime as dt
from enum import Enum

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from ..categories import CATEGORY_TREE, is_valid_subcategory
from .common import Currency, UpdateSchema, enum_column, today_uy, utcnow


class ExpenseCategory(str, Enum):
    # Deben coincidir con las claves de CATEGORY_TREE (hay un test que lo controla)
    food = "food"                    # comida
    transport = "transport"          # transporte
    housing = "housing"              # vivienda
    utilities = "utilities"          # servicios (UTE, OSE, Antel)
    health = "health"                # salud
    personal_care = "personal_care"  # cuidado personal
    education = "education"          # educación
    leisure = "leisure"              # ocio
    clothing = "clothing"            # ropa
    tech = "tech"                    # tecnología
    pets = "pets"                    # mascotas
    gifts = "gifts"                  # regalos y donaciones
    finance = "finance"              # bancos e impuestos
    other = "other"                  # otros


def check_subcategory(category, subcategory) -> None:
    """Lanza un error claro si la subcategoría no pertenece a la categoría."""
    if not is_valid_subcategory(category, subcategory):
        key = getattr(category, "value", category)
        validas = ", ".join(CATEGORY_TREE[key]["subcategories"]) or "ninguna"
        raise ValueError(
            f"La subcategoría '{subcategory}' no pertenece a '{key}'. Válidas: {validas}"
        )


class ExpenseKind(str, Enum):
    fixed = "fixed"
    variable = "variable"
    one_off = "one_off"   # puntual (no tiene el CHECK de la base: se guarda como texto)


class ExpenseBase(SQLModel):
    category: ExpenseCategory = Field(sa_type=enum_column(ExpenseCategory))
    subcategory: str | None = Field(default=None, max_length=30)  # vacía = "general"
    amount_cents: int = Field(gt=0)
    currency: Currency = Field(default=Currency.UYU, sa_type=enum_column(Currency))
    kind: ExpenseKind = Field(default=ExpenseKind.variable, sa_type=enum_column(ExpenseKind))
    date: dt.date = Field(default_factory=today_uy)
    # Solo para gastos fijos: hasta cuándo se repiten (vacío = sigue vigente)
    end_date: dt.date | None = None
    description: str | None = Field(default=None, max_length=120)
    # Cotización del dólar el día del gasto (pesos por 1 USD).
    # Guardarla congela el valor histórico: un gasto de marzo no cambia si el
    # dólar sube en noviembre. En la Etapa 2 se completa automáticamente.
    exchange_rate: float | None = Field(default=None, gt=0)
    # Comida: ¿con qué la pagaste? True = ticket de alimentación, False = tu
    # plata, None = automático (la comida se paga primero con el ticket).
    paid_with_ticket: bool | None = None


class Expense(ExpenseBase, table=True):
    __tablename__ = "expenses"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class ExpenseCreate(ExpenseBase):
    @model_validator(mode="after")
    def _validar_subcategoria(self):
        check_subcategory(self.category, self.subcategory)
        return self


class ExpenseRead(ExpenseBase):
    id: int
    created_at: dt.datetime


class ExpenseUpdate(UpdateSchema):
    nullable_fields = {"subcategory", "end_date", "description", "exchange_rate", "paid_with_ticket"}

    category: ExpenseCategory | None = None
    subcategory: str | None = Field(default=None, max_length=30)
    amount_cents: int | None = Field(default=None, gt=0)
    currency: Currency | None = None
    kind: ExpenseKind | None = None
    date: dt.date | None = None
    end_date: dt.date | None = None
    description: str | None = Field(default=None, max_length=120)
    exchange_rate: float | None = Field(default=None, gt=0)
    paid_with_ticket: bool | None = None
