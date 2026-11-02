"""
El "plan" de una meta: no solo CUÁNDO llegás, sino QUÉ hacer para llegar.

Arma, para una meta:
  1) cuánto apartar por mes (y su equivalente por semana y por día);
  2) los hitos mes a mes ("en marzo deberías tener $X");
  3) si con lo que ahorrás hoy no alcanza, ideas concretas para cerrar la
     diferencia: fijar un aporte, usar parte del aguinaldo, recortar en las
     categorías donde más gastás, revisar suscripciones o mover la fecha.

Como el resto de los servicios, son funciones PURAS (fáciles de testear).
Montos en centésimos de peso uruguayo.
"""

import datetime as dt
import math

from pydantic import BaseModel

from ..categories import is_discretionary, spending_label
from ..models import ExpenseKind, Goal
from . import finance

MAX_MILESTONES = 12        # más de 12 hitos no se leen: salteamos meses
SUGGESTED_MONTHS = 12      # sin fecha ni ahorro: proponemos llegar en un año
MAX_CUT_PCT = 30           # no sugerimos recortar más del 30% de una categoría
AGUINALDO_SHARE = 2        # sugerimos usar la MITAD del aguinaldo (1/2)


class Milestone(BaseModel):
    year: int
    month: int
    saved_cents: int          # lo que deberías tener ahorrado ese mes
    progress_pct: float
    aguinaldo_cents: int      # > 0 si ese mes cobrás aguinaldo
    is_last: bool


class PlanTip(BaseModel):
    # "set_contribution" | "aguinaldo" | "cut" | "subscriptions" | "extend"
    kind: str
    title: str
    detail: str
    amount_cents: int | None = None   # el número protagonista del consejo


class GoalPlan(BaseModel):
    goal_id: int
    name: str
    completed: bool
    remaining_cents: int
    # "deadline" = calculado para llegar a la fecha límite
    # "contribution" = según lo que hoy se le asigna por mes
    # "suggested" = sin fecha ni ahorro: proponemos llegar en 12 meses
    based_on: str
    monthly_cents: int
    weekly_cents: int
    daily_cents: int
    months: int
    finish_year: int
    finish_month: int
    current_contribution_cents: int
    gap_cents: int                    # cuánto le falta al aporte actual para cumplir el plan
    milestones: list[Milestone]
    tips: list[PlanTip]


# --- Ayudantes --------------------------------------------------------------

def months_until(today: dt.date, date: dt.date) -> int:
    """Meses enteros entre hoy y una fecha (al menos 1)."""
    return max((date.year - today.year) * 12 + date.month - today.month, 1)


def month_name(year: int, month: int) -> str:
    names = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
    return f"{names[month - 1]} {year}"


def money(cents: int) -> str:
    """$ 12.345 (formato uruguayo, sin decimales) para armar los textos."""
    # floor(x + 0.5) y no round(): round() de Python redondea 0,5 "al par" y
    # el frontend (JavaScript) hacia arriba; así los dos muestran lo mismo.
    #   = espacio "que no se corta": el $ nunca queda solo al final de una línea
    return "$ " + f"{math.floor(cents / 100 + 0.5):,}".replace(",", ".")


def discretionary_spending(data: finance.FinanceData, today: dt.date, rate: float | None, months: int = 3) -> dict[str, int]:
    """
    Promedio mensual de los gastos RECORTABLES (delivery, salidas, ropa…),
    agrupados por su nombre más concreto. Usa los últimos meses completos,
    con el mismo criterio que finance.average_variable_expenses.
    Los gastos fijos y los esenciales (alquiler, luz, súper…) nunca entran.
    """
    variables = [
        e for e in data.expenses
        if e.kind == ExpenseKind.variable and is_discretionary(e.category, e.subcategory)
    ]
    if not variables:
        return {}
    first_date = min(e.date for e in variables)
    periods = []
    for back in range(1, months + 1):
        y, m = finance.add_months(today.year, today.month, -back)
        if finance.month_bounds(y, m)[1] < first_date:
            break
        periods.append((y, m))
    if not periods:
        periods = [(today.year, today.month)]
    totals: dict[str, int] = {}
    for e in variables:
        for y, m in periods:
            amount = finance.expense_in_month(e, y, m, rate)
            if amount:
                key = spending_label(e.category, e.subcategory)
                totals[key] = totals.get(key, 0) + amount
    return {k: round(v / len(periods)) for k, v in totals.items()}


