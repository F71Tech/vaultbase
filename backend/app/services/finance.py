"""
El "cerebro" financiero de VaultBase.

Todas las funciones de este archivo son PURAS: reciben datos y devuelven
resultados, sin tocar la base de datos ni internet. Eso las hace fáciles de
entender y de testear: mismo dato de entrada -> mismo resultado, siempre.

Todos los montos son enteros en centésimos de PESO URUGUAYO (UYU).
"""

import calendar
import datetime as dt
import math
from dataclasses import dataclass, field

from pydantic import BaseModel

from ..models import (
    Commission, Currency, Expense, ExpenseKind, Goal, Income, IncomeFrequency, PayRecord, Subscription,
    SubscriptionFrequency,
)

# Cuántas veces "entra" cada frecuencia en un mes.
# Nota: "quincenal" en Uruguay = 2 cobros por mes (el 1 y el 15).
MONTHLY_FACTOR = {
    IncomeFrequency.weekly: 52 / 12,
    IncomeFrequency.biweekly: 2,
    IncomeFrequency.monthly: 1,
    IncomeFrequency.annual: 1 / 12,
}
FOOD_CATEGORY = "food"
SUBSCRIPTIONS_KEY = "subscriptions"  # pseudo-categoría para el gráfico
VARIABLE_ESTIMATE_KEY = "variable_estimate"  # gastos variables proyectados


class RateMissing(Exception):
    """Hay montos en dólares pero no tenemos cotización para convertirlos."""


# --- Utilidades de fechas y monedas -----------------------------------------

def month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    """Primer y último día del mes."""
    last_day = calendar.monthrange(year, month)[1]
    return dt.date(year, month, 1), dt.date(year, month, last_day)


def add_months(year: int, month: int, n: int) -> tuple[int, int]:
    """Suma (o resta) n meses a un año/mes. Ej: (2026, 11) + 3 = (2027, 2)."""
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def add_months_to_date(date: dt.date, n: int) -> dt.date:
    year, month = add_months(date.year, date.month, n)
    day = min(date.day, calendar.monthrange(year, month)[1])  # 31/1 + 1 mes = 28/2
    return dt.date(year, month, day)


def to_uyu(amount_cents: int, currency: Currency, rate: float | None) -> int:
    """Convierte un monto a pesos. Si es USD, multiplica por la cotización."""
    if currency == Currency.UYU:
        return amount_cents
    if rate is None:
        raise RateMissing("Falta la cotización del dólar")
    return round(amount_cents * rate)


def _category(expense: Expense) -> str:
    """La categoría como texto (acepta tanto el Enum como un string)."""
    return getattr(expense.category, "value", expense.category)


def _active_in(start: dt.date, end: dt.date | None, first: dt.date, last: dt.date) -> bool:
    """¿Un período [start, end] se superpone con el mes [first, last]?"""
    return start <= last and (end is None or end >= first)


# --- Montos de cada elemento en un mes dado ---------------------------------

def income_in_month(income: Income, year: int, month: int, rate: float | None) -> int:
    if income.previous_money:
        return 0  # ya la tenías: no te entró este mes
    first, last = month_bounds(year, month)
    amount = to_uyu(income.amount_cents, income.currency, rate)
    if income.frequency == IncomeFrequency.one_time:
        return amount if first <= income.start_date <= last else 0
    if not _active_in(income.start_date, income.end_date, first, last):
        return 0
    return round(amount * MONTHLY_FACTOR[income.frequency])


AGUINALDO_MONTHS = (6, 12)  # se cobra en junio y en diciembre


