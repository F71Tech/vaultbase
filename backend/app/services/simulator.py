"""
Simulador de compras: "si compro X por $Y, ¿cómo me afecta?".

Idea central: cada estrategia de compra es un CALENDARIO DE PAGOS mes a mes.
  - Contado:              [Y]                (todo este mes)
  - Ahorrar primero:      [A, A, A, resto]   (A = ahorro mensual; se compra al final)
  - 6 cuotas sin interés: [Y/6, Y/6, ... ]   (6 meses)
  - 6 cuotas con interés: [C, C, ...]        (C = cuota con interés, sistema francés)

Después "jugamos" los meses uno por uno: cada pago se descuenta primero del
ahorro que sobra (el que no va a ninguna meta) y, si no alcanza, se le quita
a las metas. Si ni así alcanza, ese mes queda en NEGATIVO.
Comparando con el escenario sin compra sabemos cuánto se atrasa cada meta.

Elegimos la estrategia de MENOR DAÑO con este orden de prioridades:
  1) que ningún mes quede en negativo;
  2) el menor costo extra (intereses);
  3) el menor atraso total de las metas;
  4) tener la compra lo antes posible;
  5) comprometer la menor cantidad de meses.
"""

import datetime as dt
import math

from pydantic import BaseModel, Field

from ..models import Goal
from .finance import add_months_to_date, allocate_contributions

MAX_MONTHS = 600  # horizonte de simulación (50 años): más allá, "no se alcanza"


class InstallmentOption(BaseModel):
    count: int = Field(ge=2, le=60)                        # cantidad de cuotas
    annual_rate_pct: float = Field(default=0, ge=0, le=500)  # tasa efectiva anual (0 = sin interés)


class GoalDelay(BaseModel):
    goal_id: int
    name: str
    months_without_purchase: int | None
    months_with_purchase: int | None
    delay_months: int | None   # None = con esta compra la meta ya no se alcanza


class StrategyResult(BaseModel):
    key: str                   # "cash", "save_first", "installments_6", ...
    label: str                 # texto para mostrar
    purchase_in_months: int    # 0 = comprás ahora
    purchase_date: dt.date
    months_committed: int      # durante cuántos meses pagás
    monthly_payment_cents: int
    total_cost_cents: int
    extra_cost_cents: int      # intereses
    negative_months: int       # meses en los que no alcanza la plata
    worst_month_balance_cents: int  # el peor saldo de ahorro de un mes
    year_balance_after_cents: int   # cómo queda el balance del año
    goal_delays: list[GoalDelay]
    recommended: bool = False


class SimulationResult(BaseModel):
    price_cents: int
    monthly_savings_cents: int
    strategies: list[StrategyResult]
    recommended_key: str | None
    recommendation: str


# --- Calendarios de pago ----------------------------------------------------

def french_installment(price_cents: int, count: int, annual_rate_pct: float) -> int:
    """
    Cuota del sistema francés (cuota fija, la que usan bancos y tarjetas).
    Convertimos la tasa anual a mensual: (1 + anual)^(1/12) - 1.
    """
    if annual_rate_pct == 0:
        return math.ceil(price_cents / count)
    i = (1 + annual_rate_pct / 100) ** (1 / 12) - 1
    return math.ceil(price_cents * i / (1 - (1 + i) ** -count))


def installment_schedule(price_cents: int, count: int, annual_rate_pct: float) -> list[int]:
    """
    Calendario de cuotas. Sin interés, repartimos el precio EXACTO: si no da
    justo, las primeras cuotas llevan 1 centésimo más (500.000 / 6 =
    83.334 x 2 + 83.333 x 4). Si redondeáramos todas para arriba, "sin interés"
    terminaría costando unos centésimos de más.
    """
    if annual_rate_pct == 0:
        base, extra = divmod(price_cents, count)
        return [base + 1] * extra + [base] * (count - extra)
    return [french_installment(price_cents, count, annual_rate_pct)] * count


def save_first_schedule(price_cents: int, monthly_savings_cents: int) -> list[int]:
    """Apartar todo el ahorro del mes hasta juntar el precio."""
    months = math.ceil(price_cents / monthly_savings_cents)
    schedule = [monthly_savings_cents] * (months - 1)
    schedule.append(price_cents - monthly_savings_cents * (months - 1))
    return schedule


