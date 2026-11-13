"""Módulo de auditoría: log de eventos y resultados (RNF-006).

Papel en los patrones:
    Observer: es un suscriptor. Registra todo evento publicado, incluso tipos
              nuevos, sin cambiar su código.
    Mediator: es un componente (Modulo). Atiende RegistrarResultado.

En producción el log se conservaría 5 años (RNF-006); en el prototipo vive en
memoria.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from typing import List, Tuple

from .eventos import Evento
from .formato import pesos
from .mediator import Modulo, RegistrarResultado
from .observer import Suscriptor
from .traza import traza


@dataclass(frozen=True)
class RegistroAuditable:
    momento: datetime
    tipo: str
    documento: str
    detalle: str


class Auditoria(Modulo, Suscriptor):
    """Guarda en orden cronológico los eventos y los resultados de las acciones."""

    def __init__(self) -> None:
        Modulo.__init__(self)
        self._registros: List[RegistroAuditable] = []

    def actualizar(self, evento: Evento) -> None:
        """Observer: registra cualquier evento con todos sus datos."""
        datos = [
            _describir(f.name, getattr(evento, f.name))
            for f in fields(evento)
            if f.name not in ("documento", "momento")
        ]
        self._agregar(evento.tipo, evento.documento, ", ".join(datos))

    def registrar(self, resultado: RegistrarResultado) -> None:
        """Mediator: atiende RegistrarResultado."""
        estado = "enviado" if resultado.exito else "FALLIDO"
        self._agregar(
            f"{resultado.accion.capitalize()} {estado}",
            resultado.documento,
            resultado.detalle,
        )

    @property
    def registros(self) -> Tuple[RegistroAuditable, ...]:
        return tuple(self._registros)

    def _agregar(self, tipo: str, documento: str, detalle: str) -> None:
        self._registros.append(
            RegistroAuditable(datetime.now(), tipo, documento, detalle)
        )
        traza("AUDITORIA", f"Registra «{tipo}» del documento {documento}")


_ETIQUETAS = {"transaccion": "transacción"}


def _describir(nombre: str, valor: object) -> str:
    if nombre == "monto" and isinstance(valor, int):
        return f"monto {pesos(valor)}"
    return f"{_ETIQUETAS.get(nombre, nombre)} {valor}"