def aguinaldo_in_month(income: Income, year: int, month: int, rate: float | None) -> int:
    """
    Medio aguinaldo que cobra este sueldo en `month` (solo junio o diciembre).
    Corresponde a lo trabajado en el semestre anterior (dic-may o jun-nov):
    si el sueldo empezó o terminó a mitad del semestre, se cobra proporcional.
    """
    if month not in AGUINALDO_MONTHS or not income.aguinaldo_cents:
        return 0
    months_worked = 0
    for back in range(1, 7):  # los 6 meses anteriores
        y, m = add_months(year, month, -back)
        first, last = month_bounds(y, m)
        if _active_in(income.start_date, income.end_date, first, last):
            months_worked += 1
    amount = to_uyu(income.aguinaldo_cents, income.currency, rate)
    return round(amount * months_worked / 6)


def expense_in_month(expense: Expense, year: int, month: int, rate: float | None) -> int:
    first, last = month_bounds(year, month)
    # Si el gasto tiene su cotización "congelada", usamos esa; si no, la actual
    amount = to_uyu(expense.amount_cents, expense.currency, expense.exchange_rate or rate)
    if expense.kind == ExpenseKind.fixed:
        return amount if _active_in(expense.date, expense.end_date, first, last) else 0
    return amount if first <= expense.date <= last else 0


def subscription_in_month(sub: Subscription, year: int, month: int, rate: float | None) -> int:
    if not sub.active:
        return 0
    first, last = month_bounds(year, month)
    if sub.created_at.date() > last:  # todavía no existía en ese mes
        return 0
    amount = to_uyu(sub.amount_cents, sub.currency, rate)
    # Una suscripción anual se reparte en 12 meses para el presupuesto mensual
    return amount if sub.frequency == SubscriptionFrequency.monthly else round(amount / 12)


# --- Resumen de un mes ------------------------------------------------------

@dataclass
class FinanceData:
    """Todo lo que el usuario cargó, junto, para pasárselo a los cálculos."""

    incomes: list[Income] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)
    subscriptions: list[Subscription] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    commissions: list[Commission] = field(default_factory=list)
    pay_records: list[PayRecord] = field(default_factory=list)
    # Día en que el usuario empezó a usar la app (creó la cuenta). "Tu plata hoy"
    # acumula desde el cobro anterior a ese día: lo que sobra de un mes pasa al otro.
    joined: dt.date | None = None


# --- Cobros reales ----------------------------------------------------------
# Un sueldo mensual se cobra en dos partes: el adelanto (si hay) y "el cobro"
# del día de cobro. Para cada parte:
#   1) si anotaste el cobro REAL de ese mes, manda ese (con su fecha real);
#   2) si no, y ya tenés algún cobro real anterior, se estima con el último
#      (salvo sueldos con comisiones: esos usan el modelo de rangos);
#   3) si no, lo que dice el ingreso (monto - adelanto).

def on_day(year: int, month: int, day: int) -> dt.date:
    """El día `day` del mes, sin pasarse: el "31" de febrero es el 28 (o 29)."""
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def pay_record_in_month(data: "FinanceData", income: Income, year: int, month: int, kind: str) -> PayRecord | None:
    """El cobro real anotado para ese ingreso, ese mes y esa parte ("pay" o "advance")."""
    return next((r for r in data.pay_records
                 if r.income_id == income.id and getattr(r.kind, "value", r.kind) == kind
                 and (r.date.year, r.date.month) == (year, month)), None)


def last_pay_record(data: "FinanceData", income: Income, before: dt.date, kind: str = "pay") -> PayRecord | None:
    """El último cobro real anotado ANTES de una fecha (para estimar los que vienen)."""
    records = [r for r in data.pay_records
               if r.income_id == income.id and getattr(r.kind, "value", r.kind) == kind and r.date < before]
    return max(records, key=lambda r: r.date, default=None)


@dataclass
class PayParts:
    advance_date: dt.date | None
    advance_cents: int
    pay_date: dt.date
    pay_cents: int
    status: str   # "real" (anotaste el cobro) | "last" (estimado con el último real) | "planned" (lo del ingreso)


