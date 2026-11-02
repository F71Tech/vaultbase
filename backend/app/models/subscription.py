"""
Suscripciones: Spotify, YouTube Premium, Claude, Netflix...

Para los cálculos cuentan como un gasto fijo. Muchas se cobran en dólares,
por eso tienen moneda propia.
"""

import datetime as dt
from enum import Enum

from sqlmodel import Field, SQLModel

from .common import Currency, UpdateSchema, utcnow


class SubscriptionFrequency(str, Enum):
    monthly = "monthly"
    annual = "annual"


class SubscriptionBase(SQLModel):
    name: str = Field(min_length=1, max_length=80)
    amount_cents: int = Field(gt=0)
    currency: Currency = Currency.USD
    frequency: SubscriptionFrequency = SubscriptionFrequency.monthly
    billing_day: int = Field(default=1, ge=1, le=31)  # día del mes en que se cobra
    active: bool = True  # pausada = False (no cuenta en los cálculos)


class Subscription(SubscriptionBase, table=True):
    __tablename__ = "subscriptions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionRead(SubscriptionBase):
    id: int
    created_at: dt.datetime


class SubscriptionUpdate(UpdateSchema):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    amount_cents: int | None = Field(default=None, gt=0)
    currency: Currency | None = None
    frequency: SubscriptionFrequency | None = None
    billing_day: int | None = Field(default=None, ge=1, le=31)
    active: bool | None = None
