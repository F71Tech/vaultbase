"""Tests de "Tu plata hoy": saldo actual, cobros con adelanto y cuánto ahorrar."""

import datetime as dt

from backend.app.models import Expense, Income, Subscription
from backend.app.services import finance
from backend.app.services.cashflow import money_now, on_day

HOY = dt.date(2026, 11, 10)
RATE = 40.0
UTC = dt.timezone.utc
# Cargó su saldo el 3/11 a las 12:00 de Uruguay (15:00 UTC)
SALDO_AT = dt.datetime(2026, 11, 3, 15, 0, tzinfo=UTC)


def datos(extra_gastos=()):
    sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=6_000_000, start_date=dt.date(2026, 1, 1),
                    pay_day=1, advance_cents=2_000_000, advance_day=15)
    alquiler = Expense(id=1, user_id=1, category="housing", subcategory="rent", kind="fixed",
                       amount_cents=1_500_000, date=dt.date(2026, 1, 5))
    spotify = Subscription(id=1, user_id=1, name="Spotify", amount_cents=1_000, currency="USD",
                           billing_day=20, created_at=dt.datetime(2026, 1, 1, tzinfo=UTC))
    # Historial: $ 9.000 por mes de gastos variables (agosto a octubre)
    historial = [Expense(id=None, user_id=1, category="food", amount_cents=900_000, kind="variable",
                         date=dt.date(2026, m, 10), created_at=dt.datetime(2026, m, 10, tzinfo=UTC))
                 for m in (8, 9, 10)]
    return finance.FinanceData(incomes=[sueldo], expenses=[alquiler, *historial, *extra_gastos],
                               subscriptions=[spotify])


def gasto(monto, fecha, anotado):
    return Expense(id=None, user_id=1, category="food", amount_cents=monto, kind="variable",
                   date=fecha, created_at=anotado)


def test_saldo_de_hoy_y_cuanto_ahorrar():
    extra = [
        gasto(50_000, dt.date(2026, 11, 8), dt.datetime(2026, 11, 8, 20, tzinfo=UTC)),   # cuenta
        gasto(70_000, dt.date(2026, 11, 2), dt.datetime(2026, 11, 9, 20, tzinfo=UTC)),   # de antes del saldo
        gasto(90_000, dt.date(2026, 11, 3), dt.datetime(2026, 11, 3, 13, tzinfo=UTC)),   # ya estaba en el saldo
    ]
    m = money_now(datos(extra), 3_000_000, SALDO_AT, HOY, RATE)
    # 30.000 - alquiler del 5 (15.000) - gasto del 8 (500)
    assert m.since_spent_cents == 1_550_000 and m.since_income_cents == 0
    assert m.current_cents == 1_450_000
    # Hasta fin de mes: entra el adelanto (20.000) el 15 y sale Spotify (US$ 10 = 400) el 20
    assert [(e.date.day, e.kind) for e in m.upcoming] == [(15, "advance"), (20, "subscription")]
    assert m.incoming_cents == 2_000_000 and m.bills_cents == 40_000
    # Quedan 21 días: a tu ritmo (9.000/mes) gastás 6.300
    assert m.days_left == 21 and m.usual_spending_cents == 630_000
    assert m.free_cents == 3_410_000
    assert m.can_save_cents == 2_780_000 and m.save_pct == 82
    assert m.daily_spending_cents == 30_000 and m.short_cents == 0


def test_cobros_desde_el_saldo_se_suman():
    # Saldo cargado el 14: el adelanto del 15 ya entró
    m = money_now(datos(), 100_000, dt.datetime(2026, 11, 14, 15, tzinfo=UTC), dt.date(2026, 11, 16), RATE)
    assert m.since_income_cents == 2_000_000 and m.current_cents == 2_100_000


def test_si_no_llega_a_fin_de_mes():
    # Cuenta en rojo (-10.000): -10.000 - alquiler 15.000 + adelanto 20.000 = -5.000
    m = money_now(datos(), -1_000_000, SALDO_AT, dt.date(2026, 11, 16), RATE)
    assert m.current_cents == -500_000 and m.free_cents == -540_000
    assert m.can_save_cents == 0 and m.save_pct == 0
    assert m.short_cents == 540_000 + m.usual_spending_cents
    assert m.daily_spending_cents == 0


def test_sin_saldo_igual_muestra_lo_que_viene():
    m = money_now(datos(), None, None, HOY, RATE)
    assert not m.has_balance and m.current_cents is None
    assert len(m.upcoming) == 2


def test_sueldo_sin_adelanto_entra_entero_el_dia_de_cobro():
    sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=6_000_000,
                    start_date=dt.date(2026, 1, 1), pay_day=25)
    m = money_now(finance.FinanceData(incomes=[sueldo]), 0, SALDO_AT, HOY, RATE)
    assert [(e.date.day, e.amount_cents) for e in m.upcoming] == [(25, 6_000_000)]


def test_dia_31_en_meses_cortos():
    assert on_day(2027, 2, 31) == dt.date(2027, 2, 28)


# --- API ---------------------------------------------------------------------

def test_api_saldo_y_adelanto(client, auth):
    me = client.patch("/api/users/me", json={"balance_cents": 1_234_500}, headers=auth).json()
    assert me["balance_cents"] == 1_234_500 and me["balance_at"] is not None
    ov = client.get("/api/finance/overview", headers=auth).json()
    assert ov["money"]["has_balance"] and ov["money"]["current_cents"] == 1_234_500
    # null = dejar de usarlo
    me = client.patch("/api/users/me", json={"balance_cents": None}, headers=auth).json()
    assert me["balance_cents"] is None and me["balance_at"] is None


def test_api_adelanto_menor_que_el_total(client, auth):
    body = {"source": "Sueldo", "amount_cents": 5_000_000, "advance_cents": 5_000_000, "advance_day": 15}
    assert client.post("/api/incomes", json=body, headers=auth).status_code == 422
    body["advance_cents"] = 1_500_000
    inc = client.post("/api/incomes", json=body, headers=auth).json()
    assert inc["pay_day"] == 1 and inc["advance_day"] == 15
    # Bajar el total por debajo del adelanto tampoco se permite
    res = client.patch(f"/api/incomes/{inc['id']}", json={"amount_cents": 1_000_000}, headers=auth)
    assert res.status_code == 422