def pay_parts(data: "FinanceData", income: Income, year: int, month: int, rate: float | None) -> PayParts:
    """Cuánto entra (y qué día) por un sueldo mensual en ese mes."""
    amount = to_uyu(income.amount_cents, income.currency, rate)
    advance = to_uyu(income.advance_cents, income.currency, rate) if income.advance_cents else 0
    advance_date = on_day(year, month, income.advance_day or 15) if advance else None
    rec = pay_record_in_month(data, income, year, month, "advance")
    if rec is not None:
        advance_date, advance = rec.date, rec.amount_cents

    pay_date = on_day(year, month, income.pay_day)
    rec = pay_record_in_month(data, income, year, month, "pay")
    if rec is not None:
        return PayParts(advance_date, advance, rec.date, rec.amount_cents, "real")
    planned = amount - (to_uyu(income.advance_cents, income.currency, rate) if income.advance_cents else 0)
    last = last_pay_record(data, income, pay_date) if income.commission_floor_cents is None else None
    if last is not None:
        return PayParts(advance_date, advance, pay_date, last.amount_cents, "last")
    return PayParts(advance_date, advance, pay_date, planned, "planned")


def income_total_in_month(data: "FinanceData", income: Income, year: int, month: int, rate: float | None) -> int:
    """Como income_in_month, pero un sueldo mensual usa sus cobros reales (o el último real)."""
    base = income_in_month(income, year, month, rate)
    if income.frequency != IncomeFrequency.monthly or base == 0:
        return base
    parts = pay_parts(data, income, year, month, rate)
    return parts.advance_cents + parts.pay_cents


# --- Comisiones semanales ---------------------------------------------------
# Las semanas van de lunes a domingo y se cobran con el sueldo del mes en que
# TERMINAN (su domingo). Cada semana se cobra lo que sea más alto entre la
# comisión y el bono mínimo semanal del sueldo.

def commission_income(data: "FinanceData") -> Income | None:
    """El sueldo que tiene comisiones (el que tiene bono mínimo semanal cargado)."""
    return next((i for i in data.incomes if i.commission_floor_cents is not None), None)


def sundays_in_month(year: int, month: int) -> list[dt.date]:
    first, last = month_bounds(year, month)
    day = first + dt.timedelta(days=(6 - first.weekday()) % 7)  # primer domingo
    result = []
    while day <= last:
        result.append(day)
        day += dt.timedelta(days=7)
    return result


def commissions_in_month(data: "FinanceData", year: int, month: int, high: bool = False) -> int:
    """
    Comisiones que se cobran con el sueldo de ese mes.
    high=False: escenario prudente (el mínimo de cada rango).
    high=True: escenario optimista (el máximo). Si ya cargaste el monto real, se usa ese.
    Semanas sin datos: el bono mínimo (lo único seguro).
    """
    income = commission_income(data)
    if income is None and not data.commissions:
        return 0
    # Si ya anotaste el cobro real de ese mes, las comisiones vienen adentro
    if income is not None and pay_record_in_month(data, income, year, month, "pay") is not None:
        return 0
    floor = (income.commission_floor_cents or 0) if income else 0
    by_week = {c.week_start: c for c in data.commissions}
    total = 0
    for sunday in sundays_in_month(year, month):
        week = by_week.get(sunday - dt.timedelta(days=6))
        if week is None:
            # sin anotar: solo cuenta el bono, y solo si el sueldo estaba vigente esa semana
            if income and income.start_date <= sunday and (income.end_date is None or income.end_date >= sunday):
                total += floor
            continue
        value = week.actual_cents if week.actual_cents is not None else (week.max_cents if high else week.min_cents)
        total += max(value, floor)
    return total


class MonthSummary(BaseModel):
    year: int
    month: int
    income_cents: int               # incluye el aguinaldo en junio y diciembre
    aguinaldo_cents: int            # la parte de income_cents que es aguinaldo
    fixed_expenses_cents: int       # gastos fijos (sin suscripciones)
    subscriptions_cents: int
    variable_expenses_cents: int
    total_expenses_cents: int
    balance_cents: int              # ingresos - gastos
    by_category: dict[str, int]     # para el gráfico de torta
    projected: bool                 # True = mes futuro (estimado)


