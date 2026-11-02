"""
Cotizaciones del dólar guardadas por el servidor.

En la Etapa 2, un servicio las consulta automáticamente (BCU y respaldo) y
las guarda acá. Es una tabla compartida: no pertenece a ningún usuario.
"""

import datetime as dt

from sqlmodel import Field, SQLModel

from .common import utcnow


class ExchangeRate(SQLModel, table=True):
    __tablename__ = "exchange_rates"

    id: int | None = Field(default=None, primary_key=True)
    currency: str = Field(default="USD", max_length=3, index=True)
    rate: float = Field(gt=0)           # pesos uruguayos por 1 unidad de la moneda
    rate_date: dt.date = Field(index=True)  # fecha a la que corresponde la cotización
    source: str = Field(max_length=40)  # de dónde salió (ej: "BCU")
    fetched_at: dt.datetime = Field(default_factory=utcnow)  # cuándo la consultamos
