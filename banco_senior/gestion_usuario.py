"""Módulo Gestión de Usuario: pensionados, datos de contacto e intentos de ingreso.

Papel en los patrones:
    Mediator: es un componente (Modulo). Atiende ConsultarContacto y pide
              EnviarCodigo, siempre a través del mediador. No conoce a
              Notificaciones ni a Auditoria.
    Observer: publica CuentaBloqueada y AccesoSospechoso sin saber quién
              reacciona.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .eventos import AccesoSospechoso, CuentaBloqueada
from .mediator import EnviarCodigo, Modulo
from .observer import PublicadorEventos
from .traza import traza


@dataclass(frozen=True)
class Contacto:
    """Datos de contacto que GestionUsuario entrega cuando se piden por el mediador."""

    nombre: str
    celular: str
    correo: str


@dataclass
class Pensionado:
    documento: str
    nombre: str
    celular: str
    correo: str
    verificado: bool = False
    intentos_fallidos: List[datetime] = field(default_factory=list)
    bloqueada_hasta: Optional[datetime] = None


class GestionUsuario(Modulo):
    """Registra pensionados, guarda su contacto y controla los intentos de ingreso."""

    UMBRAL_SOSPECHA = 3  # US-303: más de 3 intentos fallidos...
    VENTANA_SOSPECHA = timedelta(minutes=5)  # ...en menos de 5 minutos
    MAX_INTENTOS = 5  # US-108: bloqueo al quinto intento consecutivo
    MINUTOS_BLOQUEO = 30

    def __init__(self, publicador: PublicadorEventos) -> None:
        super().__init__()
        self._publicador = publicador
        self._pensionados: Dict[str, Pensionado] = {}

    def cargar_pensionado(
        self, documento: str, nombre: str, celular: str, correo: str
    ) -> None:
        """Carga un pensionado ya registrado y verificado (datos sintéticos)."""
        self._pensionados[documento] = Pensionado(
            documento, nombre, celular, correo, verificado=True
        )

    def registrar(self, documento: str, nombre: str, celular: str, correo: str) -> bool:
        """Registra un pensionado y pide enviarle su código (US-101 y US-102).

        GestionUsuario no sabe quién envía el código ni por qué canal: le pasa la
        solicitud EnviarCodigo al mediador. Devuelve True si el código salió.
        """
        if documento in self._pensionados:
            raise ValueError(f"El documento {documento} ya está registrado")
        self._pensionados[documento] = Pensionado(documento, nombre, celular, correo)
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        traza("GESTION", f"Registro de {nombre}: se genera su código de verificación")
        return bool(self._pedir(EnviarCodigo(documento, codigo)))

    def datos_contacto(self, documento: str) -> Contacto:
        """Atiende ConsultarContacto, la solicitud que llega por el mediador."""
        pensionado = self._buscar(documento)
        return Contacto(pensionado.nombre, pensionado.celular, pensionado.correo)

    def intento_fallido(
        self, documento: str, momento: Optional[datetime] = None
    ) -> None:
        """Registra un intento fallido de inicio de sesión.

        Publica AccesoSospechoso al cuarto intento dentro de 5 minutos (US-303) y
        CuentaBloqueada al quinto intento consecutivo (US-108). No sabe quién
        reacciona a esos eventos.
        """
        momento = momento or datetime.now()
        pensionado = self._buscar(documento)
        pensionado.intentos_fallidos.append(momento)
        recientes = [
            t
            for t in pensionado.intentos_fallidos
            if momento - t < self.VENTANA_SOSPECHA
        ]
        traza(
            "GESTION",
            f"Intento fallido número {len(pensionado.intentos_fallidos)} "
            f"de {pensionado.nombre}",
        )
        if len(recientes) == self.UMBRAL_SOSPECHA + 1:
            self._publicador.publicar(
                AccesoSospechoso(documento, intentos=len(recientes))
            )
        if len(pensionado.intentos_fallidos) == self.MAX_INTENTOS:
            pensionado.bloqueada_hasta = momento + timedelta(
                minutes=self.MINUTOS_BLOQUEO
            )
            self._publicador.publicar(
                CuentaBloqueada(documento, minutos=self.MINUTOS_BLOQUEO)
            )

    def inicio_exitoso(self, documento: str) -> None:
        """Un ingreso correcto reinicia el conteo de intentos consecutivos."""
        self._buscar(documento).intentos_fallidos.clear()

    def bloqueada_hasta(self, documento: str) -> Optional[datetime]:
        """Hasta cuándo está bloqueada la cuenta, o None si no lo está."""
        return self._buscar(documento).bloqueada_hasta

    def _buscar(self, documento: str) -> Pensionado:
        try:
            return self._pensionados[documento]
        except KeyError:
            raise KeyError(f"No hay un pensionado con documento {documento}") from None