def month_summary(
    data: FinanceData, year: int, month: int, rate: float | None,
    projected_variable_cents: int | None = None,
) -> MonthSummary:
    """
    Resumen de un mes. Si `projected_variable_cents` viene con valor, el mes se
    trata como FUTURO: los gastos variables reales se reemplazan por esa estimación.
    """
    aguinaldo = sum(aguinaldo_in_month(i, year, month, rate) for i in data.incomes)
    income = (sum(income_total_in_month(data, i, year, month, rate) for i in data.incomes) + aguinaldo
              + commissions_in_month(data, year, month))  # comisiones: escenario prudente
    subs = sum(subscription_in_month(s, year, month, rate) for s in data.subscriptions)

    fixed = 0
    variable = 0
    one_off = 0
    by_category: dict[str, int] = {}
    for expense in data.expenses:
        amount = expense_in_month(expense, year, month, rate)
        if amount == 0:
            continue
        if expense.kind == ExpenseKind.fixed:
            fixed += amount
        elif expense.kind == ExpenseKind.one_off:
            one_off += amount  # puntual: cuenta siempre, también si ya está anotado a futuro
        elif projected_variable_cents is None:
            variable += amount
        else:
            continue  # mes futuro: los del día a día se estiman aparte
        key = _category(expense)
        by_category[key] = by_category.get(key, 0) + amount

    projected = projected_variable_cents is not None
    if projected:
        variable = projected_variable_cents
        if variable:
            by_category[VARIABLE_ESTIMATE_KEY] = variable
    variable += one_off  # en el resumen, los puntuales van junto a los variables
    if subs:
        by_category[SUBSCRIPTIONS_KEY] = subs

    total = fixed + subs + variable
    return MonthSummary(
        year=year, month=month, income_cents=income, aguinaldo_cents=aguinaldo, fixed_expenses_cents=fixed,
        subscriptions_cents=subs, variable_expenses_cents=variable,
        total_expenses_cents=total, balance_cents=income - total,
        by_category=by_category, projected=projected,
    )


# --- Capacidad de ahorro ----------------------------------------------------

def average_variable_expenses(
    data: FinanceData, today: dt.date, rate: float | None, months: int = 3, only_food: bool = False,
) -> int:
    """
    Promedio de gastos variables de los últimos `months` meses COMPLETOS.

    Solo cuenta meses desde que el usuario empezó a cargar gastos (si empezó
    este mes, los meses anteriores en 0 bajarían el promedio sin razón).
    Si no hay ningún mes completo con datos, usa lo gastado en el mes actual.
    Los gastos PUNTUALES no entran: no son "lo que solés gastar".
    only_food=True: solo la comida (para saber cuánto cubre el ticket).
    """
    all_variables = [e for e in data.expenses if e.kind == ExpenseKind.variable]
    if not all_variables:
        return 0
    first_date = min(e.date for e in all_variables)
    variables = [e for e in all_variables if not only_food or _category(e) == FOOD_CATEGORY]
    totals = []
    for back in range(1, months + 1):
        year, month = add_months(today.year, today.month, -back)
        if month_bounds(year, month)[1] < first_date:
            break  # antes de que empezara a usar la app
        totals.append(sum(expense_in_month(e, year, month, rate) for e in variables))
    if totals:
        return round(sum(totals) / len(totals))
    return sum(expense_in_month(e, today.year, today.month, rate) for e in variables)


class UnusualCheck(BaseModel):
    unusual: bool
    typical_cents: int | None   # lo que solés gastar en esa categoría (la mediana)


UNUSUAL_FACTOR = 3            # "inusual" = más del triple de lo habitual…
UNUSUAL_MIN_CENTS = 100_000   # …y al menos $ 1.000 (un alfajor caro no es "puntual")


