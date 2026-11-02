"""
"Tu plata hoy": cuánta plata tenés AHORA y cuánto podés gastar y ahorrar
hasta fin de mes.

El resto de la app piensa en MESES ("este mes ganás X y gastás Y"). Acá
pensamos en DÍAS: el sueldo entra el 1, el adelanto el 15, el alquiler sale
el 5, Spotify el 12… Cada movimiento con fecha es un "evento".

La idea (todo automático, sin pedirle nada al usuario):
  1) Plata de HOY = lo que te entró desde tu último cobro - lo que gastaste
     desde entonces (cada cobro y cada pago cuenta recién el día que ocurre).
  2) Miramos lo que falta hasta tu próximo cobro: lo que va a entrar (ej: el
     adelanto), cuentas que hay que pagar y lo que solés gastar por día.
  3) Lo que sobra es lo que podés ahorrar (y qué % de tu plata es).
  4) Para metas con fecha: simulamos día por día cuánto podés juntar para
     esa fecha sin quedarte corto después (goal_budget, más abajo).

Funciones PURAS, montos en centésimos de peso uruguayo.
"""

import calendar
import datetime as dt

from pydantic import BaseModel

from ..categories import spending_label
from ..models import ExpenseKind, IncomeFrequency, SubscriptionFrequency
from . import finance

# Días en que se paga el aguinaldo (la ley pide junio y antes del 24 de diciembre)
AGUINALDO_DAY = {6: 30, 12: 18}


class CashEvent(BaseModel):
    date: dt.date
    label: str
    amount_cents: int   # positivo = entra plata, negativo = sale
    kind: str           # "income" | "advance" | "aguinaldo" | "fixed" | "subscription" | "variable"


class MoneyNow(BaseModel):
    received_cents: int               # lo que te entró desde tu último cobro
    spent_cents: int                  # lo que gastaste desde entonces (positivo)
    current_cents: int                # plata de HOY = recibido - gastado
    since: dt.date                    # tu último cobro (o el día 1 si no hay sueldo)
    next_pay: dt.date                 # tu próximo cobro
    period_end: dt.date               # el día antes del próximo cobro
    days_left: int                    # días que quedan hasta period_end, contando hoy
    upcoming: list[CashEvent]         # lo que entra y sale hasta tu próximo cobro
    incoming_cents: int
    bills_cents: int                  # positivo
    usual_spending_cents: int         # lo que solés gastar en lo que queda del mes
    has_spending_history: bool
    free_cents: int                   # plata no comprometida = hoy + cobros - cuentas
    can_save_cents: int
    save_pct: int                     # % de la plata libre que podés ahorrar
    daily_spending_cents: int         # cuánto gastar por día
    short_cents: int                  # > 0 si a tu ritmo no llegás a fin de mes


# --- Fechas -----------------------------------------------------------------

