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
    amount_cents: int   # positivo = entra plata, negativo = sale (escenario prudente)
    kind: str           # "income" | "advance" | "aguinaldo" | "commission" | "fixed" | "subscription" | "variable" | "one_off"
    # Solo para montos inciertos (comisiones): el escenario optimista
    amount_high_cents: int | None = None


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
    incoming_high_cents: int          # igual, si las comisiones vienen altas
    has_commissions: bool             # hay montos inciertos (rango) en lo que viene
    bills_cents: int                  # positivo
    usual_spending_cents: int         # lo que gastarías hasta tu próximo cobro (a ese ritmo)
    has_spending_history: bool
    usual_daily_cents: int            # tu promedio real por día (para el deslizador)
    free_cents: int                   # plata no comprometida = hoy + cobros - cuentas
    can_save_cents: int
    can_save_high_cents: int          # lo que podrías ahorrar si las comisiones vienen altas
    save_pct: int                    # % de la plata libre que podés ahorrar
    daily_spending_cents: int         # cuánto gastar por día
    short_cents: int                  # > 0 si a tu ritmo no llegás a fin de mes
    # Ticket de alimentación (otra tarjeta, solo comida): no está en "tu plata"
    ticket_cents: int
    ticket_used_cents: int            # comida que pagaste con el ticket desde tu último cobro
    ticket_left_cents: int


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
        if income.food_only:
            continue  # el ticket de alimentación va a otra tarjeta: no es plata para el resto
        events += income_events(income, start, end, rate)

    # Comisiones: se cobran con el sueldo (su día de cobro), en un rango mínimo-máximo
    com_income = finance.commission_income(data)
    if com_income is not None:
        for y, m in months_between(start, end):
            date = on_day(y, m, com_income.pay_day)
            if start <= date <= end:
                low = finance.commissions_in_month(data, y, m)
                high = finance.commissions_in_month(data, y, m, high=True)
                if low or high:
                    events.append(CashEvent(date=date, label="Comisiones", amount_cents=low,
                                            amount_high_cents=high, kind="commission"))

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

    # Cosas de una sola vez con fecha: gastos puntuales e ingresos únicos.
    # Si la fecha ya pasó, cuentan para "tu plata hoy"; si es futura, la
    # simulación los descuenta (o suma) ese día.
    for e in data.expenses:
        if e.kind == ExpenseKind.one_off and start <= e.date <= end:
            amount = finance.to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate)
            events.append(CashEvent(date=e.date, label=e.description or spending_label(e.category, e.subcategory),
                                    amount_cents=-amount, kind="one_off"))
    for i in data.incomes:
        if i.frequency == IncomeFrequency.one_time and start <= i.start_date <= end:
            amount = finance.to_uyu(i.amount_cents, i.currency, rate)
            events.append(CashEvent(date=i.start_date, label=i.source, amount_cents=amount, kind="income"))
    return sorted(events, key=lambda ev: ev.date)


def logged_events(data: finance.FinanceData, start: dt.date, end: dt.date, rate: float | None) -> list[CashEvent]:
    """Gastos del día a día que anotaste, con fecha entre start y end."""
    events = []
    for e in data.expenses:
        if e.kind == ExpenseKind.variable and start <= e.date <= end:
            amount = finance.to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate)
            events.append(CashEvent(date=e.date, label=e.description or spending_label(e.category, e.subcategory),
                                    amount_cents=-amount, kind="variable"))
    return events


# --- El ciclo de cobro ------------------------------------------------------
# La plata no se vive "del 1 al 31": se vive de un sueldo al siguiente.
# Si cobrás el 30, lo que gastás el 2 de noviembre sale del sueldo del 30 de
# octubre. Por eso "tu plata hoy" cuenta desde tu ÚLTIMO cobro.