def unusual_expense(data: FinanceData, expense: Expense, rate: float | None) -> UnusualCheck:
    """
    ¿Este gasto del día a día parece algo puntual? Lo comparamos con la
    MEDIANA de tus gastos de la misma categoría en los últimos 4 meses (la
    mediana = el del medio si los ordenás; a diferencia del promedio, un gasto
    gigante no la mueve). Si es más del triple, preguntamos.
    """
    if expense.kind != ExpenseKind.variable:
        return UnusualCheck(unusual=False, typical_cents=None)
    amount = to_uyu(expense.amount_cents, expense.currency, expense.exchange_rate or rate)
    since = expense.date - dt.timedelta(days=120)
    peers = sorted(
        to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate) for e in data.expenses
        if e.id != expense.id and e.kind == ExpenseKind.variable
        and _category(e) == _category(expense) and since <= e.date <= expense.date
    )
    if len(peers) >= 3:
        typical = peers[len(peers) // 2]
        return UnusualCheck(unusual=amount >= UNUSUAL_MIN_CENTS and amount > typical * UNUSUAL_FACTOR,
                            typical_cents=typical)
    # Pocos datos de esa categoría: lo comparamos con todo tu gasto mensual del día a día
    monthly = average_variable_expenses(data, expense.date, rate)
    return UnusualCheck(unusual=amount >= max(UNUSUAL_MIN_CENTS * 2, monthly // 4) if monthly else False,
                        typical_cents=None)


# --- Ticket de alimentación -------------------------------------------------
# Es otra tarjeta que solo sirve para comida. Regla: la comida se paga PRIMERO
# con el ticket (hasta que se acaba), salvo que el usuario diga lo contrario en
# el gasto (paid_with_ticket True/False).

def food_ticket_in_month(data: FinanceData, year: int, month: int, rate: float | None) -> int:
    """Cuánto te cargan en el ticket de alimentación ese mes."""
    return sum(income_in_month(i, year, month, rate) for i in data.incomes if i.food_only)


def is_food(expense: Expense) -> bool:
    return _category(expense) == FOOD_CATEGORY and expense.kind != ExpenseKind.fixed


def ticket_split(food_expenses: list[Expense], ticket_cents: int, rate: float | None) -> int:
    """
    De estos gastos de comida, ¿cuánto se pagó con el ticket?
      - marcados "con ticket": todo con ticket;
      - marcados "con mi plata": nada;
      - sin marcar: con el ticket mientras quede saldo (en orden de fecha).
    """
    amount = lambda e: to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate)  # noqa: E731
    used = sum(amount(e) for e in food_expenses if e.paid_with_ticket is True)
    for e in sorted((e for e in food_expenses if e.paid_with_ticket is None), key=lambda e: e.date):
        used += min(amount(e), max(ticket_cents - used, 0))
    return used


class SavingsCapacity(BaseModel):
    recurring_income_cents: int       # ingresos que se repiten (sin los únicos ni el ticket)
    fixed_costs_cents: int            # gastos fijos + suscripciones
    disposable_income_cents: int      # ingreso disponible = ingresos - fijos
    avg_variable_expenses_cents: int  # promedio de gastos variables que salen de TU plata
    food_ticket_cents: int            # ticket de alimentación por mes (solo comida)
    monthly_savings_cents: int        # ahorro mensual disponible


def next_aguinaldo(data: FinanceData, today: dt.date, rate: float | None) -> tuple[int, int] | None:
    """
    El próximo aguinaldo: (en cuántos meses, monto líquido en pesos).
    0 meses = se cobra este mes. None = no hay sueldos con aguinaldo.
    """
    for offset in range(0, 12):
        y, m = add_months(today.year, today.month, offset)
        amount = sum(aguinaldo_in_month(i, y, m, rate) for i in data.incomes)
        if amount:
            return offset, amount
    return None


def savings_capacity(data: FinanceData, today: dt.date, rate: float | None) -> SavingsCapacity:
    """
    Cuánto puede ahorrar el usuario por mes, en promedio.
    (El aguinaldo NO entra acá: es un extra de junio y diciembre, no de todos los meses.)
    """
    y, m = today.year, today.month
    recurring = sum(
        income_total_in_month(data, i, y, m, rate) for i in data.incomes
        if i.frequency != IncomeFrequency.one_time and not i.food_only
    ) + commissions_in_month(data, y, m)  # comisiones de este mes, escenario prudente
    fixed = sum(
        expense_in_month(e, y, m, rate) for e in data.expenses if e.kind == ExpenseKind.fixed
    ) + sum(subscription_in_month(s, y, m, rate) for s in data.subscriptions)
    # El ticket no es plata libre: no suma al ingreso, pero cubre comida (hasta su monto),
    # así que esa parte de tus gastos no sale de tu plata. Si comés menos que el ticket,
    # lo que sobra queda en la tarjeta: no se puede ahorrar para una meta.
    ticket = food_ticket_in_month(data, y, m, rate)
    covered = min(average_variable_expenses(data, today, rate, only_food=True), ticket)
    avg_variable = average_variable_expenses(data, today, rate) - covered
    disposable = recurring - fixed
    return SavingsCapacity(
        recurring_income_cents=recurring, fixed_costs_cents=fixed,
        disposable_income_cents=disposable, avg_variable_expenses_cents=avg_variable,
        food_ticket_cents=ticket, monthly_savings_cents=disposable - avg_variable,
    )


# --- Año completo -----------------------------------------------------------

class YearSummary(BaseModel):
    year: int
    months: list[MonthSummary]
    income_cents: int
    expenses_cents: int
    balance_cents: int


def year_summary(data: FinanceData, year: int, today: dt.date, rate: float | None) -> YearSummary:
    """Los 12 meses del año: reales hasta el mes actual, estimados después."""
    estimate = average_variable_expenses(data, today, rate)
    months = []
    for month in range(1, 13):
        is_future = (year, month) > (today.year, today.month)
        months.append(month_summary(data, year, month, rate, estimate if is_future else None))
    income = sum(m.income_cents for m in months)
    expenses = sum(m.total_expenses_cents for m in months)
    return YearSummary(
        year=year, months=months, income_cents=income,
        expenses_cents=expenses, balance_cents=income - expenses,
    )


# --- Presupuesto de comida --------------------------------------------------

class FoodWeek(BaseModel):
    start: dt.date
    end: dt.date
    budget_cents: int
    spent_cents: int
    is_current: bool


class FoodBudget(BaseModel):
    percentage: int
    monthly_budget_cents: int
    spent_cents: int
    remaining_cents: int
    by_subcategory: dict[str, int]
    weeks: list[FoodWeek]
    ticket_cents: int        # ticket de alimentación del mes (se suma al presupuesto)
    ticket_used_cents: int   # lo que ya gastaste con el ticket este mes
    ticket_left_cents: int   # lo que te queda en la tarjeta


def food_budget(
    data: FinanceData, capacity: SavingsCapacity, percentage: int,
    today: dt.date, rate: float | None,
) -> FoodBudget:
    """
    Presupuesto de comida del mes = % del ingreso disponible.
    Se divide en semanas de 7 días desde el día 1 (la última puede ser más corta),
    y cada semana recibe una parte proporcional a sus días.
    """
    first, last = month_bounds(today.year, today.month)
    days_in_month = last.day
    # Tu parte (el % de tu plata disponible) + lo que te cargan en el ticket
    ticket = capacity.food_ticket_cents
    monthly = max(capacity.disposable_income_cents, 0) * percentage // 100 + ticket

    food = [
        e for e in data.expenses
        if _category(e) == FOOD_CATEGORY and e.kind != ExpenseKind.fixed  # día a día + puntuales
        and first <= e.date <= last
    ]
    by_sub: dict[str, int] = {}
    for e in food:
        key = e.subcategory or "general"
        by_sub[key] = by_sub.get(key, 0) + to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate)

    weeks = []
    start = first
    while start <= last:
        end = min(start + dt.timedelta(days=6), last)
        days = (end - start).days + 1
        spent = sum(
            to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate)
            for e in food if start <= e.date <= end
        )
        weeks.append(FoodWeek(
            start=start, end=end, budget_cents=monthly * days // days_in_month,
            spent_cents=spent, is_current=start <= today <= end,
        ))
        start = end + dt.timedelta(days=1)

    spent_total = sum(by_sub.values())
    ticket_used = ticket_split(food, ticket, rate) if ticket else 0
    return FoodBudget(
        percentage=percentage, monthly_budget_cents=monthly, spent_cents=spent_total,
        remaining_cents=monthly - spent_total, by_subcategory=by_sub, weeks=weeks,
        ticket_cents=ticket, ticket_used_cents=ticket_used, ticket_left_cents=max(ticket - ticket_used, 0),
    )


