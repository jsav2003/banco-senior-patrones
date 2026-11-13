"""Patrón Observer (conductual): difunde los hechos que ya ocurrieron.

Problema P-05: el abono, el bloqueo de una cuenta y un acceso sospechoso deben
llegar a Notificaciones y a Auditoría sin que el módulo que los produce los
conozca. Además, deben poder sumarse reacciones nuevas, como el historial de
consignaciones (US-203), sin modificar a quien publica.

Participantes (nombre en Refactoring Guru -> nombre en Banco Senior+):
    Notificador (publisher)   -> PublicadorEventos
    Interfaz suscriptora      -> Suscriptor
    Suscriptores concretos    -> Notificaciones, Auditoria, HistorialConsignaciones
    Clientes que publican     -> ProcesadorConsignacion, GestionUsuario
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .eventos import Evento
from .traza import mas_adentro, traza


class Suscriptor(ABC):
    """Interfaz de todo objeto que quiere enterarse de los eventos publicados."""

    @abstractmethod
    def actualizar(self, evento: Evento) -> None:
        """Reacciona a un evento. Cada suscriptor decide qué hacer o si lo ignora."""


class PublicadorEventos:
    """Guarda la lista de suscriptores y le entrega cada evento a todos.

    Solo conoce la interfaz Suscriptor, nunca las clases concretas. Por eso un
    suscriptor nuevo se agrega con una línea, publicador.suscribir(...), sin
    cambiar el código del publicador ni el de quien publica.
    """

    def __init__(self) -> None:
        self._suscriptores: List[Suscriptor] = []
        self.eventos_publicados = 0  # contador para el resumen de la demo

    def suscribir(self, suscriptor: Suscriptor) -> None:
        """Agrega un suscriptor en tiempo de ejecución, sin duplicarlo."""
        if suscriptor not in self._suscriptores:
            self._suscriptores.append(suscriptor)
            traza("OBSERVER", f"{type(suscriptor).__name__} se suscribe a los eventos")

    def desuscribir(self, suscriptor: Suscriptor) -> None:
        """Retira un suscriptor; desde ese momento deja de recibir eventos."""
        if suscriptor in self._suscriptores:
            self._suscriptores.remove(suscriptor)
            traza("OBSERVER", f"{type(suscriptor).__name__} deja de recibir eventos")

    def publicar(self, evento: Evento) -> None:
        """Entrega el evento a cada suscriptor, en el orden en que se suscribieron.

        Si un suscriptor falla, el error queda en la traza y se sigue con los
        demás: un aviso que no sale no puede revertir el abono ni impedir que
        Auditoría lo registre. Nadie debe depender del orden de entrega.
        """
        self.eventos_publicados += 1
        traza(
            "OBSERVER", f"Se publica {evento} a {len(self._suscriptores)} suscriptores"
        )
        with mas_adentro():
            for suscriptor in list(self._suscriptores):
                nombre = type(suscriptor).__name__
                traza("OBSERVER", f"-> {nombre}.actualizar({evento.tipo})")
                with mas_adentro():
                    try:
                        suscriptor.actualizar(evento)
                    except Exception as error:  # aísla a cada suscriptor
                        traza("OBSERVER", f"{nombre} falló: {error}")
