"""Tests del aguinaldo dentro de los cálculos y del simulador."""

import datetime as dt

from backend.app.models import Goal, Income
from backend.app.services import finance
from backend.app.services.simulator import InstallmentOption, simulate_purchase

RATE = 40.0


def sueldo(start=dt.date(2025, 1, 1), end=None):
    return Income(id=1, user_id=1, source="Sueldo", amount_cents=5_226_000, nominal_cents=6_500_000,
                  aguinaldo_cents=2_612_250, start_date=start, end_date=end)


def test_aguinaldo_solo_en_junio_y_diciembre():
    s = sueldo()
    assert finance.aguinaldo_in_month(s, 2026, 6, RATE) == 2_612_250
    assert finance.aguinaldo_in_month(s, 2026, 12, RATE) == 2_612_250
    assert finance.aguinaldo_in_month(s, 2026, 11, RATE) == 0


def test_aguinaldo_proporcional_si_empezo_a_mitad_de_semestre():
    # Empezó en septiembre: de jun-nov trabajó 3 de 6 meses -> medio aguinaldo / 2
    s = sueldo(start=dt.date(2026, 9, 1))
    assert finance.aguinaldo_in_month(s, 2026, 12, RATE) == round(2_612_250 * 3 / 6)


def test_aguinaldo_entra_en_el_mes_y_no_en_el_ahorro_mensual():
    data = finance.FinanceData(incomes=[sueldo()])
    diciembre = finance.month_summary(data, 2026, 12, RATE)
    assert diciembre.aguinaldo_cents == 2_612_250
    assert diciembre.income_cents == 5_226_000 + 2_612_250
    capacidad = finance.savings_capacity(data, dt.date(2026, 12, 10), RATE)
    assert capacidad.recurring_income_cents == 5_226_000  # sin aguinaldo


def test_proximo_aguinaldo():
    data = finance.FinanceData(incomes=[sueldo()])
    assert finance.next_aguinaldo(data, dt.date(2026, 11, 15), RATE) == (1, 2_612_250)
    assert finance.next_aguinaldo(data, dt.date(2026, 7, 1), RATE) == (5, 2_612_250)
    assert finance.next_aguinaldo(finance.FinanceData(), dt.date(2026, 7, 1), RATE) is None


def test_simulador_recomienda_esperar_al_aguinaldo():
    # Compra de $ 20.000 con ahorro de $ 10.000/mes y una meta en curso:
    # las cuotas atrasan la meta; el aguinaldo de diciembre (26.122) la cubre entera.
    meta = Goal(id=1, user_id=1, name="Viaje", target_cents=6_000_000, saved_cents=0)
    r = simulate_purchase(2_000_000, 1_000_000, [meta], 0, dt.date(2026, 11, 15),
                          [InstallmentOption(count=3)], aguinaldo=(1, 2_612_250))
    s = {x.key: x for x in r.strategies}
    assert s["wait_aguinaldo"].goal_delays[0].delay_months == 0
    assert s["installments_3"].goal_delays[0].delay_months > 0
    assert r.recommended_key == "wait_aguinaldo"
    assert "aguinaldo" in r.recommendation


def test_endpoint_calculadora_publica(client):
    res = client.post("/api/salary/calculate", json={"nominal_cents": 6_500_000})
    assert res.status_code == 200
    body = res.json()
    assert body["monthly"]["net_cents"] == 5_226_000
    assert body["aguinaldo"]["nominal_cents"] == 3_250_000
    assert client.get("/api/salary/params").json()["bpc_cents"] == 686_400


def test_ingreso_sueldo_guarda_nominal_y_aguinaldo(client, auth):
    res = client.post("/api/incomes", json={
        "source": "Sueldo", "amount_cents": 5_226_000, "nominal_cents": 6_500_000,
        "aguinaldo_cents": 2_612_250, "start_date": "2025-01-01"}, headers=auth)
    assert res.status_code == 201 and res.json()["aguinaldo_cents"] == 2_612_250
    year = client.get("/api/finance/year?year=2026", headers=auth).json()
    assert year["months"][11]["aguinaldo_cents"] == 2_612_250
