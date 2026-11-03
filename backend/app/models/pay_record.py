"""
Cobros reales: lo que DE VERDAD te entró un día de cobro.

Un sueldo mensual es una estimación ("cobro $ X el 30"). Cuando el monto varía
(comisiones, horas extra…), anotás el cobro real y ese número manda para ese
día. Los cobros futuros se estiman con el último cobro real.

kind: "pay" = el cobro del día de cobro; "advance" = el adelanto.
"""

import datetime as dt
from enum import Enum

from sqlmodel import Field, SQLModel

from .common import UpdateSchema, enum_column, utcnow


class PayKind(str, Enum):
    pay = "pay"            # el cobro del día de cobro (lo que queda después del adelanto)
    advance = "advance"    # el adelanto


class PayRecordBase(SQLModel):
    income_id: int = Field(foreign_key="incomes.id", index=True)
    date: dt.date
    kind: PayKind = Field(default=PayKind.pay, sa_type=enum_column(PayKind))
    amount_cents: int = Field(ge=0)   # lo que te entró en mano


class PayRecord(PayRecordBase, table=True):
    __tablename__ = "pay_records"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class PayRecordCreate(PayRecordBase):
    pass


class PayRecordRead(PayRecordBase):
    id: int
    created_at: dt.datetime


class PayRecordUpdate(UpdateSchema):
    date: dt.date | None = None
    kind: PayKind | None = None
    amount_cents: int | None = Field(default=None, ge=0)
