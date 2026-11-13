"""Traza de la demo: muestra en consola qué patrón actúa en cada paso.

No forma parte de los patrones. Sirve para seguir la demo en la presentación:
cada línea lleva una etiqueta ([OBSERVER], [MEDIATOR], [CORE], ...) y la
sangría indica qué llamada ocurre dentro de cuál. Las pruebas la desactivan.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

ACTIVA = True
_nivel = 0


def traza(etiqueta: str, mensaje: str) -> None:
    """Imprime «[ETIQUETA] mensaje» con la sangría del nivel actual."""
    if ACTIVA:
        print(f"{'    ' * _nivel}{'[' + etiqueta + ']':<11} {mensaje}")


@contextmanager
def mas_adentro() -> Iterator[None]:
    """Aumenta la sangría mientras dura el bloque «with»."""
    global _nivel
    _nivel += 1
    try:
        yield
    finally:
        _nivel -= 1
