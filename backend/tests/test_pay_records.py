"""Tests de cobros reales: lo anotado manda; lo que viene se estima con el último real."""

import datetime as dt

from backend.app.models import Commission, Income, PayRecord
from backend.app.services import finance
from backend.app.services.cashflow import money_now

HOY = dt.date(2026, 11, 2)
RATE = 40.0


def sueldo(**kw):
    """Sueldo que figura como $ 35.000 (adelanto de $ 5.040 el 15, el resto el 30)."""
    return Income(id=1, user_id=1, source="Sueldo", amount_cents=3_500_000, start_date=dt.date(2026, 1, 1),
                  pay_day=30, advance_cents=504_000, advance_day=15, **kw)


def cobro(fecha, monto, kind="pay"):
    return PayRecord(id=None, user_id=1, income_id=1, date=fecha, kind=kind, amount_cents=monto)


def test_sin_cobros_reales_usa_lo_del_ingreso():
    p = finance.pay_parts(finance.FinanceData(incomes=[sueldo()]), sueldo(), 2026, 10, RATE)
    assert (p.pay_date, p.pay_cents, p.status) == (dt.date(2026, 10, 30), 3_500_000 - 504_000, "planned")


def test_el_cobro_real_manda_y_el_proximo_se_estima_con_el():
    s = sueldo()
    data = finance.FinanceData(incomes=[s], pay_records=[cobro(dt.date(2026, 10, 30), 3_010_800)])
    octubre = finance.pay_parts(data, s, 2026, 10, RATE)
    assert (octubre.pay_cents, octubre.status) == (3_010_800, "real")
    noviembre = finance.pay_parts(data, s, 2026, 11, RATE)
    assert (noviembre.pay_cents, noviembre.status) == (3_010_800, "last")   # ≈ el último real
    # El mes suma adelanto + cobro
    assert finance.income_total_in_month(data, s, 2026, 11, RATE) == 504_000 + 3_010_800


def test_tu_plata_hoy_arranca_del_cobro_real():
    s = sueldo()
    data = finance.FinanceData(incomes=[s], pay_records=[cobro(dt.date(2026, 10, 30), 3_010_800)])
    m = money_now(data, HOY, RATE)
    assert m.since == dt.date(2026, 10, 30) and m.received_cents == 3_010_800
    # Lo que viene: el adelanto del 15; el cobro del 30 es el día del próximo cobro (fuera del período)
    assert [(e.date.day, e.amount_cents) for e in m.upcoming if e.amount_cents > 0] == [(15, 504_000)]


def test_cobro_real_en_otra_fecha_y_adelanto_real():
    s = sueldo()
    data = finance.FinanceData(incomes=[s], pay_records=[
        cobro(dt.date(2026, 10, 29), 3_000_000),                    # cobró el 29, no el 30
        cobro(dt.date(2026, 10, 15), 500_000, kind="advance"),
    ])
    p = finance.pay_parts(data, s, 2026, 10, RATE)
    assert (p.pay_date, p.advance_cents) == (dt.date(2026, 10, 29), 500_000)
    assert money_now(data, HOY, RATE).since == dt.date(2026, 10, 29)


def test_con_cobro_real_las_comisiones_ya_vienen_adentro():
    s = sueldo(commission_floor_cents=241_200)
    semana = Commission(id=None, user_id=1, week_start=dt.date(2026, 10, 26), min_cents=1_125_600, max_cents=1_527_600)
    data = finance.FinanceData(incomes=[s], commissions=[semana], pay_records=[cobro(dt.date(2026, 10, 30), 3_010_800)])
    assert finance.commissions_in_month(data, 2026, 10) == 0                 # ya está en el real
    assert finance.commissions_in_month(data, 2026, 11) > 0                  # noviembre: todavía estimado
    # Con comisiones, el próximo cobro NO se estima con el último real: base + rangos
    assert finance.pay_parts(data, s, 2026, 11, RATE).status == "planned"


# --- API ---------------------------------------------------------------------

def test_api_cobros_reales(client, make_user):
    ana = make_user("ana@example.com")
    beto = make_user("beto@example.com")
    inc = client.post("/api/incomes", json={"source": "Sueldo", "amount_cents": 3_500_000, "pay_day": 30,
                                            "start_date": "2026-01-01"}, headers=ana).json()
    r = client.post("/api/pay-records", json={"income_id": inc["id"], "date": "2026-10-30",
                                              "amount_cents": 3_010_800}, headers=ana)
    assert r.status_code == 201 and r.json()["kind"] == "pay"
    # Beto no puede anotar cobros en el ingreso de Ana, ni verlos
    assert client.post("/api/pay-records", json={"income_id": inc["id"], "date": "2026-10-30",
                                                 "amount_cents": 1}, headers=beto).status_code == 404
    assert client.get(f"/api/pay-records/{r.json()['id']}", headers=beto).status_code == 404
    # Borrar el ingreso se lleva sus cobros (si no, la base no lo dejaría)
    assert client.delete(f"/api/incomes/{inc['id']}", headers=ana).status_code == 204
    assert client.get("/api/pay-records", headers=ana).json() == []
