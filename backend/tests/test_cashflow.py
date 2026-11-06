"""Tests de "Tu plata hoy": se calcula sola con los movimientos del mes."""

import datetime as dt

from backend.app.models import Expense, Goal, Income, Subscription
from backend.app.services import finance
from backend.app.services.cashflow import goal_budget, money_now, on_day

HOY = dt.date(2026, 11, 10)
RATE = 40.0
UTC = dt.timezone.utc


def datos(extra_gastos=()):
    # Sueldo de $ 60.000: $ 20.000 de adelanto el 15 y el resto ($ 40.000) el 1
    sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=6_000_000, start_date=dt.date(2026, 1, 1),
                    pay_day=1, advance_cents=2_000_000, advance_day=15)
    alquiler = Expense(id=1, user_id=1, category="housing", subcategory="rent", kind="fixed",
                       amount_cents=1_500_000, date=dt.date(2026, 1, 5))
    spotify = Subscription(id=1, user_id=1, name="Spotify", amount_cents=1_000, currency="USD",
                           billing_day=20, created_at=dt.datetime(2026, 1, 1, tzinfo=UTC))
    # Historial: $ 9.000 por mes de gastos variables (agosto a octubre)
    historial = [Expense(id=None, user_id=1, category="food", amount_cents=900_000, kind="variable",
                         date=dt.date(2026, m, 10)) for m in (8, 9, 10)]
    return finance.FinanceData(incomes=[sueldo], expenses=[alquiler, *historial, *extra_gastos],
                               subscriptions=[spotify])


def gasto(monto, fecha):
    return Expense(id=None, user_id=1, category="food", amount_cents=monto, kind="variable", date=fecha)


def test_plata_de_hoy_y_cuanto_ahorrar():
    # (los gastos de octubre del historial no cuentan: solo este mes)
    extra = [gasto(50_000, dt.date(2026, 11, 8)),
             gasto(30_000, dt.date(2026, 11, 12))]   # con fecha futura: todavía no
    m = money_now(datos(extra), HOY, RATE)
    # Entró el sueldo del 1 (40.000); salieron el alquiler del 5 (15.000) y el gasto del 8 (500)
    assert m.received_cents == 4_000_000 and m.spent_cents == 1_550_000
    assert m.current_cents == 2_450_000
    # Hasta fin de mes: entra el adelanto (20.000) el 15 y sale Spotify (US$ 10 = 400) el 20
    assert [(e.date.day, e.kind) for e in m.upcoming] == [(15, "advance"), (20, "subscription")]
    assert m.incoming_cents == 2_000_000 and m.bills_cents == 40_000
    # Quedan 21 días hasta el próximo cobro (1/12): a tu ritmo (9.000/mes = 295,89/día) gastás 6.213,70
    assert (m.since, m.next_pay) == (dt.date(2026, 11, 1), dt.date(2026, 12, 1))
    assert m.days_left == 21 and m.usual_spending_cents == 621_370
    assert m.free_cents == 4_410_000
    assert m.can_save_cents == 3_788_630 and m.save_pct == 86
    assert m.daily_spending_cents == 29_589 and m.short_cents == 0


def test_lo_de_hoy_ya_cuenta_y_no_se_repite_en_lo_que_viene():
    m = money_now(datos(), dt.date(2026, 11, 15), RATE)   # hoy entra el adelanto
    assert m.received_cents == 6_000_000                  # sueldo + adelanto
    assert all(e.kind != "advance" for e in m.upcoming)


def test_si_no_llega_a_fin_de_mes():
    # Una compra grande el 9 deja la plata en rojo
    m = money_now(datos([gasto(5_000_000, dt.date(2026, 11, 9))]), HOY, RATE)
    # 40.000 de sueldo - 15.000 de alquiler - 50.000 de la compra = -25.000
    assert m.current_cents == -2_500_000 and m.free_cents == -540_000
    assert m.can_save_cents == 0 and m.save_pct == 0
    assert m.short_cents == 540_000 + m.usual_spending_cents
    assert m.daily_spending_cents == 0


def test_cuenta_desde_el_ultimo_cobro():
    # Cobra el 25: el 10/11 vive del sueldo del 25/10, hasta el 24/11
    sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=6_000_000,
                    start_date=dt.date(2026, 1, 1), pay_day=25)
    m = money_now(finance.FinanceData(incomes=[sueldo]), HOY, RATE)
    assert (m.since, m.next_pay, m.period_end) == (dt.date(2026, 10, 25), dt.date(2026, 11, 25), dt.date(2026, 11, 24))
    assert m.current_cents == 6_000_000 and m.upcoming == []