# --- Metas ------------------------------------------------------------------

class GoalProjection(BaseModel):
    goal_id: int
    name: str
    target_cents: int
    saved_cents: int
    remaining_cents: int
    progress_pct: float
    monthly_contribution_cents: int   # cuánto se le asigna por mes
    contribution_is_manual: bool
    months_needed: int | None         # None = con el ahorro actual no se alcanza
    estimated_date: dt.date | None
    deadline: dt.date | None
    # "completed" | "on_track" | "behind" | "no_deadline" | "unreachable"
    status: str
    required_monthly_for_deadline_cents: int | None


def allocate_contributions(goals: list[Goal], monthly_savings_cents: int) -> dict[int, int]:
    """
    Reparte el ahorro mensual entre las metas sin completar:
      1) las que tienen aporte manual reciben ese aporte;
      2) lo que sobra se divide en partes iguales entre las demás.
    """
    pending = [g for g in goals if g.saved_cents < g.target_cents]
    allocation = {}
    manual_total = 0
    for g in pending:
        if g.monthly_contribution_cents is not None:
            allocation[g.id] = g.monthly_contribution_cents
            manual_total += g.monthly_contribution_cents
    automatic = [g for g in pending if g.monthly_contribution_cents is None]
    leftover = max(monthly_savings_cents - manual_total, 0)
    for g in automatic:
        allocation[g.id] = leftover // len(automatic)
    return allocation


