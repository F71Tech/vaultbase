"""Tests del ticket de alimentación: otra tarjeta que solo sirve para comida."""

import datetime as dt

from backend.app.models import Expense, Income
from backend.app.services import finance
from backend.app.services.cashflow import daily_spending, money_now

HOY = dt.date(2026, 11, 10)
RATE = 40.0
TICKET = 492_500   # $ 4.925


def gasto(monto, fecha, category="food", con_ticket=None):
    return Expense(id=None, user_id=1, category=category, amount_cents=monto, kind="variable",
                   date=fecha, paid_with_ticket=con_ticket)


def datos(*extra):
    sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=6_000_000, start_date=dt.date(2026, 1, 1), pay_day=1)
    ticket = Income(id=2, user_id=1, source="Ticket alimentación", amount_cents=TICKET,
                    start_date=dt.date(2026, 1, 1), pay_day=1, food_only=True)
    # Historial: $ 6.000 de comida y $ 3.000 de otras cosas por mes (agosto a octubre)
    historial = [gasto(600_000, dt.date(2026, m, 10)) for m in (8, 9, 10)]
    historial += [gasto(300_000, dt.date(2026, m, 12), category="leisure") for m in (8, 9, 10)]
    return finance.FinanceData(incomes=[sueldo, ticket], expenses=[*historial, *extra])


def test_el_ticket_no_es_plata_libre_pero_cubre_comida():
    cap = finance.savings_capacity(datos(), HOY, RATE)
    assert cap.recurring_income_cents == 6_000_000          # el ticket no suma a tu plata…
    assert cap.food_ticket_cents == TICKET
    assert cap.avg_variable_expenses_cents == 900_000 - TICKET  # …pero la comida que cubre no te la resta
    assert cap.monthly_savings_cents == 6_000_000 - (900_000 - TICKET)


def test_si_comes_menos_que_el_ticket_lo_que_sobra_no_se_ahorra():
    data = datos()
    data.expenses = [e for e in data.expenses if e.category != "food"] + [
        gasto(200_000, dt.date(2026, m, 10)) for m in (8, 9, 10)]   # solo $ 2.000 de comida
    cap = finance.savings_capacity(data, HOY, RATE)
    assert cap.avg_variable_expenses_cents == 500_000 - 200_000     # cubre $ 2.000, no los $ 4.925


def test_la_comida_se_paga_primero_con_el_ticket():
    data = datos(gasto(200_000, dt.date(2026, 11, 5)), gasto(400_000, dt.date(2026, 11, 8)),
                 gasto(50_000, dt.date(2026, 11, 9), con_ticket=False),          # "con mi plata"
                 gasto(100_000, dt.date(2026, 11, 9), category="transport"))
    m = money_now(data, HOY, RATE)
    assert m.received_cents == 6_000_000                     # el ticket no entra como plata
    assert m.ticket_used_cents == TICKET and m.ticket_left_cents == 0
    # Gastaste 7.500 en total; 4.925 salieron del ticket
    assert m.spent_cents == 750_000 - TICKET
    assert m.current_cents == 6_000_000 - (750_000 - TICKET)
    assert all(e.label != "Ticket alimentación" for e in m.upcoming)


def test_lo_marcado_con_ticket_cuenta_primero():
    data = datos(gasto(100_000, dt.date(2026, 11, 3), con_ticket=True), gasto(450_000, dt.date(2026, 11, 4)))
    m = money_now(data, HOY, RATE)
    assert m.ticket_used_cents == TICKET                     # 1.000 marcado + 3.925 automático
    assert m.spent_cents == 550_000 - TICKET


def test_gasto_diario_de_tu_bolsillo():
    assert daily_spending(datos(), HOY, RATE) == (900_000 - TICKET) * 12 / 365


def test_presupuesto_de_comida_suma_el_ticket():
    data = datos(gasto(300_000, dt.date(2026, 11, 5)))
    cap = finance.savings_capacity(data, HOY, RATE)
    f = finance.food_budget(data, cap, 30, HOY, RATE)
    assert f.ticket_cents == TICKET
    assert f.monthly_budget_cents == cap.disposable_income_cents * 30 // 100 + TICKET
    assert (f.ticket_used_cents, f.ticket_left_cents) == (300_000, TICKET - 300_000)


def test_sin_ticket_no_cambia_nada():
    data = datos()
    data.incomes = data.incomes[:1]
    assert daily_spending(data, HOY, RATE) == 900_000 * 12 / 365
    assert money_now(data, HOY, RATE).ticket_cents == 0


def test_api_ticket(client, auth):
    t = client.post("/api/incomes", json={"source": "Ticket alimentación", "amount_cents": TICKET,
                                          "start_date": "2026-01-01", "food_only": True}, headers=auth)
    assert t.status_code == 201 and t.json()["food_only"] is True
    g = client.post("/api/expenses", json={"category": "food", "amount_cents": 50_000,
                                           "paid_with_ticket": False}, headers=auth)
    assert g.json()["paid_with_ticket"] is False
    # Volver a "automático"
    assert client.patch(f"/api/expenses/{g.json()['id']}", json={"paid_with_ticket": None},
                        headers=auth).json()["paid_with_ticket"] is None
    ov = client.get("/api/finance/overview", headers=auth).json()
    assert ov["capacity"]["food_ticket_cents"] == TICKET and ov["money"]["ticket_cents"] == TICKET
