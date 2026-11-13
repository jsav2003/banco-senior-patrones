"""Formatos compartidos por los módulos."""


def pesos(monto: int) -> str:
    """Formatea un monto en pesos colombianos: 1423500 -> '$1.423.500'."""
    return "$" + f"{monto:,}".replace(",", ".")