def months_to_reach(remaining_cents: int, monthly_cents: int) -> int | None:
    if remaining_cents <= 0:
        return 0
    if monthly_cents <= 0:
        return None
    return math.ceil(remaining_cents / monthly_cents)


def project_goals(goals: list[Goal], monthly_savings_cents: int, today: dt.date) -> list[GoalProjection]:
    allocation = allocate_contributions(goals, monthly_savings_cents)
    result = []
    for g in goals:
        remaining = max(g.target_cents - g.saved_cents, 0)
        contribution = allocation.get(g.id, 0)
        months = months_to_reach(remaining, contribution)
        estimated = add_months_to_date(today, months) if months is not None else None

        required = None
        if g.deadline and remaining > 0:
            # meses que quedan hasta la fecha límite (al menos 1)
            months_left = max((g.deadline.year - today.year) * 12 + g.deadline.month - today.month, 1)
            required = math.ceil(remaining / months_left)

        if remaining == 0:
            status = "completed"
        elif months is None:
            status = "unreachable"
        elif g.deadline is None:
            status = "no_deadline"
        else:
            status = "on_track" if estimated <= g.deadline else "behind"

        result.append(GoalProjection(
            goal_id=g.id, name=g.name, target_cents=g.target_cents, saved_cents=g.saved_cents,
            remaining_cents=remaining,
            progress_pct=round(min(g.saved_cents / g.target_cents, 1) * 100, 1),
            monthly_contribution_cents=contribution,
            contribution_is_manual=g.monthly_contribution_cents is not None,
            months_needed=months, estimated_date=estimated, deadline=g.deadline,
            status=status, required_monthly_for_deadline_cents=required,
        ))
    return result
