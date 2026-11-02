"""
"Tu plata hoy": cuánta plata tenés AHORA y cuánto podés gastar y ahorrar
hasta fin de mes.

El resto de la app piensa en MESES ("este mes ganás X y gastás Y"). Acá
pensamos en DÍAS: el sueldo entra el 1, el adelanto el 15, el alquiler sale
el 5, Spotify el 12… Cada movimiento con fecha es un "evento".

La idea:
  1) El usuario dice cuánta plata tiene (cuentas + efectivo) en un momento.
  2) Desde ese momento sumamos los cobros y restamos los gastos -> saldo de HOY.
  3) Miramos lo que falta hasta fin de mes: cobros que van a entrar, cuentas
     que hay que pagar y lo que solés gastar en el día a día.
  4) Lo que sobra es lo que podés ahorrar (y qué % de tu plata es).

Funciones PURAS, montos en centésimos de peso uruguayo.
"""

import calendar
import datetime as dt

from pydantic import BaseModel

from ..categories import spending_label
from ..models import ExpenseKind, IncomeFrequency, SubscriptionFrequency
from ..models.common import URUGUAY_TZ
from . import finance

# Días en que se paga el aguinaldo (la ley pide junio y antes del 24 de diciembre)
AGUINALDO_DAY = {6: 30, 12: 18}


class CashEvent(BaseModel):
    date: dt.date
    label: str
    amount_cents: int   # positivo = entra plata, negativo = sale
    kind: str           # "income" | "advance" | "aguinaldo" | "fixed" | "subscription" | "variable"


class MoneyNow(BaseModel):
    has_balance: bool                 # False = el usuario todavía no cargó su saldo
    balance_cents: int | None         # lo que dijo tener…
    balance_date: dt.date | None      # …y cuándo lo dijo
    since_income_cents: int           # cobros desde entonces
    since_spent_cents: int            # gastos desde entonces (positivo)
    current_cents: int | None         # saldo estimado de HOY
    month_end: dt.date
    days_left: int                    # días que quedan, contando hoy
    upcoming: list[CashEvent]         # lo que entra y sale hasta fin de mes
    incoming_cents: int
    bills_cents: int                  # positivo
    usual_spending_cents: int         # lo que solés gastar en lo que queda del mes
    has_spending_history: bool
    free_cents: int | None            # plata no comprometida = hoy + cobros - cuentas
    can_save_cents: int | None
    save_pct: int | None              # % de la plata libre que podés ahorrar
    daily_spending_cents: int | None  # cuánto gastar por día
    short_cents: int | None           # > 0 si a tu ritmo no llegás a fin de mes


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


def as_utc(value: dt.datetime) -> dt.datetime:
    """Las bases devuelven fechas "sin zona"; nosotros siempre guardamos UTC."""
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def uy_date(value: dt.datetime) -> dt.date:
    """Qué día era en Uruguay en ese momento."""
    return as_utc(value).astimezone(URUGUAY_TZ).date()


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


def logged_since(data: finance.FinanceData, since: dt.datetime, today: dt.date, rate: float | None) -> list[CashEvent]:
    """
    Gastos del día a día e ingresos únicos ANOTADOS después de `since`.
    Dos condiciones, porque el saldo que cargaste ya incluye lo gastado antes:
      - anotado DESPUÉS de cargar el saldo (si actualizás a las 10 y anotás
        un alfajor a las 11, se resta);
      - con fecha del día en que cargaste el saldo o posterior (si hoy anotás
        un gasto de la semana pasada, esa plata ya no estaba en tu saldo).
    """
    since = as_utc(since)
    since_day = uy_date(since)
    events = []
    for e in data.expenses:
        if e.kind == ExpenseKind.variable and as_utc(e.created_at) > since and since_day <= e.date <= today:
            amount = finance.to_uyu(e.amount_cents, e.currency, e.exchange_rate or rate)
            events.append(CashEvent(date=e.date, label=e.description or spending_label(e.category, e.subcategory),
                                    amount_cents=-amount, kind="variable"))
    for i in data.incomes:
        if i.frequency == IncomeFrequency.one_time and as_utc(i.created_at) > since and since_day <= i.start_date <= today:
            amount = finance.to_uyu(i.amount_cents, i.currency, rate)
            events.append(CashEvent(date=i.start_date, label=i.source, amount_cents=amount, kind="income"))
    return events


# --- El cálculo principal ---------------------------------------------------

def money_now(
    data: finance.FinanceData, balance_cents: int | None, balance_at: dt.datetime | None,
    today: dt.date, rate: float | None,
) -> MoneyNow:
    month_end = finance.month_bounds(today.year, today.month)[1]
    days_left = (month_end - today).days + 1

    # Lo que falta hasta fin de mes (desde mañana: lo de hoy ya debería estar en el saldo)
    upcoming = scheduled_events(data, today + dt.timedelta(days=1), month_end, rate)
    incoming = sum(ev.amount_cents for ev in upcoming if ev.amount_cents > 0)
    bills = -sum(ev.amount_cents for ev in upcoming if ev.amount_cents < 0)

    # Lo que solés gastar en el día a día, proporcional a los días que quedan
    avg_variable = finance.average_variable_expenses(data, today, rate)
    usual = round(avg_variable * days_left / month_end.day)

    result = dict(
        month_end=month_end, days_left=days_left, upcoming=upcoming,
        incoming_cents=incoming, bills_cents=bills, usual_spending_cents=usual,
        has_spending_history=avg_variable > 0,
    )
    if balance_cents is None or balance_at is None:
        return MoneyNow(
            has_balance=False, balance_cents=None, balance_date=None, since_income_cents=0,
            since_spent_cents=0, current_cents=None, free_cents=None, can_save_cents=None,
            save_pct=None, daily_spending_cents=None, short_cents=None, **result,
        )

    # 1) Saldo de hoy = lo que dijiste + cobros - gastos desde ese momento
    balance_day = uy_date(balance_at)
    since = scheduled_events(data, balance_day + dt.timedelta(days=1), today, rate)
    since += logged_since(data, balance_at, today, rate)
    since_income = sum(ev.amount_cents for ev in since if ev.amount_cents > 0)
    since_spent = -sum(ev.amount_cents for ev in since if ev.amount_cents < 0)
    current = balance_cents + since_income - since_spent

    # 2) Plata libre = hoy + lo que entra - lo que ya está comprometido
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
        has_balance=True, balance_cents=balance_cents, balance_date=balance_day,
        since_income_cents=since_income, since_spent_cents=since_spent, current_cents=current,
        free_cents=free, can_save_cents=can_save, save_pct=save_pct,
        daily_spending_cents=daily, short_cents=short, **result,
    )
