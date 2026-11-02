"""Metas de ahorro: "Viaje a Brasil", "Fondo de emergencia", etc."""

import datetime as dt

from sqlmodel import Field, SQLModel

from .common import UpdateSchema, utcnow


class GoalBase(SQLModel):
    name: str = Field(min_length=1, max_length=80)
    target_cents: int = Field(gt=0)            # cuánto quiero juntar
    saved_cents: int = Field(default=0, ge=0)  # cuánto llevo ahorrado
    deadline: dt.date | None = None            # fecha límite (opcional)
    # Aporte mensual fijo (opcional). Si está vacío, la Etapa 2 le asigna
    # una parte del ahorro disponible automáticamente.
    monthly_contribution_cents: int | None = Field(default=None, ge=0)


class Goal(GoalBase, table=True):
    __tablename__ = "goals"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class GoalCreate(GoalBase):
    pass


class GoalRead(GoalBase):
    id: int
    created_at: dt.datetime


class GoalUpdate(UpdateSchema):
    nullable_fields = {"deadline", "monthly_contribution_cents"}

    name: str | None = Field(default=None, min_length=1, max_length=80)
    target_cents: int | None = Field(default=None, gt=0)
    saved_cents: int | None = Field(default=None, ge=0)
    deadline: dt.date | None = None
    monthly_contribution_cents: int | None = Field(default=None, ge=0)
