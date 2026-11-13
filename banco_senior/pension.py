"""Módulo Pensión y Productos: consignación de la pensión e historial.

Papel en los patrones:
    Observer: ProcesadorConsignacion publica AbonoRegistrado sin saber quién
              reacciona. HistorialConsignaciones es un suscriptor que se agrega
              después, sin tocar al procesador (US-203).
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Union

from .eventos import AbonoRegistrado, Evento
from .observer import PublicadorEventos, Suscriptor
from .simuladores import CoreBancarioSimulado
from .traza import traza


@dataclass
class ResultadoProceso:
    """Lo que dejó el procesamiento de un archivo de pagos."""

    archivo: str
    abonos: List[AbonoRegistrado] = field(default_factory=list)
    diferencias: List[Dict[str, str]] = field(
        default_factory=list
    )  # reporte de diferencias
    repetido: bool = False


class ProcesadorConsignacion:
    """Concilia el archivo de pagos de la entidad estatal y abona en el core (US-201).

    Solo conoce al core bancario y al publicador. No llama a Notificaciones ni a
    Auditoría: publica AbonoRegistrado y cada suscriptor decide qué hacer.
    """

    def __init__(
        self, core: CoreBancarioSimulado, publicador: PublicadorEventos
    ) -> None:
        self._core = core
        self._publicador = publicador
        self._huellas_procesadas: Set[str] = set()

    def procesar(self, archivo: Union[str, Path]) -> ResultadoProceso:
        """Procesa un archivo CSV con columnas documento, nombre, monto y periodo.

        Abona las filas cuyo documento tiene cuenta en el banco y publica un
        AbonoRegistrado por cada una. Las demás van al reporte de diferencias.
        Un archivo ya procesado (misma huella SHA-256) no se abona dos veces.
        """
        ruta = Path(archivo)
        contenido = ruta.read_bytes()
        huella = hashlib.sha256(contenido).hexdigest()
        resultado = ResultadoProceso(ruta.name)
        if huella in self._huellas_procesadas:
            resultado.repetido = True
            traza("PENSION", f"{ruta.name} ya fue procesado: no se abona dos veces")
            return resultado

        traza("PENSION", f"Procesando {ruta.name}")
        for fila in csv.DictReader(io.StringIO(contenido.decode("utf-8-sig"))):
            documento = fila["documento"].strip()
            cuenta = self._core.cuenta_de(documento)
            if cuenta is None:
                resultado.diferencias.append(fila)
                traza(
                    "PENSION",
                    f"{fila['nombre']} ({documento}) no concilia: "
                    f"va al reporte de diferencias",
                )
                continue
            monto = int(fila["monto"])
            transaccion = self._core.abonar(cuenta, monto)
            evento = AbonoRegistrado(
                documento, fila["nombre"], monto, fila["periodo"], transaccion
            )
            resultado.abonos.append(evento)
            self._publicador.publicar(evento)
        self._huellas_procesadas.add(huella)
        return resultado


@dataclass(frozen=True)
class Consignacion:
    fecha: datetime
    periodo: str
    monto: int
    estado: str


class HistorialConsignaciones(Suscriptor):
    """Historial de consignaciones por pensionado, en orden descendente (US-203).

    Muestra la escalabilidad del Observer: se agrega con publicador.suscribir()
    y empieza a recibir los abonos sin modificar ProcesadorConsignacion. Solo ve
    los eventos publicados después de suscribirse.
    """

    def __init__(self) -> None:
        self._por_documento: Dict[str, List[Consignacion]] = {}

    def actualizar(self, evento: Evento) -> None:
        if isinstance(evento, AbonoRegistrado):
            self._por_documento.setdefault(evento.documento, []).append(
                Consignacion(evento.momento, evento.periodo, evento.monto, "Abonada")
            )
            traza(
                "HISTORIAL",
                f"Agrega la consignación {evento.periodo} del documento "
                f"{evento.documento}",
            )

    def consultar(self, documento: str) -> List[Consignacion]:
        """Consignaciones del pensionado, de la más reciente a la más antigua."""
        return sorted(
            self._por_documento.get(documento, []), key=lambda c: c.fecha, reverse=True
        )
