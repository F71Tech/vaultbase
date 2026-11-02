"""Tests del plan de una meta (cuánto apartar, hitos y consejos)."""

import datetime as dt

from backend.app.models import Expense, Goal, Income, Subscription
from backend.app.services import finance
from backend.app.services.goal_plan import goal_plan

HOY = dt.date(2026, 11, 15)
RATE = 40.0


def sueldo(**kw):  # $ 60.000 por mes
    return Income(id=1, user_id=1, source="Sueldo", amount_cents=6_000_000,
                  start_date=dt.date(2026, 1, 1), **kw)


def gasto_por_mes(monto, category="food", subcategory="delivery"):
    """Un gasto variable igual en cada uno de los últimos 3 meses (por defecto, delivery)."""
    return [Expense(id=None, user_id=1, category=category, subcategory=subcategory, amount_cents=monto,
                    kind="variable", date=dt.date(2026, m, 10)) for m in (8, 9, 10)]


def meta(id, target, deadline=None, saved=0):
    return Goal(id=id, user_id=1, name=f"Meta {id}", target_cents=target,
                saved_cents=saved, deadline=deadline)


def test_con_fecha_limite_alcanza_fijando_el_aporte():
    viaje = meta(1, 30_000_000, dt.date(2027, 5, 1))   # $ 300.000 en 6 meses
    data = finance.FinanceData(incomes=[sueldo()], goals=[viaje, meta(2, 99_000_000)])
    plan = goal_plan(data, viaje, HOY, RATE)
    assert plan.based_on == "deadline" and plan.months == 6
    assert plan.monthly_cents == 5_000_000
    # hoy recibe la mitad del ahorro (comparte con la meta 2): le faltan 2 millones
    assert plan.current_contribution_cents == 3_000_000 and plan.gap_cents == 2_000_000
    assert [t.kind for t in plan.tips] == ["set_contribution"]
    assert (plan.finish_year, plan.finish_month) == (2027, 5)
    assert len(plan.milestones) == 6 and plan.milestones[-1].is_last
    assert plan.milestones[0].saved_cents == 5_000_000
    assert plan.milestones[-1].progress_pct == 100.0


def test_si_no_alcanza_sugiere_aguinaldo_recortes_y_fecha():
    casa = meta(1, 100_000_000, dt.date(2027, 11, 1))  # 12 meses
    data = finance.FinanceData(
        incomes=[sueldo(aguinaldo_cents=3_000_000)], expenses=gasto_por_mes(1_000_000),
        subscriptions=[Subscription(id=1, user_id=1, name="Spotify", amount_cents=1_000,
                                    currency="USD", created_at=dt.datetime(2026, 1, 1))],
        goals=[casa],
    )
    plan = goal_plan(data, casa, HOY, RATE)
    # es la única meta: ya recibe todo el ahorro, así que no sugiere subir el aporte
    assert [t.kind for t in plan.tips] == ["aguinaldo", "cut", "subscriptions", "extend"]
    aguinaldo = plan.tips[0]
    assert aguinaldo.amount_cents == 1_500_000 and "diciembre 2026" in aguinaldo.title
    assert plan.tips[1].title == "Recortá 20% en Delivery"
    # diciembre trae aguinaldo: el hito lo marca
    assert plan.milestones[0].month == 12 and plan.milestones[0].aguinaldo_cents == 3_000_000


def test_un_recorte_chico_alcanza():
    meta_1 = meta(1, 31_200_000, dt.date(2027, 5, 1))  # 5.200.000/mes; ahorrás 5.000.000
    meta_1.monthly_contribution_cents = 1_000_000      # pero hoy le aporta solo 1.000.000
    data = finance.FinanceData(incomes=[sueldo()], expenses=gasto_por_mes(1_000_000), goals=[meta_1])
    plan = goal_plan(data, meta_1, HOY, RATE)
    # primero: darle todo el ahorro; después, el recorte cubre solo lo que falta
    assert plan.tips[0].kind == "set_contribution" and plan.tips[0].amount_cents == 5_000_000
    corte = next(t for t in plan.tips if t.kind == "cut")
    assert corte.title == "Gastá 20% menos en Delivery" and corte.amount_cents == 200_000


def test_nunca_sugiere_recortar_gastos_esenciales():
    # Alquiler, gastos comunes y súper anotados como gastos del día: no se recortan.
    # Solo las salidas (recortables) pueden aparecer en los consejos.
    meta_1 = meta(1, 31_200_000, dt.date(2027, 5, 1))
    gastos = (gasto_por_mes(2_000_000, "housing", "rent") + gasto_por_mes(500_000, "housing", "common_fees")
              + gasto_por_mes(800_000, "food", "groceries") + gasto_por_mes(300_000, "leisure", "outings"))
    data = finance.FinanceData(incomes=[sueldo()], expenses=gastos, goals=[meta_1])
    cortes = [t.title for t in goal_plan(data, meta_1, HOY, RATE).tips if t.kind == "cut"]
    assert cortes and all("Salidas" in c for c in cortes)


def test_sin_gastos_recortables_no_sugiere_recortes():
    meta_1 = meta(1, 31_200_000, dt.date(2027, 5, 1))
    data = finance.FinanceData(incomes=[sueldo()], expenses=gasto_por_mes(1_000_000, "housing", "rent"),
                               goals=[meta_1])
    assert all(t.kind != "cut" for t in goal_plan(data, meta_1, HOY, RATE).tips)


def test_sin_fecha_ni_ahorro_propone_un_anio():
    sin_plata = meta(1, 1_200_000)
    plan = goal_plan(finance.FinanceData(goals=[sin_plata]), sin_plata, HOY, RATE)
    assert plan.based_on == "suggested" and plan.months == 12
    assert plan.monthly_cents == 100_000 and plan.weekly_cents == 23_077


def test_hitos_largos_se_resumen():
    lejos = meta(1, 3_000_000)  # 30 meses a 100.000
    data = finance.FinanceData(goals=[lejos])
    lejos.monthly_contribution_cents = 100_000
    plan = goal_plan(data, lejos, HOY, RATE)
    assert plan.months == 30 and len(plan.milestones) == 10   # uno cada 3 meses
    assert plan.tips == []                                    # el aporte ya alcanza


def test_meta_cumplida():
    hecha = meta(1, 1_000, saved=1_000)
    plan = goal_plan(finance.FinanceData(goals=[hecha]), hecha, HOY, RATE)
    assert plan.completed and plan.milestones == [] and plan.tips == []


def test_api_plan_y_aislamiento(client, make_user):
    ana = make_user("ana@example.com")
    beto = make_user("beto@example.com")
    g = client.post("/api/goals", json={"name": "Bici", "target_cents": 1_200_000}, headers=ana).json()
    res = client.get(f"/api/finance/goals/{g['id']}/plan", headers=ana)
    assert res.status_code == 200 and res.json()["based_on"] == "suggested"
    assert client.get(f"/api/finance/goals/{g['id']}/plan", headers=beto).status_code == 404