def on_day(year: int, month: int, day: int) -> dt.date:
    """El día `day` del mes, sin pasarse: el "31" de febrero es el 28 (o 29)."""
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def months_between(start: dt.date, end: dt.date):
    """Todos los (año, mes) que toca el período [start, end]."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = finance.add_months(y, m, 1)


# --- Eventos programados (los que tienen día fijo) --------------------------

def income_events(income, start: dt.date, end: dt.date, rate: float | None) -> list[CashEvent]:
    """Los cobros de un ingreso entre start y end (ambos incluidos)."""
    amount = finance.to_uyu(income.amount_cents, income.currency, rate)
    events = []

    def add(date, cents, label, kind="income"):
        if start <= date <= end and date >= income.start_date and (income.end_date is None or date <= income.end_date):
            events.append(CashEvent(date=date, label=label, amount_cents=cents, kind=kind))

    freq = income.frequency
    if freq == IncomeFrequency.one_time:
        return []  # los únicos se tratan como un gasto anotado (ver más abajo)
    for y, m in months_between(start, end):
        if freq == IncomeFrequency.monthly:
            advance = finance.to_uyu(income.advance_cents, income.currency, rate) if income.advance_cents else 0
            if advance:
                add(on_day(y, m, income.advance_day or 15), advance, f"Adelanto · {income.source}", "advance")
            add(on_day(y, m, income.pay_day), amount - advance, income.source)
        elif freq == IncomeFrequency.biweekly:  # quincenal: el 1 y el 15
            add(dt.date(y, m, 1), amount, income.source)
            add(dt.date(y, m, 15), amount, income.source)
        elif freq == IncomeFrequency.annual and m == income.start_date.month:
            add(on_day(y, m, income.start_date.day), amount, income.source)
        if m in AGUINALDO_DAY:
            aguinaldo = finance.aguinaldo_in_month(income, y, m, rate)
            if aguinaldo:
                add(dt.date(y, m, AGUINALDO_DAY[m]), aguinaldo, f"Aguinaldo · {income.source}", "aguinaldo")
    if freq == IncomeFrequency.weekly:  # cada 7 días desde que empezó
        date = income.start_date
        while date <= end:
            add(date, amount, income.source)
            date += dt.timedelta(days=7)
    return events


def scheduled_events(data: finance.FinanceData, start: dt.date, end: dt.date, rate: float | None) -> list[CashEvent]:
    """Cobros, gastos fijos y suscripciones con fecha entre start y end."""
    events = []
    for income in data.incomes:
        events += income_events(income, start, end, rate)

    for e in data.expenses:
        if e.kind != ExpenseKind.fixed:
            continue
        amount = finance.to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate)
        for y, m in months_between(start, end):
            date = on_day(y, m, e.date.day)  # se paga el mismo día del mes en que empezó
            if start <= date <= end and date >= e.date and (e.end_date is None or date <= e.end_date):
                label = e.description or spending_label(e.category, e.subcategory)
                events.append(CashEvent(date=date, label=label, amount_cents=-amount, kind="fixed"))

    for s in data.subscriptions:
        if not s.active:
            continue
        amount = finance.to_uyu(s.amount_cents, s.currency, rate)
        for y, m in months_between(start, end):
            if s.frequency == SubscriptionFrequency.annual and m != s.created_at.month:
                continue
            date = on_day(y, m, s.billing_day)
            if start <= date <= end and date >= s.created_at.date():
                events.append(CashEvent(date=date, label=s.name, amount_cents=-amount, kind="subscription"))
    return sorted(events, key=lambda ev: ev.date)


def logged_events(data: finance.FinanceData, start: dt.date, end: dt.date, rate: float | None) -> list[CashEvent]:
    """Gastos del día a día e ingresos únicos que anotaste, con fecha entre start y end."""
    events = []
    for e in data.expenses:
        if e.kind == ExpenseKind.variable and start <= e.date <= end:
            amount = finance.to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate)
            events.append(CashEvent(date=e.date, label=e.description or spending_label(e.category, e.subcategory),
                                    amount_cents=-amount, kind="variable"))
    for i in data.incomes:
        if i.frequency == IncomeFrequency.one_time and start <= i.start_date <= end:
            amount = finance.to_uyu(i.amount_cents, i.currency, rate)
            events.append(CashEvent(date=i.start_date, label=i.source, amount_cents=amount, kind="income"))
    return events


# --- El ciclo de cobro ------------------------------------------------------
# La plata no se vive "del 1 al 31": se vive de un sueldo al siguiente.
# Si cobrás el 30, lo que gastás el 2 de noviembre sale del sueldo del 30 de
# octubre. Por eso "tu plata hoy" cuenta desde tu ÚLTIMO cobro.

def main_income(data: finance.FinanceData, today: dt.date):
    """El sueldo principal: el ingreso mensual vigente más grande (o None)."""
    monthly = [
        i for i in data.incomes
        if i.frequency == IncomeFrequency.monthly and i.start_date <= today
        and (i.end_date is None or i.end_date >= today)
    ]
    return max(monthly, key=lambda i: i.amount_cents, default=None)


def pay_cycle(data: finance.FinanceData, today: dt.date, rate: float | None) -> tuple[dt.date, dt.date]:
    """
    (día del último cobro, día del próximo cobro) del sueldo principal.
    Sin sueldo mensual: el mes calendario (del 1 al 1 del mes siguiente).
    """
    income = main_income(data, today)
    if income is not None:
        window = dt.timedelta(days=62)
        pays = [ev.date for ev in income_events(income, today - window, today + window, rate) if ev.kind == "income"]
        last = [d for d in pays if d <= today]
        nxt = [d for d in pays if d > today]
        if last and nxt:
            return last[-1], nxt[0]
    first, last_day = finance.month_bounds(today.year, today.month)
    return first, last_day + dt.timedelta(days=1)


def daily_spending(data: finance.FinanceData, today: dt.date, rate: float | None) -> float:
    """Lo que solés gastar por día en el día a día (promedio mensual / días del mes)."""
    return finance.average_variable_expenses(data, today, rate) * 12 / 365


# --- El cálculo principal ---------------------------------------------------

def money_now(data: finance.FinanceData, today: dt.date, rate: float | None) -> MoneyNow:
    since, next_pay = pay_cycle(data, today, rate)
    period_end = next_pay - dt.timedelta(days=1)   # hasta el día antes del próximo sueldo
    days_left = (period_end - today).days + 1

    # 1) Plata de hoy: todo lo que pasó desde tu último cobro hasta hoy
    so_far = scheduled_events(data, since, today, rate) + logged_events(data, since, today, rate)
    received = sum(ev.amount_cents for ev in so_far if ev.amount_cents > 0)
    spent = -sum(ev.amount_cents for ev in so_far if ev.amount_cents < 0)
    current = received - spent

    # 2) Lo que falta hasta tu próximo cobro (desde mañana: lo de hoy ya está en el punto 1)
    upcoming = scheduled_events(data, today + dt.timedelta(days=1), period_end, rate)
    incoming = sum(ev.amount_cents for ev in upcoming if ev.amount_cents > 0)
    bills = -sum(ev.amount_cents for ev in upcoming if ev.amount_cents < 0)

    # Lo que solés gastar en el día a día en los días que quedan
    per_day = daily_spending(data, today, rate)
    usual = round(per_day * days_left)

    # 3) Plata libre = hoy + lo que entra - lo que ya está comprometido
    free = current + incoming - bills
    leftover = free - usual
    if leftover >= 0:
        can_save, short = leftover, 0
        daily = usual // days_left          # tu ritmo de siempre
    else:
        can_save, short = 0, -leftover
        daily = max(free, 0) // days_left   # el máximo para llegar a fin de mes
    save_pct = round(can_save / free * 100) if free > 0 else 0

    return MoneyNow(
        received_cents=received, spent_cents=spent, current_cents=current,
        since=since, next_pay=next_pay, period_end=period_end, days_left=days_left, upcoming=upcoming,
        incoming_cents=incoming, bills_cents=bills, usual_spending_cents=usual,
        has_spending_history=per_day > 0, free_cents=free, can_save_cents=can_save,
        save_pct=save_pct, daily_spending_cents=daily, short_cents=short,
    )


# --- Presupuesto real de una meta con fecha ---------------------------------
# Pregunta: "el 6 de diciembre me voy de viaje: ¿cuánto puedo llevar como
# máximo, sin quedarme sin plata antes de mi próximo sueldo?"
#
# Simulamos tu saldo día por día, desde hoy hasta el día antes del primer
# sueldo DESPUÉS de la fecha: cada cobro (sueldo, adelanto, aguinaldo) suma,
# cada cuenta y suscripción resta en su día, y todos los días se resta lo que
# solés gastar. Lo máximo para la meta es tu saldo en el día MÁS JUSTO desde
# la fecha en adelante (si gastás más que eso, ese día quedarías en rojo),
# menos un colchón por si algo varía.

CUSHION_DAYS = 7          # colchón: una semana de tus gastos habituales
MAX_BUDGET_DAYS = 400     # más lejos que ~1 año, el promedio mensual es más útil


class BudgetStep(BaseModel):
    date: dt.date
    label: str
    amount_cents: int
    kind: str      # como CashEvent.kind, más "goal" (el día de la meta)


class GoalBudget(BaseModel):
    deadline: dt.date
    start_cents: int          # tu plata hoy
    on_deadline_cents: int    # la plata que tendrías ese día (sin gastar en la meta)
    cushion_cents: int        # lo que dejamos de margen
    max_cents: int            # lo máximo que podés poner en la meta ese día
    saved_cents: int          # lo que ya tenés guardado para la meta
    budget_cents: int         # presupuesto real = guardado + máximo
    target_cents: int
    difference_cents: int     # presupuesto - objetivo (+ te sobra / - te falta)
    lowest_date: dt.date      # tu día más justo después de la meta
    covers_until: dt.date     # hasta acá vivís con lo que queda…
    next_pay: dt.date         # …porque este día volvés a cobrar
    short_before: bool        # True = antes de la fecha ya te quedarías sin plata
    steps: list[BudgetStep]   # lo importante que pasa en el medio (para mostrar)


def goal_budget(data: finance.FinanceData, goal, today: dt.date, rate: float | None) -> GoalBudget | None:
    deadline = goal.deadline
    if deadline is None or deadline <= today or (deadline - today).days > MAX_BUDGET_DAYS:
        return None
    _, next_pay = pay_cycle(data, deadline, rate)       # primer sueldo después de la fecha
    horizon = next_pay - dt.timedelta(days=1)

    per_day = daily_spending(data, today, rate)
    start = money_now(data, today, rate).current_cents
    events = scheduled_events(data, today + dt.timedelta(days=1), horizon, rate)
    by_day: dict[dt.date, int] = {}
    for ev in events:
        by_day[ev.date] = by_day.get(ev.date, 0) + ev.amount_cents

    balance = float(start)
    lowest_before = balance
    on_deadline = lowest_after = None
    lowest_date = deadline
    day = today + dt.timedelta(days=1)
    while day <= horizon:
        balance += by_day.get(day, 0) - per_day
        if day < deadline:
            lowest_before = min(lowest_before, balance)
        else:
            if day == deadline:
                on_deadline = balance
            if lowest_after is None or balance < lowest_after:
                lowest_after, lowest_date = balance, day
        day += dt.timedelta(days=1)

    cushion = round(per_day * CUSHION_DAYS)
    max_for_goal = max(round(lowest_after) - cushion, 0)
    budget = goal.saved_cents + max_for_goal

    # Lo importante para mostrar: cobros y cuentas fijas (las suscripciones y
    # los gastos del día a día van resumidos en el texto, si no es una lista eterna)
    steps = [BudgetStep(date=ev.date, label=ev.label, amount_cents=ev.amount_cents, kind=ev.kind)
             for ev in events if ev.kind in ("income", "advance", "aguinaldo", "fixed")]
    steps.append(BudgetStep(date=deadline, label=goal.name, amount_cents=-max_for_goal, kind="goal"))
    steps.sort(key=lambda s: (s.date, s.kind != "goal"))

    return GoalBudget(
        deadline=deadline, start_cents=start, on_deadline_cents=round(on_deadline),
        cushion_cents=cushion, max_cents=max_for_goal, saved_cents=goal.saved_cents,
        budget_cents=budget, target_cents=goal.target_cents,
        difference_cents=budget - goal.target_cents, lowest_date=lowest_date,
        covers_until=horizon, next_pay=next_pay, short_before=lowest_before < 0, steps=steps,
    )