def main_income(data: finance.FinanceData, today: dt.date):
    """El sueldo principal: el ingreso mensual vigente más grande (o None)."""
    monthly = [
        i for i in data.incomes
        if i.frequency == IncomeFrequency.monthly and not i.food_only and i.start_date <= today
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
    """
    Lo que solés gastar por día en el día a día DE TU PLATA (promedio mensual /
    días del mes). La comida que cubre el ticket de alimentación no cuenta.
    """
    monthly = finance.average_variable_expenses(data, today, rate)
    ticket = finance.food_ticket_in_month(data, today.year, today.month, rate)
    if ticket:
        monthly -= min(finance.average_variable_expenses(data, today, rate, only_food=True), ticket)
    return monthly * 12 / 365


# --- El cálculo principal ---------------------------------------------------

def money_now(
    data: finance.FinanceData, today: dt.date, rate: float | None, daily_cents: int | None = None,
) -> MoneyNow:
    """daily_cents: cuánto pensás gastar por día (None = tu promedio real)."""
    since, next_pay = pay_cycle(data, today, rate)
    period_end = next_pay - dt.timedelta(days=1)   # hasta el día antes del próximo sueldo
    days_left = (period_end - today).days + 1

    # 1) Plata de hoy: todo lo que pasó desde tu último cobro hasta hoy
    so_far = scheduled_events(data, since, today, rate) + logged_events(data, since, today, rate)
    received = sum(ev.amount_cents for ev in so_far if ev.amount_cents > 0)
    spent = -sum(ev.amount_cents for ev in so_far if ev.amount_cents < 0)
    # La comida pagada con el ticket de alimentación no salió de tu plata
    ticket = finance.food_ticket_in_month(data, today.year, today.month, rate)
    food = [e for e in data.expenses if finance.is_food(e) and since <= e.date <= today]
    ticket_used = finance.ticket_split(food, ticket, rate) if ticket else 0
    spent -= ticket_used
    current = received - spent

    # 2) Lo que falta hasta tu próximo cobro (desde mañana: lo de hoy ya está en el punto 1)
    upcoming = scheduled_events(data, today + dt.timedelta(days=1), period_end, rate)
    incoming = sum(ev.amount_cents for ev in upcoming if ev.amount_cents > 0)
    incoming_high = sum(ev.amount_high_cents or ev.amount_cents for ev in upcoming if ev.amount_cents >= 0)
    bills = -sum(ev.amount_cents for ev in upcoming if ev.amount_cents < 0)

    # Lo que solés gastar en el día a día (o lo que elegiste) en los días que quedan
    usual_daily = daily_spending(data, today, rate)
    per_day = usual_daily if daily_cents is None else daily_cents
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

    can_save_high = max(current + incoming_high - bills - usual, 0)

    return MoneyNow(
        received_cents=received, spent_cents=spent, current_cents=current,
        since=since, next_pay=next_pay, period_end=period_end, days_left=days_left, upcoming=upcoming,
        incoming_cents=incoming, incoming_high_cents=incoming_high,
        has_commissions=any(ev.kind == "commission" for ev in upcoming + so_far),
        bills_cents=bills, usual_spending_cents=usual,
        has_spending_history=usual_daily > 0, usual_daily_cents=round(usual_daily), free_cents=free,
        can_save_cents=can_save, can_save_high_cents=can_save_high,
        ticket_cents=ticket, ticket_used_cents=ticket_used, ticket_left_cents=max(ticket - ticket_used, 0),
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

CUSHION_DAYS = 7          # colchón por defecto: una semana de tus gastos habituales
MAX_BUDGET_DAYS = 400     # más lejos que ~1 año, el promedio mensual es más útil


class BudgetStep(BaseModel):
    date: dt.date
    label: str
    amount_cents: int
    kind: str      # como CashEvent.kind, más "goal" (el día de la meta)
    amount_high_cents: int | None = None   # comisiones: el máximo del rango


class BalancePoint(BaseModel):
    date: dt.date
    balance_cents: int


class GoalBudget(BaseModel):
    deadline: dt.date
    start_cents: int          # tu plata hoy
    on_deadline_cents: int    # la plata que tendrías ese día (sin gastar en la meta)
    usual_daily_cents: int    # lo que solés gastar por día (tu promedio real)
    daily_cents: int          # el gasto por día que se usó (el tuyo o el que elegiste)
    cushion_days: int
    cushion_cents: int        # lo que dejamos de margen
    max_cents: int            # lo máximo que podés poner en la meta ese día
    saved_cents: int          # lo que ya tenés guardado para la meta
    budget_cents: int         # presupuesto real = guardado + máximo
    target_cents: int
    difference_cents: int     # presupuesto - objetivo (+ te sobra / - te falta)
    # Al revés: si la meta cuesta lo que dijiste, ¿cuánto podés gastar como
    # máximo por día (y por semana) hasta tu próximo cobro, y llegar igual?
    max_daily_cents: int
    max_weekly_cents: int
    goal_spend_cents: int     # lo que sale de tu plata ese día en el gráfico
    lowest_date: dt.date      # tu día más justo después de la meta
    lowest_cents: int         # cuánto te queda ese día (ya pagada la meta)
    covers_until: dt.date     # hasta acá vivís con lo que queda…
    next_pay: dt.date         # …porque este día volvés a cobrar
    short_before: bool        # True = antes de la fecha ya te quedarías sin plata
    steps: list[BudgetStep]   # lo importante que pasa en el medio (para mostrar)
    series: list[BalancePoint]  # tu saldo día por día (para el gráfico)
    # Sueldos con comisiones: lo de arriba es el escenario PRUDENTE (lo mínimo
    # de cada rango). Esto es si las comisiones vienen en el máximo.
    has_commissions: bool
    budget_high_cents: int
    max_daily_high_cents: int
    max_weekly_high_cents: int


def goal_budget(
    data: finance.FinanceData, goal, today: dt.date, rate: float | None,
    daily_cents: int | None = None, cushion_days: int | None = None,
) -> GoalBudget | None:
    """
    daily_cents: cuánto pensás gastar por día (None = tu promedio real).
    cushion_days: cuántos días de gastos dejar de colchón (None = 7).
    """
    deadline = goal.deadline
    if deadline is None or deadline <= today or (deadline - today).days > MAX_BUDGET_DAYS:
        return None
    _, next_pay = pay_cycle(data, deadline, rate)       # primer sueldo después de la fecha
    horizon = next_pay - dt.timedelta(days=1)

    usual = daily_spending(data, today, rate)
    per_day = usual if daily_cents is None else daily_cents
    cushion_days = CUSHION_DAYS if cushion_days is None else cushion_days
    cushion = round(per_day * cushion_days)
    start = money_now(data, today, rate).current_cents
    events = scheduled_events(data, today + dt.timedelta(days=1), horizon, rate)

    def walk(high: bool):
        """
        Recorre los días UNA vez y guarda, para cada día, la plata que entró/salió
        por eventos (acumulada) y cuántos días de gasto pasaron.
        high=True: las comisiones en su máximo (escenario optimista).
        """
        by_day: dict[dt.date, int] = {}
        for ev in events:
            amount = ev.amount_high_cents if high and ev.amount_high_cents is not None else ev.amount_cents
            by_day[ev.date] = by_day.get(ev.date, 0) + amount
        days, acc, day, k = [], 0, today + dt.timedelta(days=1), 0
        while day <= horizon:
            acc += by_day.get(day, 0)
            k += 1
            days.append((day, acc, k))       # (fecha, eventos acumulados, días de gasto)
            day += dt.timedelta(days=1)
        return days

    def balance(acc, k):
        return start + acc - per_day * k

    need = max(goal.target_cents - goal.saved_cents, 0)
    usual_cushion = round(usual * cushion_days)

    def max_for_goal_and_daily(days):
        """(lo máximo para la meta, día más justo, saldo ese día, tope de gasto por día)"""
        lowest_after, lowest_date = min((balance(a, k), d) for d, a, k in days if d >= deadline)
        # Tope por día: el gasto diario más alto con el que igual pagás la meta y
        # nunca bajás del colchón. Para cada día t: start + eventos(t) - meta - s·k ≥ colchón
        # => s ≤ (start + eventos(t) - meta - colchón) / k. El tope es el menor de todos.
        max_daily = min((start + a - (need if d >= deadline else 0) - usual_cushion) / k for d, a, k in days)
        return max(round(lowest_after) - cushion, 0), lowest_date, lowest_after, max(int(max_daily), 0)

    days = walk(high=False)                    # escenario prudente: el que manda
    max_for_goal, lowest_date, lowest_after, max_daily = max_for_goal_and_daily(days)
    lowest_before = min([balance(a, k) for d, a, k in days if d < deadline] + [start])
    on_deadline = next(balance(a, k) for d, a, k in days if d == deadline)
    budget = goal.saved_cents + max_for_goal

    has_commissions = any(ev.kind == "commission" for ev in events)
    high_max, _, _, high_daily = max_for_goal_and_daily(walk(high=True)) if has_commissions \
        else (max_for_goal, None, None, max_daily)

    # Gráfico: tu saldo si gastás lo que pensás por día y ponés en la meta
    # lo que cuesta (o lo máximo posible, si no alcanza)
    spend = min(need, max_for_goal) if need else 0
    series = [BalancePoint(date=today, balance_cents=start)] + [
        BalancePoint(date=d, balance_cents=round(balance(a, k) - (spend if d >= deadline else 0)))
        for d, a, k in days
    ]

    # Lo importante para mostrar: cobros, cuentas fijas y puntuales (las
    # suscripciones y los gastos del día a día van resumidos en el texto)
    steps = [BudgetStep(date=ev.date, label=ev.label, amount_cents=ev.amount_cents, kind=ev.kind,
                        amount_high_cents=ev.amount_high_cents)
             for ev in events if ev.kind in ("income", "advance", "aguinaldo", "commission", "fixed", "one_off")]
    steps.append(BudgetStep(date=deadline, label=goal.name, amount_cents=-max_for_goal, kind="goal"))
    steps.sort(key=lambda s: (s.date, s.kind != "goal"))

    return GoalBudget(
        deadline=deadline, start_cents=start, on_deadline_cents=round(on_deadline),
        usual_daily_cents=round(usual), daily_cents=round(per_day), cushion_days=cushion_days,
        cushion_cents=cushion, max_cents=max_for_goal, saved_cents=goal.saved_cents,
        budget_cents=budget, target_cents=goal.target_cents,
        difference_cents=budget - goal.target_cents,
        max_daily_cents=max_daily, max_weekly_cents=max_daily * 7, goal_spend_cents=spend,
        lowest_date=lowest_date, lowest_cents=round(lowest_after) - spend,
        covers_until=horizon, next_pay=next_pay, short_before=lowest_before < 0,
        steps=steps, series=series, has_commissions=has_commissions,
        budget_high_cents=goal.saved_cents + high_max, max_daily_high_cents=high_daily,
        max_weekly_high_cents=high_daily * 7,
    )