def build_milestones(
    data: finance.FinanceData, goal: Goal, monthly: int, months: int, today: dt.date, rate: float | None,
) -> list[Milestone]:
    """Lo que deberías tener ahorrado al final de cada mes del plan."""
    step = math.ceil(months / MAX_MILESTONES)  # ej: 30 meses -> un hito cada 3
    result = []
    for k in range(1, months + 1):
        if k % step and k != months:
            continue
        y, m = finance.add_months(today.year, today.month, k)
        saved = min(goal.saved_cents + monthly * k, goal.target_cents)
        aguinaldo = sum(finance.aguinaldo_in_month(i, y, m, rate) for i in data.incomes)
        result.append(Milestone(
            year=y, month=m, saved_cents=saved,
            progress_pct=round(saved / goal.target_cents * 100, 1),
            aguinaldo_cents=aguinaldo, is_last=k == months,
        ))
    return result


# --- El plan ----------------------------------------------------------------

def goal_plan(data: finance.FinanceData, goal: Goal, today: dt.date, rate: float | None) -> GoalPlan:
    capacity = finance.savings_capacity(data, today, rate)
    projections = {p.goal_id: p for p in finance.project_goals(data.goals, capacity.monthly_savings_cents, today)}
    p = projections[goal.id]
    remaining = p.remaining_cents
    contribution = p.monthly_contribution_cents

    # 1) ¿Cuánto por mes? Manda la fecha límite; si no hay, el aporte actual.
    if remaining == 0:
        based_on, months, monthly = "contribution", 0, 0
    elif goal.deadline:
        based_on = "deadline"
        months = months_until(today, goal.deadline)
        monthly = math.ceil(remaining / months)
    elif contribution > 0:
        based_on, months, monthly = "contribution", p.months_needed, contribution
    else:
        based_on, months = "suggested", SUGGESTED_MONTHS
        monthly = math.ceil(remaining / months)

    finish_y, finish_m = finance.add_months(today.year, today.month, months)
    gap = max(monthly - contribution, 0)

    tips: list[PlanTip] = []
    if remaining and gap:
        tips = _tips(data, goal, p, projections, capacity, monthly, months, gap, today, rate)

    return GoalPlan(
        goal_id=goal.id, name=goal.name, completed=remaining == 0, remaining_cents=remaining,
        based_on=based_on, monthly_cents=monthly,
        weekly_cents=math.ceil(monthly * 12 / 52), daily_cents=math.ceil(monthly * 12 / 365),
        months=months, finish_year=finish_y, finish_month=finish_m,
        current_contribution_cents=contribution, gap_cents=gap,
        milestones=build_milestones(data, goal, monthly, months, today, rate) if remaining else [],
        tips=tips,
    )


