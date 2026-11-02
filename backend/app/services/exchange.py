"""
Cotización automática del dólar.

Orden de fuentes:
  1) BCU (Banco Central del Uruguay): cotización oficial, dólar billete.
     Publica solo días hábiles, así que pedimos los últimos 10 días y
     usamos el más reciente.
  2) open.er-api.com: API pública gratuita, como respaldo si el BCU falla.
  3) El último valor guardado: si todo falla, la app sigue funcionando.

Caché: guardamos cada cotización en la tabla exchange_rates. Si la última
consulta tiene menos de CACHE_HOURS horas, la reutilizamos sin salir a
internet. Así todos los usuarios comparten el mismo valor y no saturamos
a las fuentes con pedidos.
"""

import datetime as dt
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx
from sqlmodel import Session, select

from ..models import ExchangeRate
from ..models.common import today_uy, utcnow

logger = logging.getLogger(__name__)

CACHE_HOURS = 6
TIMEOUT_SECONDS = 10
BCU_URL = "https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcucotizaciones"
BCU_USD_BILLETE = 2225  # código del BCU para el dólar billete
OPEN_ER_URL = "https://open.er-api.com/v6/latest/USD"

# El BCU usa SOAP: un formato de pedido en XML (más antiguo que JSON).
BCU_REQUEST = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cot="Cotiza">
<soapenv:Header/><soapenv:Body><cot:wsbcucotizaciones.Execute><cot:Entrada>
<cot:Moneda><cot:item>{moneda}</cot:item></cot:Moneda>
<cot:FechaDesde>{desde}</cot:FechaDesde><cot:FechaHasta>{hasta}</cot:FechaHasta>
<cot:Grupo>0</cot:Grupo></cot:Entrada></cot:wsbcucotizaciones.Execute></soapenv:Body>
</soapenv:Envelope>"""


@dataclass
class RateQuote:
    """Una cotización recién obtenida de alguna fuente."""

    rate: float          # pesos por 1 USD
    rate_date: dt.date   # a qué día corresponde
    source: str


class RateUnavailable(Exception):
    """No hay ninguna cotización disponible (ni en internet ni guardada)."""


# --- Fuentes ---------------------------------------------------------------

def parse_bcu_response(xml_bytes: bytes) -> RateQuote | None:
    """Lee la respuesta XML del BCU y devuelve la cotización más reciente."""
    ns = {"c": "Cotiza"}
    root = ET.fromstring(xml_bytes)
    datos = root.findall(".//c:datoscotizaciones.dato", ns)
    if not datos:
        return None
    ultimo = max(datos, key=lambda d: d.findtext("c:Fecha", namespaces=ns))
    return RateQuote(
        rate=float(ultimo.findtext("c:TCV", namespaces=ns)),  # TCV = tipo de cambio vendedor
        rate_date=dt.date.fromisoformat(ultimo.findtext("c:Fecha", namespaces=ns)),
        source="BCU",
    )


def fetch_bcu(until: dt.date) -> RateQuote | None:
    """Pide al BCU la cotización vigente al día `until` (o el último día hábil antes)."""
    body = BCU_REQUEST.format(
        moneda=BCU_USD_BILLETE, desde=until - dt.timedelta(days=10), hasta=until
    )
    resp = httpx.post(
        BCU_URL, content=body, timeout=TIMEOUT_SECONDS,
        headers={"Content-Type": "text/xml; charset=utf-8"},
    )
    resp.raise_for_status()  # si el servidor respondió con error, lanza excepción
    return parse_bcu_response(resp.content)


def fetch_open_er(until: dt.date) -> RateQuote | None:
    """Respaldo: solo sabe la cotización de HOY (no tiene históricos)."""
    if until < today_uy():
        return None
    resp = httpx.get(OPEN_ER_URL, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    if data.get("result") != "success" or "UYU" not in data.get("rates", {}):
        return None
    return RateQuote(rate=float(data["rates"]["UYU"]), rate_date=today_uy(), source="open.er-api.com")


def _fetchers():
    # Se buscan al momento de usarse (y no en una lista fija) para que los
    # tests puedan reemplazarlas por versiones falsas sin internet.
    return [fetch_bcu, fetch_open_er]


def _fetch_first_available(until: dt.date) -> RateQuote | None:
    """Prueba las fuentes en orden y devuelve la primera que responda bien."""
    for fetcher in _fetchers():
        try:
            quote = fetcher(until)
            if quote and quote.rate > 0:
                return quote
        except (httpx.HTTPError, ET.ParseError, ValueError, KeyError) as error:
            # Una fuente caída no debe romper la app: anotamos y seguimos
            logger.warning("Fuente de cotización %s falló: %s", fetcher.__name__, error)
    return None


# --- Caché en la base de datos ---------------------------------------------

def _as_aware(value: dt.datetime) -> dt.datetime:
    # SQLite no guarda la zona horaria; asumimos UTC (así la guardamos)
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def _save(session: Session, quote: RateQuote) -> ExchangeRate:
    """Guarda la cotización (o actualiza la del mismo día y fuente)."""
    row = session.exec(
        select(ExchangeRate).where(
            ExchangeRate.currency == "USD",
            ExchangeRate.rate_date == quote.rate_date,
            ExchangeRate.source == quote.source,
        )
    ).first()
    if row is None:
        row = ExchangeRate(currency="USD", rate=quote.rate, rate_date=quote.rate_date, source=quote.source)
    row.rate = quote.rate
    row.fetched_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_current_rate(session: Session) -> ExchangeRate:
    """Cotización actual del dólar, usando la caché si es reciente."""
    # La más reciente por FECHA de cotización (no por cuándo se guardó: un
    # histórico de marzo guardado hoy no debe tomarse como la "actual")
    latest = session.exec(
        select(ExchangeRate)
        .where(ExchangeRate.currency == "USD")
        .order_by(ExchangeRate.rate_date.desc(), ExchangeRate.fetched_at.desc())
    ).first()

    if latest and utcnow() - _as_aware(latest.fetched_at) < dt.timedelta(hours=CACHE_HOURS):
        return latest  # la caché está fresca: no salimos a internet

    quote = _fetch_first_available(today_uy())
    if quote:
        return _save(session, quote)
    if latest:
        return latest  # todas las fuentes fallaron: usamos el último valor conocido
    raise RateUnavailable("No se pudo obtener la cotización del dólar")


def rate_for_date(session: Session, date: dt.date) -> float:
    """
    Cotización de un día puntual (para congelar el valor de un gasto en USD).
    Para hoy o fechas futuras, usa la cotización actual.
    """
    if date >= today_uy():
        return get_current_rate(session).rate

    # ¿Ya tenemos guardada una cotización de ese día (o de pocos días antes)?
    row = session.exec(
        select(ExchangeRate)
        .where(
            ExchangeRate.currency == "USD",
            ExchangeRate.rate_date <= date,
            ExchangeRate.rate_date >= date - dt.timedelta(days=10),
        )
        .order_by(ExchangeRate.rate_date.desc())
    ).first()
    if row:
        return row.rate

    quote = _fetch_first_available(date)  # el BCU tiene históricos
    if quote:
        return _save(session, quote).rate
    return get_current_rate(session).rate