def test_ingreso_unico_del_mes_suma():
    changa = Income(id=2, user_id=1, source="Changa", amount_cents=300_000, frequency="one_time",
                    start_date=dt.date(2026, 11, 3))
    data = datos()
    data.incomes.append(changa)
    assert money_now(data, HOY, RATE).received_cents == 4_300_000


def test_dia_31_en_meses_cortos():
    assert on_day(2027, 2, 31) == dt.date(2027, 2, 28)


# --- API ---------------------------------------------------------------------

def test_api_overview_trae_la_plata_de_hoy(client, auth):
    client.post("/api/incomes", json={"source": "Sueldo", "amount_cents": 5_000_000,
                                      "start_date": "2025-01-01"}, headers=auth)
    money = client.get("/api/finance/overview", headers=auth).json()["money"]
    assert money["received_cents"] == 5_000_000 and money["current_cents"] == 5_000_000


def test_api_adelanto_menor_que_el_total(client, auth):
    body = {"source": "Sueldo", "amount_cents": 5_000_000, "advance_cents": 5_000_000, "advance_day": 15}
    assert client.post("/api/incomes", json=body, headers=auth).status_code == 422
    body["advance_cents"] = 1_500_000
    inc = client.post("/api/incomes", json=body, headers=auth).json()
    assert inc["pay_day"] == 1 and inc["advance_day"] == 15
    # Bajar el total por debajo del adelanto tampoco se permite
    res = client.patch(f"/api/incomes/{inc['id']}", json={"amount_cents": 1_000_000}, headers=auth)
    assert res.status_code == 422


# --- Presupuesto real de una meta con fecha ----------------------------------

def caso_viaje(aguinaldo=True):
    """Cobra $ 60.000 el 30, alquiler el 5, gasta $ 9.000/mes; viaje de $ 15.000 el 6/12."""
    sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=6_000_000, start_date=dt.date(2026, 1, 1),
                    pay_day=30, aguinaldo_cents=3_000_000 if aguinaldo else None)
    data = datos()
    data.incomes = [sueldo]
    data.subscriptions = []
    viaje = Goal(id=1, user_id=1, name="Viaje", target_cents=1_500_000, saved_cents=0,
                 deadline=dt.date(2026, 12, 6))
    data.goals = [viaje]
    return data, viaje


def test_presupuesto_real_del_viaje():
    data, viaje = caso_viaje()
    b = goal_budget(data, viaje, dt.date(2026, 11, 2), RATE)
    por_dia = 900_000 * 12 / 365
    # Vive hasta el 29/12 (el 30 vuelve a cobrar)
    assert b.next_pay == dt.date(2026, 12, 30) and b.covers_until == dt.date(2026, 12, 29)
    # Hoy: el sueldo del 30/10. Para el 6/12: +sueldo 30/11, -2 alquileres, -34 días de gastos
    assert b.start_cents == 6_000_000
    assert b.on_deadline_cents == round(9_000_000 - 34 * por_dia)
    # El día más justo es el 17/12, justo antes del aguinaldo del 18
    assert b.lowest_date == dt.date(2026, 12, 17)
    assert b.cushion_cents == round(por_dia * 7)
    assert b.max_cents == round(9_000_000 - 45 * por_dia) - b.cushion_cents
    assert b.difference_cents == b.max_cents - 1_500_000 > 0     # le sobra presupuesto
    assert any(s.kind == "aguinaldo" and s.date == dt.date(2026, 12, 18) for s in b.steps)
    assert not b.short_before


def test_el_aguinaldo_agranda_el_presupuesto():
    con = goal_budget(*caso_viaje(aguinaldo=True), dt.date(2026, 11, 2), RATE)
    sin = goal_budget(*caso_viaje(aguinaldo=False), dt.date(2026, 11, 2), RATE)
    assert con.max_cents > sin.max_cents
    assert sin.lowest_date == dt.date(2026, 12, 29)   # sin aguinaldo, lo más justo es el final


def test_sin_fecha_o_muy_lejos_no_hay_presupuesto():
    data, viaje = caso_viaje()
    viaje.deadline = None
    assert goal_budget(data, viaje, HOY, RATE) is None
    viaje.deadline = dt.date(2029, 1, 1)
    assert goal_budget(data, viaje, HOY, RATE) is None


# --- Gastos puntuales, ajustes y tope por día ---------------------------------

def puntual(monto, fecha):
    return Expense(id=None, user_id=1, category="clothing", amount_cents=monto, kind="one_off", date=fecha)


def test_un_gasto_puntual_no_infla_el_promedio():
    data = datos()
    antes = finance.average_variable_expenses(data, HOY, RATE)
    data.expenses.append(puntual(4_000_000, dt.date(2026, 10, 20)))   # una campera de $ 40.000
    assert finance.average_variable_expenses(data, HOY, RATE) == antes
    # …pero sí cuenta como gasto de octubre
    assert finance.month_summary(data, 2026, 10, RATE).variable_expenses_cents == 900_000 + 4_000_000


