"""Tests de sueldo variable: comisiones semanales con rango y bono mínimo."""

import datetime as dt

from backend.app.models import Commission, Goal, Income
from backend.app.services import finance
from backend.app.services.cashflow import goal_budget, money_now

HOY = dt.date(2026, 11, 2)   # lunes
RATE = 40.0


def caso(*comisiones):
    """Sueldo base $ 28.000 el 30, bono mínimo de $ 3.000 por semana."""
    sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=2_800_000, start_date=dt.date(2026, 1, 1),
                    pay_day=30, commission_floor_cents=300_000)
    return finance.FinanceData(incomes=[sueldo], commissions=list(comisiones))


def semana(lunes, minimo, maximo, real=None):
    return Commission(id=None, user_id=1, week_start=lunes, min_cents=minimo, max_cents=maximo, actual_cents=real)


def test_semanas_que_se_cobran_en_noviembre():
    # Domingos de noviembre 2026: 1, 8, 15, 22 y 29 -> 5 semanas se cobran el 30/11
    assert len(finance.sundays_in_month(2026, 11)) == 5


def test_rango_y_bono_minimo():
    data = caso(semana(dt.date(2026, 10, 26), 1_400_000, 1_900_000))   # la semana del 356%
    # Prudente: 14.000 + 4 semanas sin anotar a 3.000 = 26.000
    assert finance.commissions_in_month(data, 2026, 11) == 2_600_000
    # Optimista: 19.000 + 4 x 3.000 = 31.000
    assert finance.commissions_in_month(data, 2026, 11, high=True) == 3_100_000


def test_si_no_llega_cobra_el_bono():
    data = caso(semana(dt.date(2026, 11, 2), 100_000, 250_000))          # semana floja
    assert finance.commissions_in_month(data, 2026, 11) == 5 * 300_000


def test_el_monto_real_reemplaza_al_rango():
    data = caso(semana(dt.date(2026, 10, 26), 1_400_000, 1_900_000, real=1_650_000))
    assert finance.commissions_in_month(data, 2026, 11) == finance.commissions_in_month(data, 2026, 11, high=True)
    assert finance.commissions_in_month(data, 2026, 11) == 1_650_000 + 4 * 300_000


def test_el_mes_suma_base_y_comisiones():
    data = caso(semana(dt.date(2026, 10, 26), 1_400_000, 1_900_000))
    assert finance.month_summary(data, 2026, 11, RATE).income_cents == 2_800_000 + 2_600_000


def test_presupuesto_con_rango():
    data = caso(semana(dt.date(2026, 10, 26), 1_400_000, 1_900_000))
    viaje = Goal(id=1, user_id=1, name="Viaje", target_cents=1_500_000, saved_cents=0, deadline=dt.date(2026, 12, 6))
    data.goals = [viaje]
    b = goal_budget(data, viaje, HOY, RATE)
    assert b.has_commissions
    # Las comisiones del 30/11 entran antes del viaje: si vienen altas, hay $ 5.000 más
    assert b.budget_high_cents - b.budget_cents == 500_000
    assert b.max_daily_high_cents >= b.max_daily_cents
    paso = next(s for s in b.steps if s.kind == "commission")
    assert paso.date == dt.date(2026, 11, 30) and (paso.amount_cents, paso.amount_high_cents) == (2_600_000, 3_100_000)


def test_sin_comisiones_no_cambia_nada():
    sueldo = Income(id=1, user_id=1, source="Sueldo", amount_cents=2_800_000, start_date=dt.date(2026, 1, 1), pay_day=30)
    data = finance.FinanceData(incomes=[sueldo])
    assert finance.commissions_in_month(data, 2026, 11) == 0
    assert not money_now(data, HOY, RATE).has_commissions


# --- API ---------------------------------------------------------------------

def test_api_comisiones(client, make_user):
    ana = make_user("ana@example.com")
    beto = make_user("beto@example.com")
    # El miércoles 28/10 se guarda como el lunes de esa semana (26/10)
    c = client.post("/api/commissions", json={"week_start": "2026-10-28", "min_cents": 1_400_000,
                                              "max_cents": 1_900_000, "note": "356% de la meta"}, headers=ana)
    assert c.status_code == 201 and c.json()["week_start"] == "2026-10-26"
    cid = c.json()["id"]
    mal = client.post("/api/commissions", json={"week_start": "2026-11-02", "min_cents": 5, "max_cents": 1}, headers=ana)
    assert mal.status_code == 422
    assert client.patch(f"/api/commissions/{cid}", json={"min_cents": 9_999_999}, headers=ana).status_code == 422
    assert client.patch(f"/api/commissions/{cid}", json={"actual_cents": 1_650_000}, headers=ana).json()["actual_cents"] == 1_650_000
    assert client.get(f"/api/commissions/{cid}", headers=beto).status_code == 404
    assert len(client.get("/api/commissions", headers=ana).json()) == 1
    # Borrar la cuenta borra también sus comisiones
    assert client.delete("/api/users/me", headers=ana).status_code == 204