def _tips(data, goal, p, projections, capacity, monthly, months, gap, today, rate) -> list[PlanTip]:
    """Ideas para cerrar la diferencia entre lo que hace falta y lo que se aporta hoy."""
    tips = []

    # a) Si tu ahorro alcanza (sacando lo que ya va a OTRAS metas con aporte fijo),
    #    alcanza con fijarle el aporte a esta meta.
    others_fixed = sum(
        q.monthly_contribution_cents for gid, q in projections.items()
        if gid != goal.id and q.contribution_is_manual and q.remaining_cents > 0
    )
    available = capacity.monthly_savings_cents - others_fixed
    if available >= monthly:
        tips.append(PlanTip(
            kind="set_contribution", amount_cents=monthly,
            title=f"Fijale un aporte de {money(monthly)} por mes",
            detail="Tu ahorro mensual alcanza: hoy se reparte entre varias metas. "
                   "Fijando el aporte, esta meta tiene su parte asegurada.",
        ))
        return tips  # con esto alcanza; no hace falta recortar nada

    shortfall = monthly - max(available, 0)  # lo que no sale de tu ahorro actual

    # Primero, lo que sí se puede: darle a esta meta todo el ahorro disponible.
    # (Los recortes de abajo cubren solo lo que falta DESPUÉS de esto.)
    if available > p.monthly_contribution_cents:
        tips.append(PlanTip(
            kind="set_contribution", amount_cents=available,
            title=f"Subí el aporte a {money(available)} por mes",
            detail=f"Es todo lo que hoy podés ahorrar. Aun así faltarían {money(shortfall)} por mes: "
                   "estas ideas cubren esa parte.",
        ))

    # b) Aguinaldo: usar la mitad del próximo baja el aporte de todos los meses.
    nxt = finance.next_aguinaldo(data, today, rate)
    if nxt and nxt[0] < months:
        offset, amount = nxt
        share = amount // AGUINALDO_SHARE
        y, m = finance.add_months(today.year, today.month, offset)
        if share >= p.remaining_cents:
            tips.append(PlanTip(
                kind="aguinaldo", amount_cents=p.remaining_cents,
                title=f"Con la mitad del aguinaldo de {month_name(y, m)} la cumplís",
                detail=f"Te faltan {money(p.remaining_cents)} y medio aguinaldo son unos {money(share)}.",
            ))
        else:
            new_monthly = math.ceil((p.remaining_cents - share) / months)
            tips.append(PlanTip(
                kind="aguinaldo", amount_cents=share,
                title=f"Poné la mitad del aguinaldo de {month_name(y, m)} ({money(share)})",
                detail=f"El aporte necesario baja de {money(monthly)} a {money(new_monthly)} por mes.",
            ))

    # c) Recortes: solo en gastos recortables, empezando por donde más gastás.
    spending = sorted(discretionary_spending(data, today, rate).items(), key=lambda kv: kv[1], reverse=True)
    for label, avg in spending[:3]:
        if avg <= 0:
            continue
        pct = math.ceil(shortfall / avg * 100)
        if pct <= MAX_CUT_PCT:
            tips.append(PlanTip(
                kind="cut", amount_cents=shortfall,
                title=f"Gastá {pct}% menos en {label}",
                detail=f"Hoy gastás unos {money(avg)} por mes en {label}. "
                       f"Bajando {money(shortfall)} cerrás la diferencia.",
            ))
            break  # un solo recorte que alcanza es más claro que tres a medias
        freed = avg * 20 // 100
        tips.append(PlanTip(
            kind="cut", amount_cents=freed,
            title=f"Recortá 20% en {label}",
            detail=f"Gastás unos {money(avg)} por mes ahí: liberás {money(freed)} por mes.",
        ))

    # d) Suscripciones: suelen ser plata "invisible".
    y, m = today.year, today.month
    subs = sum(finance.subscription_in_month(s, y, m, rate) for s in data.subscriptions)
    if subs:
        tips.append(PlanTip(
            kind="subscriptions", amount_cents=subs,
            title=f"Revisá tus suscripciones ({money(subs)}/mes)",
            detail="Pausar alguna que no uses tanto, aunque sea mientras juntás para esta meta, también suma.",
        ))

    # e) Si ya aportás algo pero no llegás a la fecha: ¿y si la movés?
    if goal.deadline and p.estimated_date:
        tips.append(PlanTip(
            kind="extend",
            title=f"O mové la fecha a {month_name(p.estimated_date.year, p.estimated_date.month)}",
            detail=f"Con lo que hoy le aportás ({money(p.monthly_contribution_cents)}/mes) llegás ahí sin cambiar nada.",
        ))
    return tips