def test_un_puntual_a_futuro_entra_en_la_simulacion():
    data, viaje = caso_viaje()
    sin = goal_budget(data, viaje, dt.date(2026, 11, 2), RATE)
    data.expenses.append(puntual(200_000, dt.date(2026, 11, 20)))     # cumpleaños el 20/11
    con = goal_budget(data, viaje, dt.date(2026, 11, 2), RATE)
    assert sin.max_cents - con.max_cents == 200_000
    assert any(s.kind == "one_off" and s.date == dt.date(2026, 11, 20) for s in con.steps)
    # y en el mes proyectado también aparece
    assert finance.month_summary(data, 2026, 11, RATE, projected_variable_cents=0).variable_expenses_cents == 200_000


def test_gastar_menos_por_dia_agranda_el_presupuesto():
    data, viaje = caso_viaje()
    normal = goal_budget(data, viaje, dt.date(2026, 11, 2), RATE)
    ajustado = goal_budget(data, viaje, dt.date(2026, 11, 2), RATE, daily_cents=10_000, cushion_days=0)
    assert ajustado.daily_cents == 10_000 and ajustado.cushion_cents == 0
    assert ajustado.max_cents > normal.max_cents
    assert ajustado.usual_daily_cents == normal.usual_daily_cents   # el promedio real no cambia


def test_tope_por_dia_para_llegar():
    data, viaje = caso_viaje()
    hoy = dt.date(2026, 11, 2)
    b = goal_budget(data, viaje, hoy, RATE)
    assert b.max_daily_cents > b.usual_daily_cents      # le sobra: puede gastar más que su promedio
    assert b.max_weekly_cents == b.max_daily_cents * 7
    # Gastando justo el tope (y sin colchón extra) todavía paga el viaje y le queda el colchón
    justo = goal_budget(data, viaje, hoy, RATE, daily_cents=b.max_daily_cents, cushion_days=0)
    assert justo.max_cents >= 1_500_000 + b.cushion_cents - 100
    # Un poco más por día y ya no llega con colchón
    pasado = goal_budget(data, viaje, hoy, RATE, daily_cents=b.max_daily_cents + 5_000, cushion_days=0)
    assert pasado.max_cents < 1_500_000 + b.cushion_cents


def test_serie_para_el_grafico():
    data, viaje = caso_viaje()
    b = goal_budget(data, viaje, dt.date(2026, 11, 2), RATE)
    assert b.series[0].date == dt.date(2026, 11, 2) and b.series[0].balance_cents == b.start_cents
    assert b.series[-1].date == b.covers_until
    assert b.goal_spend_cents == 1_500_000                  # le alcanza: el gráfico resta lo que cuesta
    dia_mas_justo = next(p for p in b.series if p.date == b.lowest_date)
    assert dia_mas_justo.balance_cents == b.lowest_cents


def test_detecta_gasto_inusual():
    comida = [Expense(id=i, user_id=1, category="food", amount_cents=50_000, kind="variable",
                      date=dt.date(2026, 11, i)) for i in range(1, 5)]
    data = finance.FinanceData(expenses=comida)
    grande = Expense(id=99, user_id=1, category="food", amount_cents=500_000, kind="variable", date=HOY)
    normal = Expense(id=98, user_id=1, category="food", amount_cents=120_000, kind="variable", date=HOY)
    assert finance.unusual_expense(data, grande, RATE).unusual
    check = finance.unusual_expense(data, normal, RATE)
    assert not check.unusual and check.typical_cents == 50_000


def test_api_ajustes_y_gasto_inusual(client, make_user):
    ana = make_user("ana@example.com")
    beto = make_user("beto@example.com")
    client.post("/api/incomes", json={"source": "Sueldo", "amount_cents": 5_000_000, "start_date": "2025-01-01"},
                headers=ana)
    m = client.get("/api/finance/money?daily_cents=10000", headers=ana).json()
    assert m["usual_spending_cents"] == 10_000 * m["days_left"]
    gasto = client.post("/api/expenses", json={"category": "food", "amount_cents": 5_000}, headers=ana).json()
    assert client.get(f"/api/finance/unusual/{gasto['id']}", headers=ana).json()["unusual"] is False
    assert client.get(f"/api/finance/unusual/{gasto['id']}", headers=beto).status_code == 404
    puntual = client.post("/api/expenses", json={"category": "clothing", "amount_cents": 400_000,
                                                 "kind": "one_off"}, headers=ana)
    assert puntual.status_code == 201 and puntual.json()["kind"] == "one_off"
    meta = client.post("/api/goals", json={"name": "Viaje", "target_cents": 100_000,
                                           "deadline": (dt.date.today() + dt.timedelta(days=40)).isoformat()},
                       headers=ana).json()
    plan = client.get(f"/api/finance/goals/{meta['id']}/plan?daily_cents=0&cushion_days=0", headers=ana).json()
    assert plan["budget"]["daily_cents"] == 0 and plan["budget"]["cushion_days"] == 0


