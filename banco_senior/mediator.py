"""Patrón Mediator (conductual): las peticiones entre módulos pasan por un mediador.

Problema P-05: Notificaciones necesita los datos de contacto que guarda Gestión
de Usuario; Gestión de Usuario necesita que Notificaciones envíe el código de
verificación (US-102); y el resultado de cada envío debe quedar en Auditoría
(RNF-006). Sin mediador, cada módulo tendría que conocer a los otros.

Participantes (nombre en Refactoring Guru -> nombre en Banco Senior+):
    Mediador (interfaz)    -> Mediador
    Mediador concreto      -> MediadorModulos
    Componentes            -> Modulo y sus subclases: GestionUsuario,
                              Notificaciones, Auditoria

Diferencia con Observer: un evento es un hecho que se difunde a quien quiera
oírlo; una solicitud es una petición que va a un solo módulo y puede esperar
respuesta. El mediador decide qué módulo la atiende.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

from .traza import mas_adentro, traza

if TYPE_CHECKING:  # solo para las anotaciones; evita importaciones circulares
    from .auditoria import Auditoria
    from .gestion_usuario import GestionUsuario
    from .notificaciones import Notificaciones


# --- Solicitudes: lo que un módulo le puede pedir a otro -------------------


@dataclass(frozen=True)
class Solicitud:
    """Petición de un módulo que el mediador entrega al módulo que la atiende."""


@dataclass(frozen=True)
class ConsultarContacto(Solicitud):
    """Pide el nombre, el celular y el correo de un pensionado (GestionUsuario)."""

    documento: str

    def __str__(self) -> str:
        return f"ConsultarContacto({self.documento})"


@dataclass(frozen=True)
class EnviarCodigo(Solicitud):
    """Pide enviar el código de verificación, US-102 (Notificaciones)."""

    documento: str
    codigo: str

    def __str__(self) -> str:
        return f"EnviarCodigo({self.documento})"


@dataclass(frozen=True)
class RegistrarResultado(Solicitud):
    """Pide dejar en el log el resultado de una acción, RNF-006 (Auditoria)."""

    accion: str
    documento: str
    exito: bool
    detalle: str = ""

    def __str__(self) -> str:
        estado = "enviado" if self.exito else "FALLIDO"
        return f"RegistrarResultado({self.accion} {estado})"


# --- Interfaz del mediador y clase base de los componentes -----------------


class Mediador(ABC):
    """Interfaz que conocen los módulos. Es lo único que saben de los demás."""

    @abstractmethod
    def notificar(self, emisor: "Modulo", solicitud: Solicitud) -> Any:
        """Entrega la solicitud al módulo que la atiende y devuelve su respuesta."""


class Modulo:
    """Componente del mediador: colabora con los demás módulos solo a través de él.

    No guarda referencias a otros módulos; solo al mediador, que recibe cuando
    el mediador se crea (conectar).
    """

    def __init__(self) -> None:
        self._mediador: Optional[Mediador] = None

    def conectar(self, mediador: Mediador) -> None:
        """Guarda la referencia al mediador. La llama MediadorModulos al crearse."""
        self._mediador = mediador

    def _pedir(self, solicitud: Solicitud) -> Any:
        """Envía una solicitud al mediador y devuelve la respuesta."""
        if self._mediador is None:
            nombre = type(self).__name__
            raise RuntimeError(f"{nombre} no está conectado a un mediador")
        return self._mediador.notificar(self, solicitud)


# --- Mediador concreto ------------------------------------------------------


class MediadorModulos(Mediador):
    """Conoce a los tres módulos y decide qué módulo atiende cada solicitud.

    Solo enruta: no tiene reglas de negocio. Así se evita que crezca hasta ser
    un objeto todopoderoso, el riesgo que advierte Refactoring Guru. Para
    atender una solicitud nueva se agrega una entrada en self._rutas y no se
    toca ningún otro módulo.
    """

    def __init__(
        self,
        gestion: "GestionUsuario",
        notificaciones: "Notificaciones",
        auditoria: "Auditoria",
    ) -> None:
        self._gestion = gestion
        self._notificaciones = notificaciones
        self._auditoria = auditoria
        for modulo in (gestion, notificaciones, auditoria):
            modulo.conectar(self)
        self._rutas: Dict[type, Tuple[str, Callable[[Any], Any]]] = {
            ConsultarContacto: ("GestionUsuario", self._consultar_contacto),
            EnviarCodigo: ("Notificaciones", self._enviar_codigo),
            RegistrarResultado: ("Auditoria", self._registrar_resultado),
        }
        # Contador para el resumen de la demo.
        self.solicitudes_atendidas: Counter = Counter()
        traza(
            "MEDIATOR",
            "MediadorModulos conecta a GestionUsuario, Notificaciones y Auditoria",
        )

    def notificar(self, emisor: Modulo, solicitud: Solicitud) -> Any:
        """Busca qué módulo atiende la solicitud y le entrega el trabajo."""
        ruta = self._rutas.get(type(solicitud))
        if ruta is None:
            raise ValueError(f"El mediador no sabe atender {type(solicitud).__name__}")
        destino, atender = ruta
        self.solicitudes_atendidas[type(solicitud).__name__] += 1
        traza(
            "MEDIATOR",
            f"{type(emisor).__name__} pide {solicitud} -> la atiende {destino}",
        )
        with mas_adentro():
            return atender(solicitud)

    def _consultar_contacto(self, solicitud: ConsultarContacto) -> Any:
        return self._gestion.datos_contacto(solicitud.documento)

    def _enviar_codigo(self, solicitud: EnviarCodigo) -> bool:
        return self._notificaciones.enviar_codigo(solicitud.documento, solicitud.codigo)

    def _registrar_resultado(self, solicitud: RegistrarResultado) -> None:
        self._auditoria.registrar(solicitud)
 