"""Módulo Notificaciones: avisa al pensionado por su canal preferido.

Papel en los patrones:
    Observer: es un suscriptor. Reacciona a AbonoRegistrado (US-301),
              CuentaBloqueada (US-108) y AccesoSospechoso (US-303).
    Mediator: es un componente (Modulo). Pide ConsultarContacto y
              RegistrarResultado y atiende EnviarCodigo, siempre a través del
              mediador. No conoce a GestionUsuario ni a Auditoria.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from .eventos import AbonoRegistrado, AccesoSospechoso, CuentaBloqueada, Evento
from .formato import pesos
from .mediator import ConsultarContacto, Modulo, RegistrarResultado
from .observer import Suscriptor
from .simuladores import OperadorMensajeriaSimulado
from .traza import traza


class Notificaciones(Modulo, Suscriptor):
    """Decide qué aviso enviar y por qué canal; el operador lo entrega."""

    CANALES = ("sms", "correo", "llamada")  # US-302
    CANAL_POR_DEFECTO = "sms"
    PLAZO_AVISO_ABONO = 5 * 60  # US-301: menos de 5 minutos (en segundos)

    def __init__(self, operador: OperadorMensajeriaSimulado) -> None:
        Modulo.__init__(self)
        self._operador = operador
        self._canal_preferido: Dict[str, str] = {}

    # --- Canal preferido (US-302) ------------------------------------------

    def preferir_canal(self, documento: str, canal: str) -> None:
        """Guarda el canal que eligió el pensionado; se puede cambiar cuando quiera."""
        if canal not in self.CANALES:
            raise ValueError(f"Canal desconocido: {canal}. Use uno de {self.CANALES}")
        self._canal_preferido[documento] = canal

    def canal_de(self, documento: str) -> str:
        return self._canal_preferido.get(documento, self.CANAL_POR_DEFECTO)

    # --- Observer: reacción a los hechos publicados ------------------------

    def actualizar(self, evento: Evento) -> None:
        """Reacciona a los eventos que le interesan e ignora los demás."""
        canal = self.canal_de(evento.documento)
        if isinstance(evento, AbonoRegistrado):
            mensaje = (
                f"su pensión de {pesos(evento.monto)} del periodo "
                f"{evento.periodo} ya está en su cuenta."
            )
            if self.enviar_aviso(evento.documento, canal, mensaje):
                demora = (datetime.now() - evento.momento).total_seconds()
                plazo = "dentro" if demora < self.PLAZO_AVISO_ABONO else "FUERA"
                segundos = f"{demora:.2f}".replace(".", ",")
                texto = f"Aviso a {segundos} s del abono: {plazo} del plazo de US-301"
                traza("NOTIFICA", texto)
        elif isinstance(evento, AccesoSospechoso):
            segundo_canal = "correo" if canal != "correo" else "sms"
            for canal_alerta in (canal, segundo_canal):
                self.enviar_aviso(
                    evento.documento,
                    canal_alerta,
                    "hubo varios intentos fallidos de ingreso a su cuenta. "
                    "Si no fue usted, llame a Soporte.",
                )
        elif isinstance(evento, CuentaBloqueada):
            self.enviar_aviso(
                evento.documento,
                canal,
                f"su cuenta quedó bloqueada {evento.minutos} minutos por "
                f"intentos fallidos. Si no fue usted, llame a Soporte.",
            )

    # --- Mediator: petición que atiende ------------------------------------

    def enviar_codigo(self, documento: str, codigo: str) -> bool:
        """Atiende EnviarCodigo: envía el código por el canal preferido (US-102)."""
        return self.enviar_aviso(
            documento,
            self.canal_de(documento),
            f"su código de verificación es {codigo}. Vence en 15 minutos.",
        )

    # --- Envío común ---------------------------------------------------------

    def enviar_aviso(self, documento: str, canal: str, mensaje: str) -> bool:
        """Envía un aviso; el contacto y el resultado pasan por el mediador.

        Si el operador falla, el error se maneja aquí: se devuelve False y el
        resultado queda en Auditoría. El abono u otra acción que originó el aviso
        no se revierte.
        """
        contacto = self._pedir(ConsultarContacto(documento))
        destino = contacto.correo if canal == "correo" else contacto.celular
        primer_nombre = contacto.nombre.split()[0]
        try:
            self._operador.enviar(canal, destino, f"Hola, {primer_nombre}: {mensaje}")
            entregado = True
        except ConnectionError:
            entregado = False
        self._pedir(
            RegistrarResultado("aviso", documento, entregado, f"{canal} a {destino}")
        )
        return entregado
