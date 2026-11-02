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
from .cashflow import AGUINALDO_DAY

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
    # Cuánto ayuda POR MES a cerrar la diferencia (para poder sumar las ideas).
    # None = no se puede calcular (ej: "revisá tus suscripciones").
    monthly_cents: int | None = None


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
    current_contribution_cents: int   # lo que hoy le toca a esta meta de tu ahorro mensual
    gap_cents: int                    # cuánto le falta al aporte actual para cumplir el plan
    deadline: dt.date | None          # la fecha límite exacta que puso el usuario
    monthly_savings_cents: int        # lo que te sobra por mes en total (sueldo - gastos)
    other_goals: int                  # cuántas OTRAS metas sin cumplir comparten ese ahorro
    # Cuándo llegás si no cambiás nada (None = con lo de hoy no llegás nunca)
    current_finish_year: int | None
    current_finish_month: int | None
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
        deadline=goal.deadline,
        monthly_savings_cents=max(capacity.monthly_savings_cents, 0),
        other_goals=sum(1 for gid, q in projections.items() if gid != goal.id and q.remaining_cents > 0),
        current_finish_year=p.estimated_date.year if p.estimated_date and remaining else None,
        current_finish_month=p.estimated_date.month if p.estimated_date and remaining else None,
        milestones=build_milestones(data, goal, monthly, months, today, rate) if remaining else [],
        tips=tips,
    )


def _tips(data, goal, p, projections, capacity, monthly, months, gap, today, rate) -> list[PlanTip]:
    """
    Ideas para conseguir lo que falta por mes (gap). Cada una dice cuánto
    aporta por mes (monthly_cents), así el usuario puede sumarlas y ver si alcanza.
    Textos en lenguaje simple: "gastá $ 800 menos en X", no porcentajes sueltos.
    """
    tips = []
    contribution = p.monthly_contribution_cents

    # a) Darle más de tu ahorro a esta meta (hoy se reparte entre todas).
    #    Lo que ya va FIJO a otras metas no se toca.
    others_fixed = sum(
        q.monthly_contribution_cents for gid, q in projections.items()
        if gid != goal.id and q.contribution_is_manual and q.remaining_cents > 0
    )
    available = capacity.monthly_savings_cents - others_fixed
    if available >= monthly:
        tips.append(PlanTip(
            kind="set_contribution", amount_cents=monthly, monthly_cents=gap,
            title=f"Destiná {money(monthly)} por mes a esta meta",
            detail=f"Te sobran {money(capacity.monthly_savings_cents)} por mes, pero hoy se reparten entre "
                   "todas tus metas. Si a esta le das su parte fija, llegás a tiempo.",
        ))
        return tips  # con esto alcanza; no hace falta recortar nada

    shortfall = monthly - max(available, 0)  # lo que no sale de tu ahorro actual
    if available > contribution:
        tips.append(PlanTip(
            kind="set_contribution", amount_cents=available, monthly_cents=available - contribution,
            title=f"Destiná todo tu ahorro a esta meta ({money(available)} por mes)",
            detail=("Es todo lo que te sobra por mes" + (
                f", sacando los {money(others_fixed)} que ya van fijos a otras metas" if others_fixed else ""
            ) + ". Las otras metas esperarían un poco."),
        ))

    # b) Aguinaldo: poner la mitad del próximo baja lo que hay que juntar cada mes.
    # Solo si se cobra ANTES de la fecha límite (si vence el 1/12, el del 18/12 llega tarde)
    nxt = finance.next_aguinaldo(data, today, rate)
    if nxt:
        offset, amount = nxt
        y, m = finance.add_months(today.year, today.month, offset)
        pay_date = dt.date(y, m, AGUINALDO_DAY[m])
        on_time = pay_date <= goal.deadline if goal.deadline else offset <= months
    if nxt and on_time:
        share = amount // AGUINALDO_SHARE
        if share >= p.remaining_cents:
            tips.append(PlanTip(
                kind="aguinaldo", amount_cents=p.remaining_cents, monthly_cents=gap,
                title=f"Usá parte del aguinaldo de {month_name(y, m)}",
                detail=f"Te faltan {money(p.remaining_cents)} y con medio aguinaldo ({money(share)}) ya la cumplís.",
            ))
        else:
            new_monthly = math.ceil((p.remaining_cents - share) / months)
            tips.append(PlanTip(
                kind="aguinaldo", amount_cents=share, monthly_cents=monthly - new_monthly,
                title=f"Usá la mitad del aguinaldo de {month_name(y, m)} ({money(share)})",
                detail=f"Así ya no necesitás juntar {money(monthly)} por mes, sino {money(new_monthly)}.",
            ))

    # c) Recortes: solo en gastos recortables, empezando por donde más gastás.
    spending = sorted(discretionary_spending(data, today, rate).items(), key=lambda kv: kv[1], reverse=True)
    for label, avg in spending[:3]:
        if avg <= 0:
            continue
        pct = math.ceil(shortfall / avg * 100)
        cut = shortfall if pct <= MAX_CUT_PCT else avg * 20 // 100
        tips.append(PlanTip(
            kind="cut", amount_cents=cut, monthly_cents=cut,
            title=f"Gastá {money(cut)} menos por mes en {label}",
            detail=f"Hoy gastás unos {money(avg)} por mes ahí: sería un "
                   f"{pct if pct <= MAX_CUT_PCT else 20}% menos.",
        ))
        if pct <= MAX_CUT_PCT:
            break  # un solo recorte que alcanza es más claro que tres a medias

    # d) Suscripciones: suelen ser plata "invisible".
    y, m = today.year, today.month
    subs = sum(finance.subscription_in_month(s, y, m, rate) for s in data.subscriptions)
    if subs:
        tips.append(PlanTip(
            kind="subscriptions", amount_cents=subs,
            title="Revisá tus suscripciones",
            detail=f"Pagás {money(subs)} por mes en total. Pausar alguna que no uses tanto, "
                   "aunque sea mientras juntás, también suma.",
        ))

    # e) La alternativa: no cambiar nada y llegar un poco más tarde.
    if goal.deadline and p.estimated_date:
        tips.append(PlanTip(
            kind="extend",
            title=f"Mover la fecha a {month_name(p.estimated_date.year, p.estimated_date.month)}",
            detail=f"Ahorrando lo que hoy te sobra para esta meta ({money(contribution)} por mes), "
                   "sin recortar nada, llegás en esa fecha.",
        ))
    return tips
