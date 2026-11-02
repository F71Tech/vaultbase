"""
Endpoints de cálculos: resúmenes, presupuesto de comida, metas, simulador y
cotización del dólar.

Este archivo es "la capa fina": busca los datos del usuario en la base,
consigue la cotización y le pasa todo a los servicios (que hacen las cuentas).
"""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, select

from ..deps import CurrentUser, SessionDep
from ..models import Currency, Expense, Goal, Income, Subscription, User, WishItem
from ..models.common import today_uy
from ..services import cashflow, finance, goal_plan
from ..services.exchange import RateUnavailable, get_current_rate
from ..services.simulator import InstallmentOption, SimulationResult, simulate_purchase

router = APIRouter(prefix="/api", tags=["Finanzas"])


# --- Ayudantes --------------------------------------------------------------

def _load_data(session: Session, user: User) -> finance.FinanceData:
    """Trae de la base todo lo que el usuario cargó."""
    def mine(model):
        return list(session.exec(select(model).where(model.user_id == user.id)).all())

    return finance.FinanceData(
        incomes=mine(Income), expenses=mine(Expense),
        subscriptions=mine(Subscription), goals=mine(Goal),
    )


def _usd_rate(session: Session) -> float | None:
    try:
        return get_current_rate(session).rate
    except RateUnavailable:
        return None  # solo es un problema si el usuario tiene cosas en dólares


def _rate_error() -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "No se pudo obtener la cotización del dólar. Probá de nuevo en unos minutos.",
    )


# --- Cotización -------------------------------------------------------------

class ExchangeRateOut(BaseModel):
    currency: str
    rate: float
    rate_date: dt.date
    source: str
    fetched_at: dt.datetime


@router.get("/exchange-rate", response_model=ExchangeRateOut, tags=["Cotización"])
def exchange_rate(session: SessionDep):
    """Cotización actual del dólar (pesos por 1 USD). Pública, no requiere login."""
    try:
        return get_current_rate(session)
    except RateUnavailable:
        raise _rate_error()


# --- Resúmenes --------------------------------------------------------------

@router.get("/finance/month", response_model=finance.MonthSummary)
def month(
    session: SessionDep, user: CurrentUser,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
):
    """Balance de un mes (por defecto, el actual) con gastos por categoría."""
    today = today_uy()
    try:
        return finance.month_summary(
            _load_data(session, user), year or today.year, month or today.month, _usd_rate(session)
        )
    except finance.RateMissing:
        raise _rate_error()


@router.get("/finance/year", response_model=finance.YearSummary)
def year(
    session: SessionDep, user: CurrentUser,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
):
    """Los 12 meses del año: reales hasta hoy y estimados hacia adelante."""
    today = today_uy()
    try:
        return finance.year_summary(_load_data(session, user), year or today.year, today, _usd_rate(session))
    except finance.RateMissing:
        raise _rate_error()


class Overview(BaseModel):
    """Todo lo que necesita el dashboard, en un solo pedido."""

    today: dt.date
    usd_rate: float | None
    capacity: finance.SavingsCapacity
    current_month: finance.MonthSummary
    year: finance.YearSummary
    food: finance.FoodBudget
    goals: list[finance.GoalProjection]
    money: cashflow.MoneyNow


@router.get("/finance/overview", response_model=Overview)
def overview(session: SessionDep, user: CurrentUser):
    today = today_uy()
    rate = _usd_rate(session)
    data = _load_data(session, user)
    try:
        capacity = finance.savings_capacity(data, today, rate)
        return Overview(
            today=today, usd_rate=rate, capacity=capacity,
            current_month=finance.month_summary(data, today.year, today.month, rate),
            year=finance.year_summary(data, today.year, today, rate),
            food=finance.food_budget(data, capacity, user.food_budget_pct, today, rate),
            goals=finance.project_goals(data.goals, capacity.monthly_savings_cents, today),
            money=cashflow.money_now(data, today, rate),
        )
    except finance.RateMissing:
        raise _rate_error()


@router.get("/finance/food-budget", response_model=finance.FoodBudget)
def food_budget(session: SessionDep, user: CurrentUser):
    """Presupuesto de comida del mes, dividido por semanas."""
    today = today_uy()
    rate = _usd_rate(session)
    data = _load_data(session, user)
    try:
        capacity = finance.savings_capacity(data, today, rate)
        return finance.food_budget(data, capacity, user.food_budget_pct, today, rate)
    except finance.RateMissing:
        raise _rate_error()


@router.get("/finance/goals", response_model=list[finance.GoalProjection])
def goals(session: SessionDep, user: CurrentUser):
    """Progreso y fecha estimada de cada meta según el ahorro disponible."""
    today = today_uy()
    rate = _usd_rate(session)
    data = _load_data(session, user)
    try:
        capacity = finance.savings_capacity(data, today, rate)
    except finance.RateMissing:
        raise _rate_error()
    return finance.project_goals(data.goals, capacity.monthly_savings_cents, today)


@router.get("/finance/goals/{goal_id}/plan", response_model=goal_plan.GoalPlan)
def plan(goal_id: int, session: SessionDep, user: CurrentUser):
    """Plan para llegar a una meta: aporte por mes, hitos y qué ajustar si no alcanza."""
    data = _load_data(session, user)
    goal = next((g for g in data.goals if g.id == goal_id), None)
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meta no encontrada")
    try:
        return goal_plan.goal_plan(data, goal, today_uy(), _usd_rate(session))
    except finance.RateMissing:
        raise _rate_error()


# --- Simulador --------------------------------------------------------------

def _default_installments() -> list[InstallmentOption]:
    return [InstallmentOption(count=n) for n in (3, 6, 12)]


class SimulationRequest(BaseModel):
    """Qué querés comprar: un monto, o un ítem de tu lista de compras deseadas."""

    cost_cents: int | None = Field(default=None, gt=0)
    currency: Currency = Currency.UYU
    wish_item_id: int | None = None
    # Opciones de cuotas a comparar (por defecto: 3, 6 y 12 sin interés)
    installments: list[InstallmentOption] = Field(default_factory=_default_installments, max_length=8)

    @model_validator(mode="after")
    def _monto_o_item(self):
        if (self.cost_cents is None) == (self.wish_item_id is None):
            raise ValueError("Enviá cost_cents o wish_item_id (uno de los dos)")
        return self


@router.post("/finance/simulate", response_model=SimulationResult)
def simulate(body: SimulationRequest, session: SessionDep, user: CurrentUser):
    """
    "Si compro X por $Y": compara pagar al contado, ahorrar primero y cuotas;
    muestra el impacto en el año y en tus metas, y recomienda la de menor daño.
    """
    cost, currency = body.cost_cents, body.currency
    if body.wish_item_id is not None:
        item = session.get(WishItem, body.wish_item_id)
        if item is None or item.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Compra deseada no encontrada")
        cost, currency = item.cost_cents, item.currency

    today = today_uy()
    rate = _usd_rate(session)
    data = _load_data(session, user)
    try:
        price = finance.to_uyu(cost, currency, rate)
        capacity = finance.savings_capacity(data, today, rate)
        year_summary = finance.year_summary(data, today.year, today, rate)
    except finance.RateMissing:
        raise _rate_error()

    return simulate_purchase(
        price_cents=price, monthly_savings_cents=capacity.monthly_savings_cents,
        goals=data.goals, year_balance_cents=year_summary.balance_cents,
        today=today, installments=body.installments,
        aguinaldo=finance.next_aguinaldo(data, today, rate),
    )
