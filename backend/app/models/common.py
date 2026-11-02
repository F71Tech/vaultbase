"""
Piezas compartidas por todos los modelos.

Convención de dinero: TODOS los montos se guardan como números enteros en
centésimos (campos que terminan en "_cents"). Ejemplo: $ 1.500,50 -> 150050.
Así evitamos los errores de redondeo de los decimales (0.1 + 0.2 != 0.3).
"""

import datetime as dt
from enum import Enum
from typing import ClassVar

from pydantic import model_validator
from sqlmodel import SQLModel


def utcnow() -> dt.datetime:
    """Fecha y hora actual en UTC (hora universal, independiente del país)."""
    return dt.datetime.now(dt.timezone.utc)


class Currency(str, Enum):
    """Monedas soportadas. La moneda base de la app es el peso uruguayo."""

    UYU = "UYU"
    USD = "USD"


class UpdateSchema(SQLModel):
    """
    Base para los esquemas de edición (PATCH).

    En un PATCH todos los campos son opcionales: mandás solo lo que cambia.
    Pero "opcional" no significa que se pueda borrar: por ejemplo, un gasto
    no puede quedar sin monto. Cada esquema lista en `nullable_fields` los
    campos que SÍ se pueden vaciar enviando null (ej: la fecha límite de una meta).
    """

    nullable_fields: ClassVar[set[str]] = set()

    @model_validator(mode="after")
    def _rechazar_nulos(self):
        for name in self.model_fields_set:  # solo los campos que el cliente envió
            if getattr(self, name) is None and name not in self.nullable_fields:
                raise ValueError(f"El campo '{name}' no puede ser nulo")
        return self
