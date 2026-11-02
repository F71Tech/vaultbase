"""Compras deseadas: cosas que quiero comprar y puedo simular antes."""

import datetime as dt
from enum import Enum

from sqlmodel import Field, SQLModel

from .common import Currency, UpdateSchema, enum_column, utcnow


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class WishItemBase(SQLModel):
    name: str = Field(min_length=1, max_length=80)
    cost_cents: int = Field(gt=0)
    currency: Currency = Field(default=Currency.UYU, sa_type=enum_column(Currency))
    priority: Priority = Field(default=Priority.medium, sa_type=enum_column(Priority))
    notes: str | None = Field(default=None, max_length=200)


class WishItem(WishItemBase, table=True):
    __tablename__ = "wish_items"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class WishItemCreate(WishItemBase):
    pass


class WishItemRead(WishItemBase):
    id: int
    created_at: dt.datetime


class WishItemUpdate(UpdateSchema):
    nullable_fields = {"notes"}

    name: str | None = Field(default=None, min_length=1, max_length=80)
    cost_cents: int | None = Field(default=None, gt=0)
    currency: Currency | None = None
    priority: Priority | None = None
    notes: str | None = Field(default=None, max_length=200)
