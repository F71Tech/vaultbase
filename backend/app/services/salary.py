"""
Calculadora de sueldo para trabajadores dependientes del sector privado (Uruguay).

    NOMINAL = lo que dice el contrato.
    LÍQUIDO = lo que te depositan = nominal - aportes (BPS, FONASA, FRL) - IRPF.

Todos los parámetros están juntos en PARAMS_2026, con su fuente. Cada enero
cambian (la BPC se ajusta): basta con agregar PARAMS_2027 y apuntar CURRENT.

Fuentes oficiales consultadas (noviembre 2026):
  - BPS, Comunicado R 5/2026 "IRPF ejercicio 2026: valores mensuales":
    BPC $ 6.864, escala progresional, tasa de deducciones 14 % / 8 %,
    deducción por hijo 20 BPC anuales ($ 11.440 mensuales).
  - BPS, "Tasas Fonasa": aporte personal según sueldo y familia a cargo.
  - BPS, Comunicado 01/2019: Fondo de Reconversión Laboral 0,10 %.

Es una ESTIMACIÓN: no contempla el tope de aportes jubilatorios (afecta
solo a sueldos muy altos), el Fondo de Solidaridad, ni el ajuste anual del IRPF.
"""

import math
from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator


@dataclass(frozen=True)
class SalaryParams:
    year: int
    bpc_cents: int
    # Escala mensual del IRPF: (hasta cuántas BPC, tasa). None = sin tope.
    irpf_brackets: tuple[tuple[float | None, float], ...]
    increment_threshold_bpc: float  # si el ingreso supera esto, la base se incrementa 6 %
    increment_rate: float
    deduction_rate_low: float       # tasa de deducciones para ingresos bajos
    deduction_rate_high: float
    deduction_threshold_bpc: float  # corte entre una y otra tasa
    child_deduction_bpc_year: float
    disabled_child_deduction_bpc_year: float
    pension_rate: float             # aporte jubilatorio (montepío)
    frl_rate: float                 # Fondo de Reconversión Laboral
    fonasa_threshold_bpc: float     # 2,5 BPC
    # FONASA: (con cónyuge a cargo, con hijos) -> (tasa hasta 2,5 BPC, tasa por encima)
    fonasa_rates: dict


PARAMS_2026 = SalaryParams(
    year=2026,
    bpc_cents=686_400,
    irpf_brackets=(
        (7, 0.0), (10, 0.10), (15, 0.15), (30, 0.24), (50, 0.25), (75, 0.27), (115, 0.31), (None, 0.36),
    ),
    increment_threshold_bpc=10,
    increment_rate=0.06,
    deduction_rate_low=0.14,
    deduction_rate_high=0.08,
    deduction_threshold_bpc=15,
    child_deduction_bpc_year=20,
    disabled_child_deduction_bpc_year=40,
    pension_rate=0.15,
    frl_rate=0.001,
    fonasa_threshold_bpc=2.5,
    fonasa_rates={
        (False, False): (0.03, 0.045),
        (False, True): (0.03, 0.06),
        (True, False): (0.05, 0.065),
        (True, True): (0.05, 0.08),
    },
)
CURRENT = PARAMS_2026


# --- Entrada y salida -------------------------------------------------------

class SalaryInput(BaseModel):
    """Datos del trabajador. Mandá el nominal O el líquido que querés cobrar."""

    nominal_cents: int | None = Field(default=None, gt=0, le=10_000_000_000)
    net_cents: int | None = Field(default=None, gt=0, le=10_000_000_000)
    children: int = Field(default=0, ge=0, le=15)             # hijos menores a cargo
    disabled_children: int = Field(default=0, ge=0, le=15)    # hijos con discapacidad
    spouse: bool = False      # cónyuge/concubino a cargo sin cobertura propia del SNIS
    # Deducción por hijos: 100 % si la tomás vos sola/o, 50 % si se reparte con el otro progenitor
    children_share_pct: int = Field(default=100, ge=0, le=100)

    @model_validator(mode="after")
    def _uno_de_los_dos(self):
        if (self.nominal_cents is None) == (self.net_cents is None):
            raise ValueError("Enviá nominal_cents o net_cents (uno de los dos)")
        return self


class Breakdown(BaseModel):
    nominal_cents: int
    pension_cents: int        # BPS: aporte jubilatorio
    fonasa_cents: int
    fonasa_rate: float
    frl_cents: int
    irpf_cents: int
    net_cents: int            # líquido
    # Detalle del IRPF, para mostrar "cómo se calculó"
    irpf_base_cents: int
    irpf_gross_cents: int
    irpf_deductions_cents: int
    deduction_rate: float


class AguinaldoEstimate(BaseModel):
    nominal_cents: int        # cada medio aguinaldo (junio y diciembre)
    contributions_cents: int  # BPS + FONASA + FRL
    net_cents: int


class SalaryResult(BaseModel):
    params_year: int
    bpc_cents: int
    monthly: Breakdown
    aguinaldo: AguinaldoEstimate
    annual_net_cents: int     # 12 sueldos + 2 medios aguinaldos (líquidos)


