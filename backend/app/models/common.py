"""
Piezas compartidas por todos los modelos.

Convención de dinero: TODOS los montos se guardan como números enteros en
centésimos (campos que terminan en "_cents"). Ejemplo: $ 1.500,50 -> 150050.
Así evitamos los errores de redondeo de los decimales (0.1 + 0.2 != 0.3).
"""

import datetime as dt
from enum import Enum
from typing import ClassVar
from zoneinfo import ZoneInfo

from pydantic import model_validator
from sqlalchemy import Enum as SAEnum
from sqlmodel import SQLModel

URUGUAY_TZ = ZoneInfo("America/Montevideo")


def utcnow() -> dt.datetime:
    """Fecha y hora actual en UTC (hora universal, independiente del país)."""
    return dt.datetime.now(dt.timezone.utc)


def today_uy() -> dt.date:
    """
    Qué día es HOY en Uruguay.

    El servidor de deploy suele estar en hora UTC (3 horas adelante): a las
    22:00 de Montevideo, en UTC ya es "mañana". Por eso no usamos date.today().
    """
    return dt.datetime.now(URUGUAY_TZ).date()


class Currency(str, Enum):
    """Monedas soportadas. La moneda base de la app es el peso uruguayo."""

    UYU = "UYU"
    USD = "USD"


def enum_column(enum_class: type[Enum]) -> SAEnum:
    """
    Cómo se guarda un Enum en la base: como TEXTO común (native_enum=False).

    PostgreSQL tiene "tipos enum nativos", pero traen dos problemas:
      - agregar una opción nueva (ej: una categoría) exige una migración especial;
      - si dos tablas usan el mismo enum (la moneda está en 4), las migraciones
        intentan crear el tipo varias veces y fallan.
    Como texto, la validación igual la hace Python (pydantic) antes de guardar.
    """
    return SAEnum(enum_class, native_enum=False, length=20)


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