# --- Motor de simulación ----------------------------------------------------

def _months_per_goal(goals: list[Goal], allocation: dict[int, int],
                     monthly_savings_cents: int, schedule: list[int]) -> tuple[dict[int, int | None], list[int]]:
    """
    Simula mes a mes y devuelve:
      - cuántos meses tarda cada meta en completarse (None = nunca);
      - el saldo de ahorro de cada mes del calendario (puede ser negativo).
    """
    total_alloc = sum(allocation.values())
    free = max(monthly_savings_cents - total_alloc, 0)  # ahorro que no va a ninguna meta
    remaining = {g.id: max(g.target_cents - g.saved_cents, 0) for g in goals}
    done: dict[int, int | None] = {gid: 0 for gid, rest in remaining.items() if rest == 0}
    balances = []
    debt = 0  # lo que no se pudo cubrir un mes pasa al siguiente

    for month in range(MAX_MONTHS):
        scheduled = schedule[month] if month < len(schedule) else 0
        if month < len(schedule):
            balances.append(monthly_savings_cents - scheduled)
        payment = scheduled + debt

        # 1) el pago sale primero del ahorro libre...
        from_free = min(payment, free)
        rest = payment - from_free
        # 2) ...y lo que falta se les quita a las metas, en proporción
        cut = min(rest, total_alloc)
        debt = rest - cut
        factor = 1 - cut / total_alloc if total_alloc else 0

        for gid, contribution in allocation.items():
            if gid in done:
                continue
            remaining[gid] -= contribution * factor
            if remaining[gid] <= 0:
                done[gid] = month + 1
        if len(done) == len(remaining) and month >= len(schedule) and debt == 0:
            break

    return {gid: done.get(gid) for gid in remaining}, balances


def _evaluate(key: str, label: str, schedule: list[int], purchase_in: int, price_cents: int,
              goals: list[Goal], allocation: dict[int, int], monthly_savings_cents: int,
              baseline: dict[int, int | None], year_balance_cents: int, today: dt.date) -> StrategyResult:
    with_purchase, balances = _months_per_goal(goals, allocation, monthly_savings_cents, schedule)

    delays = []
    for g in goals:
        before, after = baseline[g.id], with_purchase[g.id]
        delay = after - before if (before is not None and after is not None) else None
        delays.append(GoalDelay(goal_id=g.id, name=g.name, months_without_purchase=before,
                                months_with_purchase=after, delay_months=delay))

    # Pagos que caen dentro de este año calendario
    months_left_in_year = 12 - today.month + 1
    paid_this_year = sum(schedule[:months_left_in_year])
    # "Ahorrar primero" y "esperar al aguinaldo" no son gastos mes a mes: lo que
    # impacta al balance anual es la compra en sí, en el mes en que ocurre.
    if key in ("save_first", "wait_aguinaldo"):
        paid_this_year = price_cents if purchase_in < months_left_in_year else 0

    total = sum(schedule)
    return StrategyResult(
        key=key, label=label, purchase_in_months=purchase_in,
        purchase_date=add_months_to_date(today, purchase_in),
        months_committed=len(schedule), monthly_payment_cents=schedule[0],
        total_cost_cents=total, extra_cost_cents=total - price_cents,
        negative_months=sum(1 for b in balances if b < 0),
        worst_month_balance_cents=min(balances),
        year_balance_after_cents=year_balance_cents - paid_this_year,
        goal_delays=delays,
    )


MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
               "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def simulate_purchase(price_cents: int, monthly_savings_cents: int, goals: list[Goal],
                      year_balance_cents: int, today: dt.date,
                      installments: list[InstallmentOption],
                      aguinaldo: tuple[int, int] | None = None) -> SimulationResult:
    """
    `aguinaldo` = (en cuántos meses se cobra el próximo, monto líquido).
    El aguinaldo no forma parte del ahorro mensual, así que usarlo para una
    compra no le quita nada a las metas: solo hay que esperar a cobrarlo.
    """
    allocation = allocate_contributions(goals, monthly_savings_cents)
    baseline, _ = _months_per_goal(goals, allocation, monthly_savings_cents, [])
    common = dict(price_cents=price_cents, goals=goals, allocation=allocation,
                  monthly_savings_cents=monthly_savings_cents, baseline=baseline,
                  year_balance_cents=year_balance_cents, today=today)

    strategies = [_evaluate("cash", "Pagar al contado ahora", [price_cents], 0, **common)]

    if monthly_savings_cents > 0:
        schedule = save_first_schedule(price_cents, monthly_savings_cents)
        months = len(schedule)
        label = "Ahorrar primero y comprar " + ("este mes" if months == 1 else f"en {months} meses")
        strategies.append(_evaluate("save_first", label, schedule, months - 1, **common))

    if aguinaldo and aguinaldo[1] > 0:
        offset, amount = aguinaldo
        rest = max(price_cents - amount, 0)  # lo que el aguinaldo no alcanza a cubrir
        month = MONTH_NAMES[(today.month - 1 + offset) % 12]
        label = f"Esperar al aguinaldo de {month}" + (" y completar con ahorro" if rest else "")
        result = _evaluate("wait_aguinaldo", label, [0] * offset + [rest], offset, **common)
        result.monthly_payment_cents = rest
        result.months_committed = 1 if rest else 0
        strategies.append(result)

    for option in installments:
        schedule = installment_schedule(price_cents, option.count, option.annual_rate_pct)
        if option.annual_rate_pct == 0:
            key, label = f"installments_{option.count}", f"{option.count} cuotas sin interés"
        else:
            rate = f"{option.annual_rate_pct:g}"
            key = f"installments_{option.count}_{rate}"
            label = f"{option.count} cuotas con {rate}% anual"
        strategies.append(_evaluate(key, label, schedule, 0, **common))

    # Orden de "menor daño" (ver explicación arriba)
    best = min(strategies, key=lambda s: (
        s.negative_months > 0, s.extra_cost_cents, _total_delay(s),
        s.purchase_in_months, s.months_committed,
    ))
    best.recommended = True
    return SimulationResult(
        price_cents=price_cents, monthly_savings_cents=monthly_savings_cents,
        strategies=strategies, recommended_key=best.key,
        recommendation=_explain(best, monthly_savings_cents),
    )


def _total_delay(strategy: StrategyResult) -> int:
    """Suma de meses de atraso de todas las metas (una meta perdida pesa mucho)."""
    return sum(MAX_MONTHS if d.delay_months is None else d.delay_months
               for d in strategy.goal_delays)


def _explain(best: StrategyResult, monthly_savings_cents: int) -> str:
    """Una frase en español que justifica la recomendación."""
    if monthly_savings_cents <= 0:
        return ("Hoy tus gastos igualan o superan tus ingresos: cualquier compra te deja "
                "en negativo. Conviene revisar gastos antes de comprar.")
    if best.negative_months > 0:
        return (f"Ninguna opción evita quedar en negativo; la de menor impacto es "
                f"'{best.label}'. Considerá posponer la compra.")
    max_delay = max((d.delay_months or 0 for d in best.goal_delays), default=0)
    delay_txt = (" y no atrasa tus metas" if max_delay == 0
                 else f" y atrasa tus metas como máximo {max_delay} mes(es)")
    if best.key == "cash":
        return "Te alcanza con el ahorro de este mes: pagalo al contado, sin deudas" + delay_txt + "."
    if best.key == "wait_aguinaldo":
        month = MONTH_NAMES[best.purchase_date.month - 1]
        return (f"Esperá al aguinaldo de {month}: lo pagás con esa plata extra, sin cuotas ni "
                f"tocar tu ahorro de todos los meses" + delay_txt + ".")
    if best.key == "save_first":
        return (f"Lo más sano es ahorrar primero: en {best.months_committed} mes(es) lo tenés, "
                f"sin intereses ni meses en negativo" + delay_txt + ".")
    if best.extra_cost_cents == 0:
        return f"'{best.label}' te deja comprarlo ya sin pagar de más ni quedar en negativo" + delay_txt + "."
    return f"'{best.label}' es la opción que menos daño hace a tu economía" + delay_txt + "."