# --- Cálculo ----------------------------------------------------------------

def fonasa_rate(nominal_cents: int, spouse: bool, has_children: bool, p: SalaryParams = CURRENT) -> float:
    low, high = p.fonasa_rates[(spouse, has_children)]
    return high if nominal_cents > p.fonasa_threshold_bpc * p.bpc_cents else low


def progressive_tax(base_cents: float, p: SalaryParams = CURRENT) -> float:
    """
    Escala progresional: cada franja paga SU tasa solo por la parte que cae en ella.
    Ej.: con $ 60.000 -> los primeros $ 48.048 pagan 0 % y los $ 11.952 restantes, 10 %.
    """
    tax = 0.0
    lower = 0.0
    for upper_bpc, rate in p.irpf_brackets:
        upper = math.inf if upper_bpc is None else upper_bpc * p.bpc_cents
        if base_cents > lower:
            tax += (min(base_cents, upper) - lower) * rate
        lower = upper
    return tax


def breakdown_from_nominal(nominal: int, data: SalaryInput, p: SalaryParams = CURRENT) -> Breakdown:
    # 1) Aportes a la seguridad social (sobre el nominal)
    rate = fonasa_rate(nominal, data.spouse, data.children + data.disabled_children > 0, p)
    pension = round(nominal * p.pension_rate)
    fonasa = round(nominal * rate)
    frl = round(nominal * p.frl_rate)
    contributions = pension + fonasa + frl

    # 2) IRPF. Si el sueldo supera 10 BPC, la base se incrementa 6 %: así se va
    #    anticipando mes a mes el impuesto del aguinaldo y el salario vacacional.
    base = nominal * (1 + p.increment_rate) if nominal > p.increment_threshold_bpc * p.bpc_cents else nominal
    gross = progressive_tax(base, p)

    # 3) Deducciones: aportes + hijos a cargo, multiplicadas por una tasa fija
    share = data.children_share_pct / 100
    children = (data.children * p.child_deduction_bpc_year
                + data.disabled_children * p.disabled_child_deduction_bpc_year) * p.bpc_cents / 12 * share
    deduction_rate = p.deduction_rate_low if base <= p.deduction_threshold_bpc * p.bpc_cents else p.deduction_rate_high
    deductions = (contributions + children) * deduction_rate

    irpf = round(max(gross - deductions, 0))
    return Breakdown(
        nominal_cents=nominal, pension_cents=pension, fonasa_cents=fonasa, fonasa_rate=rate,
        frl_cents=frl, irpf_cents=irpf, net_cents=nominal - contributions - irpf,
        irpf_base_cents=round(base), irpf_gross_cents=round(gross),
        irpf_deductions_cents=round(deductions), deduction_rate=deduction_rate,
    )


def nominal_for_net(target_net: int, data: SalaryInput, p: SalaryParams = CURRENT) -> int:
    """
    Al revés: ¿qué nominal necesito para cobrar X líquido?
    No hay una fórmula directa (el IRPF tiene franjas), así que usamos
    "búsqueda binaria": probamos un nominal, vemos si da más o menos líquido
    y achicamos el rango a la mitad, hasta encontrar el centésimo exacto.
    """
    low, high = target_net, target_net * 3
    while low < high:
        mid = (low + high) // 2
        if breakdown_from_nominal(mid, data, p).net_cents < target_net:
            low = mid + 1
        else:
            high = mid
    return low


def aguinaldo_from_nominal(monthly_nominal: int, data: SalaryInput, p: SalaryParams = CURRENT) -> AguinaldoEstimate:
    """
    Medio aguinaldo = lo ganado en el semestre / 12 (con sueldo fijo: medio sueldo).
    Tiene aportes de BPS, FONASA (a la tasa del sueldo) y FRL. El IRPF no se
    descuenta aparte: para sueldos de más de 10 BPC ya se anticipó con el
    incremento del 6 %, y por debajo queda bajo el mínimo no imponible.
    """
    nominal = round(monthly_nominal * 6 / 12)
    rate = fonasa_rate(monthly_nominal, data.spouse, data.children + data.disabled_children > 0, p)
    contributions = round(nominal * p.pension_rate) + round(nominal * rate) + round(nominal * p.frl_rate)
    return AguinaldoEstimate(nominal_cents=nominal, contributions_cents=contributions, net_cents=nominal - contributions)


def calculate(data: SalaryInput, p: SalaryParams = CURRENT) -> SalaryResult:
    nominal = data.nominal_cents if data.nominal_cents is not None else nominal_for_net(data.net_cents, data, p)
    monthly = breakdown_from_nominal(nominal, data, p)
    aguinaldo = aguinaldo_from_nominal(nominal, data, p)
    return SalaryResult(
        params_year=p.year, bpc_cents=p.bpc_cents, monthly=monthly, aguinaldo=aguinaldo,
        annual_net_cents=monthly.net_cents * 12 + aguinaldo.net_cents * 2,
    )
