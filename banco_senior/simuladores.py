"""Simuladores de los sistemas externos (no son parte de los patrones).

El caso no define las interfaces del core bancario ni del operador de
mensajería, y las pruebas solo pueden usar datos sintéticos (Ley 1581 de 2012).
Por eso el prototipo trabaja con estas dos clases simuladas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .formato import pesos
from .traza import traza


class CoreBancarioSimulado:
    """Simula el core bancario: cuentas por documento, saldos y abonos."""

    def __init__(self, cuentas: Dict[str, str]) -> None:
        self._cuentas = dict(cuentas)  # documento -> número de cuenta
        self._saldos = {cuenta: 0 for cuenta in self._cuentas.values()}
        self._consecutivo = 0

    def cuenta_de(self, documento: str) -> Optional[str]:
        """Devuelve la cuenta del documento o None si no tiene cuenta en el banco."""
        return self._cuentas.get(documento)

    def abonar(self, cuenta: str, monto: int) -> str:
        """Abona el monto y devuelve el identificador de la transacción."""
        self._saldos[cuenta] += monto
        self._consecutivo += 1
        transaccion = f"TX-{self._consecutivo:04d}"
        traza("CORE", f"Abono de {pesos(monto)} en la cuenta {cuenta} ({transaccion})")
        return transaccion

    def saldo(self, cuenta: str) -> int:
        return self._saldos[cuenta]


class OperadorMensajeriaSimulado:
    """Simula el operador que entrega SMS, correos y llamadas.

    Los destinos de fallar_para simulan un operador que no responde, para
    mostrar que un aviso fallido no revierte el abono.
    """

    def __init__(self, fallar_para: Iterable[str] = ()) -> None:
        self._fallar_para = set(fallar_para)
        # Cada envío queda como (momento, canal, destino, mensaje).
        self.enviados: List[Tuple[datetime, str, str, str]] = []

    def enviar(self, canal: str, destino: str, mensaje: str) -> None:
        """Entrega el mensaje o lanza ConnectionError si el operador no responde."""
        if destino in self._fallar_para:
            traza("OPERADOR", f"{canal.upper()} a {destino}: el operador no responde")
            raise ConnectionError(f"el operador no entregó el {canal} a {destino}")
        self.enviados.append((datetime.now(), canal, destino, mensaje))
        traza("OPERADOR", f'{canal.upper()} a {destino}: "{mensaje}"')