# --- Lo que sobra de un mes pasa al siguiente ---------------------------------

def test_lo_que_sobra_de_un_mes_no_desaparece():
    def caso(joined):
        sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=6_000_000, start_date=dt.date(2026, 1, 1), pay_day=1)
        alquiler = Expense(id=1, user_id=1, category="housing", subcategory="rent", kind="fixed",
                           amount_cents=1_500_000, date=dt.date(2026, 1, 5))
        gastos = [gasto(1_000_000, dt.date(2026, 10, 20)), gasto(500_000, dt.date(2026, 11, 8))]
        return finance.FinanceData(incomes=[sueldo], expenses=[alquiler, *gastos], joined=joined)

    # Sin saber desde cuándo usa la app: solo el ciclo actual (1/11 a hoy)
    assert money_now(caso(None), HOY, RATE).current_cents == 6_000_000 - 1_500_000 - 500_000
    # Empezó a usar la app el 15/10: cuenta desde el cobro del 1/10 y arrastra lo que sobró
    m = money_now(caso(dt.date(2026, 10, 15)), HOY, RATE)
    assert m.tracked_from == dt.date(2026, 10, 1) and m.since == dt.date(2026, 11, 1)
    assert m.received_cents == 2 * 6_000_000
    assert m.current_cents == 12_000_000 - 2 * 1_500_000 - 1_000_000 - 500_000   # 7.500 de octubre siguen ahí


def test_sueldo_como_unica_vez_antes_de_empezar_cuenta():
    unico = Income(id=1, user_id=1, source="Sueldo", amount_cents=3_010_800, frequency="one_time",
                   start_date=dt.date(2026, 10, 30))
    data = finance.FinanceData(incomes=[unico], expenses=[gasto(400_000, dt.date(2026, 11, 5))],
                               joined=dt.date(2026, 11, 2))
    m = money_now(data, HOY, RATE)
    assert m.tracked_from == dt.date(2026, 10, 30)
    assert m.current_cents == 3_010_800 - 400_000          # ya no da negativo


# --- Plata que ya tenías e ingresos puntuales -------------------------------

def test_plata_que_ya_tenia_suma_hoy_pero_no_es_ingreso_del_mes():
    data = datos()
    sin_ella = money_now(data, HOY, RATE)
    # Con fecha vieja, a propósito: cuenta igual, sea cual sea el inicio del cálculo
    data.incomes.append(Income(id=2, user_id=1, source="Plata que ya tenía", amount_cents=10_000_000,
                               frequency="one_time", previous_money=True, start_date=dt.date(2026, 1, 1)))
    con_ella = money_now(data, HOY, RATE)
    assert con_ella.previous_cents == 10_000_000
    assert con_ella.current_cents == sin_ella.current_cents + 10_000_000
    assert con_ella.received_cents == sin_ella.received_cents
    assert finance.income_in_month(data.incomes[-1], 2026, 1, RATE) == 0


def test_plata_que_ya_tenia_en_dolares():
    data = datos()
    data.incomes.append(Income(id=2, user_id=1, source="Dólares guardados", amount_cents=100_000, currency="USD",
                               frequency="one_time", previous_money=True, start_date=HOY))
    assert money_now(data, HOY, RATE).previous_cents == 4_000_000


def test_ingreso_puntual_suma_hoy_y_es_ingreso_del_mes():
    data = datos()
    sin_el = money_now(data, HOY, RATE)
    data.incomes.append(Income(id=2, user_id=1, source="Changa", amount_cents=500_000,
                               frequency="one_time", start_date=dt.date(2026, 11, 9)))
    assert money_now(data, HOY, RATE).current_cents == sin_el.current_cents + 500_000
    assert finance.income_in_month(data.incomes[-1], 2026, 11, RATE) == 500_000


def test_la_api_guarda_la_plata_que_ya_tenia_como_unica_vez(client, auth):
    res = client.post("/api/incomes", headers=auth, json={
        "source": "Plata que ya tenía", "amount_cents": 1_000_000, "frequency": "monthly", "previous_money": True})
    assert res.status_code == 201
    assert res.json()["frequency"] == "one_time" and res.json()["previous_money"] is True
    assert client.get("/api/finance/overview", headers=auth).json()["money"]["previous_cents"] == 1_000_000
