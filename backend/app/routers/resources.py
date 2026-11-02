"""
Endpoints de ingresos, gastos, metas, suscripciones y compras deseadas.

Los cuatro primeros salen de la fábrica `build_crud_router`. Los gastos usan
la fábrica también, pero con un listado propio que permite filtrar por
fechas, categoría y tipo (lo vamos a necesitar para el dashboard).
"""

import datetime as dt
from typing import Annotated

from fastapi import Query
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import (
    Commission, CommissionCreate, CommissionRead, CommissionUpdate,
    Currency,
    Expense, ExpenseCategory, ExpenseCreate, ExpenseKind, ExpenseRead, ExpenseUpdate,
    Goal, GoalCreate, GoalRead, GoalUpdate,
    Income, IncomeCreate, IncomeRead, IncomeUpdate,
    Subscription, SubscriptionCreate, SubscriptionRead, SubscriptionUpdate,
    WishItem, WishItemCreate, WishItemRead, WishItemUpdate,
)
from ..models.commission import check_range
from ..models.expense import check_subcategory
from ..models.income import check_advance
from ..services.exchange import RateUnavailable, rate_for_date
from .crud import build_crud_router


def freeze_exchange_rate(expense: Expense, session) -> None:
    """
    Si el gasto es en dólares y no trae cotización, guardamos la del día del
    gasto. Así su valor en pesos queda "congelado" para siempre.
    (Al editar, el frontend manda exchange_rate=null si cambió la fecha o la
    moneda, para que se vuelva a calcular.)
    """
    if expense.currency == Currency.USD and expense.exchange_rate is None:
        try:
            expense.exchange_rate = rate_for_date(session, expense.date)
        except RateUnavailable:
            pass  # sin cotización: los cálculos usarán la actual cuando exista


incomes_router = build_crud_router(
    model=Income, create_schema=IncomeCreate, read_schema=IncomeRead,
    update_schema=IncomeUpdate, prefix="/api/incomes", tag="Ingresos",
    order_by=Income.start_date,
    # al editar solo el monto o solo el adelanto, igual hay que revisar los dos juntos
    validate_item=lambda i: check_advance(i.advance_cents, i.amount_cents),
)

def check_commission(c: Commission) -> None:
    """Al editar: el rango tiene que tener sentido y la semana empieza el lunes."""
    check_range(c.min_cents, c.max_cents)
    c.week_start = c.week_start - dt.timedelta(days=c.week_start.weekday())


commissions_router = build_crud_router(
    model=Commission, create_schema=CommissionCreate, read_schema=CommissionRead,
    update_schema=CommissionUpdate, prefix="/api/commissions", tag="Comisiones",
    order_by=Commission.week_start.desc(),
    validate_item=lambda c: check_commission(c),
)

goals_router = build_crud_router(
    model=Goal, create_schema=GoalCreate, read_schema=GoalRead,
    update_schema=GoalUpdate, prefix="/api/goals", tag="Metas",
    order_by=Goal.created_at,
)

subscriptions_router = build_crud_router(
    model=Subscription, create_schema=SubscriptionCreate, read_schema=SubscriptionRead,
    update_schema=SubscriptionUpdate, prefix="/api/subscriptions", tag="Suscripciones",
    order_by=Subscription.billing_day,
)

wishlist_router = build_crud_router(
    model=WishItem, create_schema=WishItemCreate, read_schema=WishItemRead,
    update_schema=WishItemUpdate, prefix="/api/wishlist", tag="Compras deseadas",
    order_by=WishItem.created_at,
)

expenses_router = build_crud_router(
    model=Expense, create_schema=ExpenseCreate, read_schema=ExpenseRead,
    update_schema=ExpenseUpdate, prefix="/api/expenses", tag="Gastos",
    order_by=Expense.date, include_list=False,
    validate_item=lambda e: check_subcategory(e.category, e.subcategory),
    before_save=freeze_exchange_rate,
)


@expenses_router.get("", response_model=list[ExpenseRead], summary="Listar gastos")
def list_expenses(
    session: SessionDep,
    user: CurrentUser,
    # Query(...) = parámetros opcionales en la URL, ej: /api/expenses?category=food
    from_date: Annotated[dt.date | None, Query(description="Desde (incluida)")] = None,
    to_date: Annotated[dt.date | None, Query(description="Hasta (incluida)")] = None,
    category: ExpenseCategory | None = None,
    subcategory: str | None = None,
    # Se puede repetir: ?kind=variable&kind=one_off trae los dos tipos
    kind: Annotated[list[ExpenseKind] | None, Query(description="Tipo(s) de gasto")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Lista los gastos del usuario, del más nuevo al más viejo, con filtros opcionales."""
    stmt = select(Expense).where(Expense.user_id == user.id)
    # Vamos agregando condiciones solo si el filtro vino en la URL
    if from_date:
        stmt = stmt.where(Expense.date >= from_date)
    if to_date:
        stmt = stmt.where(Expense.date <= to_date)
    if category:
        stmt = stmt.where(Expense.category == category)
    if subcategory:
        stmt = stmt.where(Expense.subcategory == subcategory)
    if kind:
        stmt = stmt.where(Expense.kind.in_(kind))
    stmt = stmt.order_by(Expense.date.desc(), Expense.id.desc()).offset(offset).limit(limit)
    return session.exec(stmt).all()
