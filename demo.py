"""Mini demo de Banco Senior+: Observer y Mediator en la comunicación entre módulos (P-05).

Uso:
    python demo.py            corre los cuatro escenarios seguidos
    python demo.py --pausa    se detiene entre escenarios (para la presentación)

Cada línea de la traza dice qué patrón actúa: [OBSERVER] cuando se difunde un
hecho y [MEDIATOR] cuando un módulo le pide algo a otro por el mediador. La
sangría muestra qué llamada ocurre dentro de cuál.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from banco_senior.formato import pesos
from banco_senior.pension import HistorialConsignaciones
from banco_senior.sistema import armar_desde_csv, referencias_directas_entre_modulos

DATOS = Path(__file__).resolve().parent / "datos"
CELULAR_CAIDO = (
    "3001110002"  # Jorge Iván Ocampo: el operador simulado no le entrega mensajes
)


def titulo(texto: str) -> None:
    print()
    print("=" * 78)
    print(texto)
    print("=" * 78)


def nota(texto: str) -> None:
    print(f"  > {texto}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mini demo de Observer y Mediator en Banco Senior+"
    )
    parser.add_argument(
        "--pausa", action="store_true", help="esperar Enter entre escenarios"
    )
    args = parser.parse_args()

    def pausa() -> None:
        if args.pausa:
            input("\n  [Enter para continuar] ")

    titulo("BANCO SENIOR+ | Mini demo de Observer y Mediator (problema P-05)")
    print(
        "Datos sintéticos (Ley 1581 de 2012). Core bancario y operador de mensajería simulados."
    )
    print(
        "El celular de Jorge Iván Ocampo está caído: el operador no le entrega mensajes."
    )
    print()
    print("Armando el sistema (sistema.py):")
    sistema = armar_desde_csv(DATOS / "pensionados.csv", fallar_para={CELULAR_CAIDO})
    pausa()

    # ------------------------------------------------------------------------
    titulo("ESCENARIO 1. Día de pago: abono y aviso (US-201, US-301, RNF-006)")
    nota("ProcesadorConsignacion solo PUBLICA AbonoRegistrado (Observer).")
    nota(
        "Notificaciones pide el contacto y reporta el resultado POR EL MEDIADOR (Mediator)."
    )
    print()
    inicio = time.perf_counter()
    resultado = sistema.procesador.procesar(DATOS / "pagos_2026-11.csv")
    duracion = f"{time.perf_counter() - inicio:.2f}".replace(".", ",")
    avisos = [r for r in sistema.auditoria.registros if r.tipo.startswith("Aviso")]
    entregados = sum(1 for r in avisos if r.tipo == "Aviso enviado")
    jorge = sistema.core.saldo(sistema.core.cuenta_de("1001002"))
    print()
    print(
        f"Resultado: {len(resultado.abonos)} abonos y {len(resultado.diferencias)} diferencia "
        f"en {duracion} s (US-201 pide menos de 3 horas)."
    )
    for fila in resultado.diferencias:
        print(
            f"  Reporte de diferencias: {fila['nombre']} ({fila['documento']}) "
            f"no tiene cuenta en el banco."
        )
    print(
        f"  Avisos entregados: {entregados} de {len(avisos)}. El de Jorge falló, pero su abono de "
        f"{pesos(jorge)} sigue en la cuenta:"
    )
    print("  el error se quedó en Notificaciones y Auditoría lo registró.")
    pausa()

    # ------------------------------------------------------------------------
    titulo("ESCENARIO 2. Registro con código de verificación (US-101, US-102)")
    nota(
        "GestionUsuario y Notificaciones se piden cosas en AMBOS sentidos sin conocerse:"
    )
    nota("todo pasa por MediadorModulos (Mediator).")
    print()
    enviado = sistema.gestion.registrar(
        "1001005", "Ana Beatriz Gómez", "3001110005", "ana.gomez@correo.test"
    )
    print()
    print(
        f"Resultado: código de verificación {'enviado' if enviado else 'NO enviado'} "
        f"por el canal por defecto (SMS)."
    )
    pausa()

    # ------------------------------------------------------------------------
    titulo("ESCENARIO 3. Seguridad: cinco intentos fallidos de Luis (US-303, US-108)")
    nota(
        "GestionUsuario PUBLICA AccesoSospechoso al 4.º intento y CuentaBloqueada al 5.º (Observer)."
    )
    nota(
        "Notificaciones decide por su cuenta: alerta por dos canales y luego aviso de bloqueo."
    )
    print()
    for _ in range(5):
        sistema.gestion.intento_fallido("1001004")
    bloqueo = sistema.gestion.bloqueada_hasta("1001004")
    print()
    print(
        f"Resultado: cuenta de Luis bloqueada hasta las {bloqueo:%H:%M}; alertas por llamada "
        f"(su canal preferido) y por correo."
    )
    pausa()

    # ------------------------------------------------------------------------
    titulo(
        "ESCENARIO 4. Escalabilidad: se agrega el historial (US-203) sin tocar el procesador"
    )
    nota("Una sola línea nueva: publicador.suscribir(historial).")
    nota(
        "ProcesadorConsignacion no cambia y el historial empieza a recibir los abonos."
    )
    print()
    historial = HistorialConsignaciones()
    sistema.publicador.suscribir(historial)
    sistema.procesador.procesar(DATOS / "pagos_2026-12.csv")
    print()
    print(
        "Historial de Rosa Elena Martínez (1001001), del más reciente al más antiguo:"
    )
    for c in historial.consultar("1001001"):
        print(f"  {c.periodo}  {pesos(c.monto):>12}  {c.estado}")
    print(
        "  (El abono de 2026-11 no aparece: ocurrió antes de que el historial se suscribiera.)"
    )
    pausa()

    # ------------------------------------------------------------------------
    titulo("REGISTRO DE AUDITORÍA (RNF-006)")
    for r in sistema.auditoria.registros:
        print(f"  {r.momento:%H:%M:%S}  {r.tipo:<17} {r.documento}  {r.detalle}")

    titulo("RESUMEN DE LOS PATRONES")
    atendidas = sistema.mediador.solicitudes_atendidas
    detalle = ", ".join(f"{n} {tipo}" for tipo, n in sorted(atendidas.items()))
    print(
        f"  Observer: {sistema.publicador.eventos_publicados} eventos publicados. Quien publica "
        f"no conoce a ningún suscriptor."
    )
    print(f"  Mediator: {sum(atendidas.values())} solicitudes atendidas ({detalle}).")
    referencias = referencias_directas_entre_modulos(sistema)
    print(
        f"  Referencias directas entre módulos: {len(referencias)}. "
        f"Cada módulo solo conoce al mediador, al publicador o a un sistema externo."
    )


if __name__ == "__main__":
    main()
