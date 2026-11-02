"""
Tests de los cálculos financieros. Como las funciones son puras, armamos los
datos directamente en Python (sin base de datos ni servidor).
"""

import datetime as dt

from backend.app.models import Expense, Goal, Income, Subscription
from backend.app.services import finance

HOY = dt.date(2026, 11, 15)
RATE = 40.0


def sueldo(monto=6_000_000, **kw):  # $ 60.000
    return Income(id=1, user_id=1, source="Sueldo", amount_cents=monto,
                  start_date=dt.date(2026, 1, 1), **kw)


def gasto(monto, fecha, category="food", kind="variable", **kw):
    return Expense(id=None, user_id=1, category=category, amount_cents=monto,
                   kind=kind, date=fecha, **kw)


def suscripcion(monto, currency="USD", **kw):
    return Subscription(id=1, user_id=1, name="Spotify", amount_cents=monto, currency=currency,
                        created_at=dt.datetime(2026, 1, 1), **kw)


def test_frecuencias_se_normalizan_a_mensual():
    assert finance.income_in_month(sueldo(frequency="biweekly", monto=100), 2026, 11, RATE) == 200
    assert finance.income_in_month(sueldo(frequency="annual", monto=1200), 2026, 11, RATE) == 100
    unico = sueldo(frequency="one_time", monto=500)  # cobrado en enero
    assert finance.income_in_month(unico, 2026, 1, RATE) == 500
    assert finance.income_in_month(unico, 2026, 2, RATE) == 0


def test_ingreso_terminado_no_cuenta():
    viejo = sueldo(end_date=dt.date(2026, 6, 30))
    assert finance.income_in_month(viejo, 2026, 6, RATE) > 0
    assert finance.income_in_month(viejo, 2026, 7, RATE) == 0


def test_resumen_del_mes():
    data = finance.FinanceData(
        incomes=[sueldo()],
        expenses=[
            gasto(1_500_000, dt.date(2026, 1, 1), category="housing", kind="fixed"),  # alquiler
            gasto(6_000, dt.date(2026, 11, 3)),                                     # alfajor
            gasto(9_999, dt.date(2026, 10, 3)),                                     # otro mes
        ],
        subscriptions=[suscripcion(1_000)],  # US$ 10 -> $ 400
    )
    m = finance.month_summary(data, 2026, 11, RATE)
    assert m.income_cents == 6_000_000
    assert m.fixed_expenses_cents == 1_500_000
    assert m.subscriptions_cents == 40_000
    assert m.variable_expenses_cents == 6_000
    assert m.balance_cents == 6_000_000 - 1_500_000 - 40_000 - 6_000
    assert m.by_category == {"housing": 1_500_000, "food": 6_000, "subscriptions": 40_000}


def test_gasto_en_dolares_usa_su_cotizacion_congelada():
    g = gasto(1_000, dt.date(2026, 11, 1), currency="USD", exchange_rate=38.0)
    assert finance.expense_in_month(g, 2026, 11, RATE) == 38_000  # no 40.000


def test_capacidad_de_ahorro_usa_promedio_de_variables():
    data = finance.FinanceData(
        incomes=[sueldo()],
        expenses=[
            gasto(1_000_000, dt.date(2026, 1, 1), category="housing", kind="fixed"),
            gasto(300_000, dt.date(2026, 8, 10)),
            gasto(600_000, dt.date(2026, 9, 10)),
            gasto(900_000, dt.date(2026, 10, 10)),
        ],
    )
    c = finance.savings_capacity(data, HOY, RATE)
    assert c.disposable_income_cents == 5_000_000
    assert c.avg_variable_expenses_cents == 600_000  # (3+6+9)/3 mil
    assert c.monthly_savings_cents == 4_400_000


def test_promedio_ignora_meses_antes_de_empezar():
    # Empezó a usar la app en octubre: agosto y septiembre no cuentan como 0
    data = finance.FinanceData(expenses=[gasto(900_000, dt.date(2026, 10, 10))])
    assert finance.average_variable_expenses(data, HOY, RATE) == 900_000


def test_anio_proyecta_meses_futuros():
    data = finance.FinanceData(incomes=[sueldo()], expenses=[gasto(500_000, dt.date(2026, 10, 1))])
    y = finance.year_summary(data, 2026, HOY, RATE)
    assert len(y.months) == 12
    assert y.months[10].projected is False   # noviembre (actual)
    assert y.months[11].projected is True    # diciembre (futuro)
    assert y.months[11].variable_expenses_cents == 500_000


def test_presupuesto_de_comida_por_semanas():
    data = finance.FinanceData(
        incomes=[sueldo()],
        expenses=[
            gasto(200_000, dt.date(2026, 11, 2), subcategory="groceries"),
            gasto(6_000, dt.date(2026, 11, 15), subcategory="snacks"),
        ],
    )
    cap = finance.savings_capacity(data, HOY, RATE)
    f = finance.food_budget(data, cap, 30, HOY, RATE)
    assert f.monthly_budget_cents == 1_800_000           # 30% de 60.000
    assert len(f.weeks) == 5                             # 7+7+7+7+2 días
    assert f.weeks[0].budget_cents == 1_800_000 * 7 // 30
    assert f.weeks[0].spent_cents == 200_000
    assert f.weeks[2].is_current                         # el 15 cae en la semana 3
    assert f.by_subcategory == {"groceries": 200_000, "snacks": 6_000}


def test_metas_reparto_y_fechas():
    metas = [
        Goal(id=1, user_id=1, name="Viaje", target_cents=1_000_000, saved_cents=0),
        Goal(id=2, user_id=1, name="Auto", target_cents=2_000_000, saved_cents=500_000,
             monthly_contribution_cents=100_000, deadline=dt.date(2027, 3, 1)),
        Goal(id=3, user_id=1, name="Hecha", target_cents=100, saved_cents=100),
    ]
    p = {g.goal_id: g for g in finance.project_goals(metas, 300_000, HOY)}
    # Auto tiene aporte manual (100.000); Viaje recibe lo que sobra (200.000)
    assert p[2].monthly_contribution_cents == 100_000
    assert p[1].monthly_contribution_cents == 200_000
    assert p[1].months_needed == 5
    assert p[1].estimated_date == dt.date(2027, 4, 15)
    assert p[2].months_needed == 15 and p[2].status == "behind"
    assert p[2].progress_pct == 25.0
    assert p[3].status == "completed"


def test_meta_inalcanzable_si_no_hay_ahorro():
    meta = Goal(id=1, user_id=1, name="Casa", target_cents=1_000, saved_cents=0)
    assert finance.project_goals([meta], 0, HOY)[0].status == "unreachable"
