"""
Tests de la calculadora de sueldo. Los resultados esperados están calculados
A MANO con los valores oficiales 2026 (BPC $ 6.864), para que el test
compruebe la lógica y no solo "que el código dé lo que da".
"""

import pytest

from backend.app.services.salary import (
    SalaryInput, calculate, fonasa_rate, nominal_for_net, progressive_tax,
)

BPC = 686_400


def test_escala_progresional_por_franjas():
    assert progressive_tax(7 * BPC) == 0                       # hasta 7 BPC: 0 %
    # $ 60.000: (60.000 - 48.048) x 10 % = $ 1.195,20
    assert progressive_tax(6_000_000) == pytest.approx(119_520)
    # $ 120.000: 10 % de 7-10 BPC + 15 % de 10-15 BPC + 24 % del resto
    esperado = 3 * BPC * 0.10 + 5 * BPC * 0.15 + (12_000_000 - 15 * BPC) * 0.24
    assert progressive_tax(12_000_000) == pytest.approx(esperado)


def test_tasas_fonasa_oficiales():
    bajo, alto = 2 * BPC, 10 * BPC
    assert fonasa_rate(bajo, spouse=False, has_children=False) == 0.03
    assert fonasa_rate(alto, spouse=False, has_children=False) == 0.045
    assert fonasa_rate(alto, spouse=False, has_children=True) == 0.06
    assert fonasa_rate(alto, spouse=True, has_children=False) == 0.065
    assert fonasa_rate(alto, spouse=True, has_children=True) == 0.08
    assert fonasa_rate(bajo, spouse=True, has_children=True) == 0.05


def test_sueldo_65000_sin_hijos():
    # Aportes: BPS 9.750 + FONASA 4,5 % 2.925 + FRL 65 = 12.740
    # IRPF: (65.000 - 48.048) x 10 % = 1.695,20; deducciones 12.740 x 14 % = 1.783,60 -> 0
    r = calculate(SalaryInput(nominal_cents=6_500_000)).monthly
    assert (r.pension_cents, r.fonasa_cents, r.frl_cents) == (975_000, 292_500, 6_500)
    assert r.irpf_cents == 0
    assert r.net_cents == 5_226_000  # $ 52.260


def test_sueldo_alto_usa_incremento_6_y_deduccion_8():
    # $ 120.000 > 10 BPC -> base 127.200; > 15 BPC -> deducciones al 8 %
    r = calculate(SalaryInput(nominal_cents=12_000_000)).monthly
    assert r.irpf_base_cents == 12_720_000
    assert r.deduction_rate == 0.08
    aportes = 1_800_000 + 540_000 + 12_000            # 15 % + 4,5 % + 0,1 %
    bruto = progressive_tax(12_720_000)
    assert r.irpf_cents == round(bruto - aportes * 0.08)
    assert r.net_cents == 12_000_000 - aportes - r.irpf_cents


def test_hijos_bajan_el_irpf():
    sin = calculate(SalaryInput(nominal_cents=12_000_000)).monthly
    con = calculate(SalaryInput(nominal_cents=12_000_000, children=2)).monthly
    assert con.irpf_cents < sin.irpf_cents
    # Pero FONASA sube (6 % con hijos)
    assert con.fonasa_rate == 0.06


def test_deduccion_compartida_al_50():
    entera = calculate(SalaryInput(nominal_cents=12_000_000, children=1)).monthly
    mitad = calculate(SalaryInput(nominal_cents=12_000_000, children=1, children_share_pct=50)).monthly
    # La deducción por hijo es 11.440 x 8 % = 915,20; a la mitad, el IRPF sube 457,60
    assert mitad.irpf_cents - entera.irpf_cents == pytest.approx(45_760, abs=1)


def test_inverso_liquido_a_nominal():
    data = SalaryInput(net_cents=8_000_000, children=1)
    nominal = nominal_for_net(8_000_000, data)
    r = calculate(SalaryInput(nominal_cents=nominal, children=1)).monthly
    assert r.net_cents >= 8_000_000
    # Un centésimo menos de nominal ya no alcanza: es el mínimo exacto
    assert calculate(SalaryInput(nominal_cents=nominal - 1, children=1)).monthly.net_cents < 8_000_000


def test_aguinaldo_es_medio_sueldo_con_aportes():
    r = calculate(SalaryInput(nominal_cents=6_500_000))
    assert r.aguinaldo.nominal_cents == 3_250_000
    # 15 % + 4,5 % + 0,1 % de 32.500
    assert r.aguinaldo.net_cents == 3_250_000 - (487_500 + 146_250 + 3_250)
    assert r.annual_net_cents == r.monthly.net_cents * 12 + r.aguinaldo.net_cents * 2


def test_hay_que_mandar_nominal_o_liquido():
    with pytest.raises(ValueError):
        SalaryInput()
    with pytest.raises(ValueError):
        SalaryInput(nominal_cents=1, net_cents=1)
