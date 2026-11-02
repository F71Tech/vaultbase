"""Tests de la cotización automática del dólar (sin internet: fuentes falsas)."""

import datetime as dt

import httpx
import pytest

from backend.app.models import ExchangeRate
from backend.app.services import exchange

# Respuesta real del BCU (recortada), para probar que la sabemos leer
BCU_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>
<wsbcucotizaciones.ExecuteResponse xmlns="Cotiza"><Salida xmlns="Cotiza"><datoscotizaciones>
<datoscotizaciones.dato xmlns="Cotiza"><Fecha>2026-10-29</Fecha><TCV>40.191000</TCV></datoscotizaciones.dato>
<datoscotizaciones.dato xmlns="Cotiza"><Fecha>2026-10-30</Fecha><TCV>40.188000</TCV></datoscotizaciones.dato>
</datoscotizaciones></Salida></wsbcucotizaciones.ExecuteResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>"""


def test_lee_la_respuesta_del_bcu():
    quote = exchange.parse_bcu_response(BCU_XML)
    assert quote.rate == 40.188  # el día más reciente
    assert quote.rate_date == dt.date(2026, 10, 30)


def test_usa_la_cache_y_no_vuelve_a_consultar(session, monkeypatch):
    llamadas = []

    def contar(until):
        llamadas.append(until)
        return exchange.RateQuote(rate=41.0, rate_date=until, source="BCU")

    monkeypatch.setattr(exchange, "fetch_bcu", contar)
    assert exchange.get_current_rate(session).rate == 41.0
    assert exchange.get_current_rate(session).rate == 41.0
    assert len(llamadas) == 1  # la segunda vez salió de la caché


def test_si_el_bcu_falla_usa_el_respaldo(session, monkeypatch):
    def bcu_caido(until):
        raise httpx.ConnectError("sin conexión")

    monkeypatch.setattr(exchange, "fetch_bcu", bcu_caido)
    monkeypatch.setattr(
        exchange, "fetch_open_er",
        lambda until: exchange.RateQuote(rate=40.5, rate_date=until, source="open.er-api.com"),
    )
    row = exchange.get_current_rate(session)
    assert (row.rate, row.source) == (40.5, "open.er-api.com")


def test_si_todo_falla_usa_el_ultimo_valor_guardado(session, monkeypatch):
    viejo = ExchangeRate(
        rate=39.9, rate_date=dt.date(2026, 10, 1), source="BCU",
        fetched_at=dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc),
    )
    session.add(viejo)
    session.commit()
    monkeypatch.setattr(exchange, "fetch_bcu", lambda until: None)
    assert exchange.get_current_rate(session).rate == 39.9


def test_sin_nada_disponible_lanza_error(session, monkeypatch):
    monkeypatch.setattr(exchange, "fetch_bcu", lambda until: None)
    with pytest.raises(exchange.RateUnavailable):
        exchange.get_current_rate(session)


def test_gasto_en_dolares_congela_la_cotizacion(client, auth):
    res = client.post(
        "/api/expenses",
        json={"category": "tech", "amount_cents": 2000, "currency": "USD", "date": "2026-03-10"},
        headers=auth,
    )
    assert res.json()["exchange_rate"] == 40.0  # la del día del gasto (fuente falsa)


def test_endpoint_publico_de_cotizacion(client):
    res = client.get("/api/exchange-rate")
    assert res.status_code == 200
    assert res.json()["rate"] == 40.0 and res.json()["source"] == "BCU"
