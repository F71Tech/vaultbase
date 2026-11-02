"""Calculadora de sueldo nominal <-> líquido y aguinaldo (Uruguay). Pública."""

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.salary import CURRENT, SalaryInput, SalaryResult, calculate

router = APIRouter(prefix="/api/salary", tags=["Sueldo"])


@router.post("/calculate", response_model=SalaryResult)
def calculate_salary(data: SalaryInput):
    """
    Calcula el líquido a partir del nominal (o el nominal necesario para un
    líquido). Incluye el desglose de BPS, FONASA, FRL, IRPF y el aguinaldo.
    """
    return calculate(data)


class ParamsOut(BaseModel):
    year: int
    bpc_cents: int
    irpf_brackets: list[tuple[float | None, float]]
    pension_rate: float
    frl_rate: float
    sources: list[str]


@router.get("/params", response_model=ParamsOut)
def params():
    """Los valores que usa la calculadora (para mostrarlos con su fuente)."""
    return ParamsOut(
        year=CURRENT.year, bpc_cents=CURRENT.bpc_cents,
        irpf_brackets=list(CURRENT.irpf_brackets),
        pension_rate=CURRENT.pension_rate, frl_rate=CURRENT.frl_rate,
        sources=[
            "BPS · Comunicado R 5/2026 (IRPF ejercicio 2026: valores mensuales)",
            "BPS · Tasas Fonasa (aporte personal)",
            "BPS · Comunicado 01/2019 (Fondo de Reconversión Laboral 0,10 %)",
        ],
    )
