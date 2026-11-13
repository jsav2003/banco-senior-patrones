"""Eventos: hechos que ya ocurrieron en un módulo.

Son los mensajes del patrón Observer. Un módulo los publica y no sabe quién los
recibe. Cada evento es inmutable y lleva el momento en que ocurrió.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Evento:
    """Hecho que ya ocurrió y que puede interesar a otros módulos."""

    documento: str
    momento: datetime = field(default_factory=datetime.now, init=False, compare=False)

    @property
    def tipo(self) -> str:
        """Nombre del evento, por ejemplo «AbonoRegistrado»."""
        return type(self).__name__

    def __str__(self) -> str:
        return f"{self.tipo}(documento {self.documento})"


@dataclass(frozen=True)
class AbonoRegistrado(Evento):
    """Pensión y Productos abonó la mesada en el core bancario (US-201)."""

    nombre: str
    monto: int
    periodo: str
    transaccion: str


@dataclass(frozen=True)
class CuentaBloqueada(Evento):
    """Gestión de Usuario bloqueó la cuenta por intentos fallidos (US-108)."""

    minutos: int


@dataclass(frozen=True)
class AccesoSospechoso(Evento):
    """Más de 3 intentos fallidos de ingreso en menos de 5 minutos (US-303)."""

    intentos: int
