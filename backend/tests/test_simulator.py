"""Tests del simulador de compras."""

import datetime as dt

from backend.app.models import Goal
from backend.app.services.simulator import (
    InstallmentOption, french_installment, installment_schedule, save_first_schedule,
    simulate_purchase,
)

HOY = dt.date(2026, 11, 15)
CUOTAS = [InstallmentOption(count=n) for n in (3, 6, 12)]


def meta(**kw):
    return Goal(id=1, user_id=1, name="Viaje", target_cents=1_200_000, saved_cents=0, **kw)


def simular(precio, ahorro, metas=None, cuotas=CUOTAS):
    return simulate_purchase(precio, ahorro, metas or [], 0, HOY, cuotas)


def por_clave(resultado):
    return {s.key: s for s in resultado.strategies}


def test_cuota_sistema_frances():
    assert french_installment(120_000, 12, 0) == 10_000
    # 40% anual -> 2,84% mensual -> cuota de $ 119,44 (calculado a mano)
    assert french_installment(120_000, 12, 40) == 11_944


def test_cuotas_sin_interes_suman_el_precio_exacto():
    schedule = installment_schedule(500_000, 6, 0)
    assert sum(schedule) == 500_000
    assert schedule == [83_334, 83_334, 83_333, 83_333, 83_333, 83_333]


def test_calendario_de_ahorrar_primero():
    assert save_first_schedule(250, 100) == [100, 100, 50]


def test_si_alcanza_el_ahorro_recomienda_contado():
    r = simular(50_000, 100_000)
    assert r.recommended_key == "cash"


def test_compra_cara_recomienda_cuotas_sin_interes():
    # Ahorro 100.000/mes; compra de 500.000: al contado deja el mes en negativo
    r = simular(500_000, 100_000)
    s = por_clave(r)
    assert s["cash"].negative_months == 1
    assert s["installments_6"].negative_months == 0
    assert r.recommended_key == "installments_6"  # 3 cuotas = 166.667 > 100.000 (negativo)


def test_si_las_cuotas_tienen_interes_conviene_ahorrar_primero():
    cuotas = [InstallmentOption(count=12, annual_rate_pct=60)]
    r = simular(500_000, 100_000, cuotas=cuotas)
    s = por_clave(r)
    assert s["installments_12_60"].extra_cost_cents > 0
    assert r.recommended_key == "save_first"
    assert s["save_first"].purchase_in_months == 4  # 5 meses de ahorro


def test_la_compra_atrasa_las_metas():
    # Meta de 1.200.000 con 100.000/mes = 12 meses. Comprar 300.000 la atrasa 3.
    r = simular(300_000, 100_000, metas=[meta()])
    for strategy in r.strategies:
        if strategy.negative_months == 0:
            assert strategy.goal_delays[0].months_without_purchase == 12
            assert strategy.goal_delays[0].delay_months == 3


def test_prefiere_la_opcion_que_menos_atrasa_las_metas():
    # Meta cercana (3 meses). Pagar en más cuotas le quita menos ahorro mientras
    # se completa, así que la atrasa menos -> gana sobre menos cuotas.
    # Ahorro 200.000/mes, meta de 600.000 (3 meses), compra de 360.000:
    #   3 cuotas de 120.000 -> la meta recibe 80.000/mes  -> 5 meses (+2)
    #  12 cuotas de  30.000 -> la meta recibe 170.000/mes -> 4 meses (+1)
    cercana = Goal(id=1, user_id=1, name="Viaje", target_cents=600_000, saved_cents=0)
    r = simular(360_000, 200_000, metas=[cercana])
    s = por_clave(r)
    assert s["installments_12"].goal_delays[0].delay_months < s["installments_3"].goal_delays[0].delay_months
    assert r.recommended_key == "installments_12"


def test_sin_capacidad_de_ahorro_avisa():
    r = simular(100_000, 0)
    assert "save_first" not in por_clave(r)
    assert "gastos igualan o superan" in r.recommendation
