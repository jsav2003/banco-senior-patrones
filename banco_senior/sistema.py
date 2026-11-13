"""Arma el sistema: el único lugar que conoce todas las clases concretas.

Aquí se conectan los dos patrones:
    Mediator: MediadorModulos recibe a GestionUsuario, Notificaciones y Auditoria.
    Observer: Notificaciones y Auditoria se suscriben al PublicadorEventos.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Union

from .auditoria import Auditoria
from .gestion_usuario import GestionUsuario
from .mediator import MediadorModulos
from .notificaciones import Notificaciones
from .observer import PublicadorEventos
from .pension import ProcesadorConsignacion
from .simuladores import CoreBancarioSimulado, OperadorMensajeriaSimulado


@dataclass
class Sistema:
    publicador: PublicadorEventos
    mediador: MediadorModulos
    gestion: GestionUsuario
    notificaciones: Notificaciones
    auditoria: Auditoria
    procesador: ProcesadorConsignacion
    core: CoreBancarioSimulado
    operador: OperadorMensajeriaSimulado


def armar_sistema(cuentas: Dict[str, str], fallar_para: Iterable[str] = ()) -> Sistema:
    """Crea los módulos y conecta Observer y Mediator.

    cuentas: documento -> número de cuenta en el core simulado.
    fallar_para: destinos a los que el operador simulado no entrega mensajes.
    """
    publicador = PublicadorEventos()
    core = CoreBancarioSimulado(cuentas)
    operador = OperadorMensajeriaSimulado(fallar_para)

    gestion = GestionUsuario(publicador)
    notificaciones = Notificaciones(operador)
    auditoria = Auditoria()

    # Mediator: el mediador recibe a los módulos y les entrega su referencia.
    mediador = MediadorModulos(gestion, notificaciones, auditoria)

    # Observer: quienes reaccionan a los hechos se suscriben. Auditoría va primero
    # solo para que el log se lea en orden (el abono antes que su aviso); ningún
    # suscriptor depende del orden para funcionar.
    publicador.suscribir(auditoria)
    publicador.suscribir(notificaciones)

    procesador = ProcesadorConsignacion(core, publicador)
    return Sistema(
        publicador,
        mediador,
        gestion,
        notificaciones,
        auditoria,
        procesador,
        core,
        operador,
    )


def armar_desde_csv(
    ruta_pensionados: Union[str, Path], fallar_para: Iterable[str] = ()
) -> Sistema:
    """Arma el sistema con los pensionados sintéticos de un CSV.

    Columnas: documento, nombre, celular, correo, canal_preferido, cuenta.
    """
    with open(ruta_pensionados, encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    sistema = armar_sistema({f["documento"]: f["cuenta"] for f in filas}, fallar_para)
    for f in filas:
        sistema.gestion.cargar_pensionado(
            f["documento"], f["nombre"], f["celular"], f["correo"]
        )
        sistema.notificaciones.preferir_canal(f["documento"], f["canal_preferido"])
    return sistema


def referencias_directas_entre_modulos(sistema: Sistema) -> List[str]:
    """Lista los atributos de un módulo que apuntan a otro módulo.

    Con los dos patrones la lista debe quedar vacía: los módulos solo guardan
    referencias al mediador, al publicador o a los simuladores externos.
    """
    modulos = [
        sistema.gestion,
        sistema.notificaciones,
        sistema.auditoria,
        sistema.procesador,
    ]
    encontradas = []
    for modulo in modulos:
        for atributo, valor in vars(modulo).items():
            if any(valor is otro for otro in modulos if otro is not modulo):
                encontradas.append(
                    f"{type(modulo).__name__}.{atributo} -> {type(valor).__name__}"
                )
    return encontradas
