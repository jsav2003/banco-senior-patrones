"""Prototipo de Banco Senior+ con los patrones Observer y Mediator.

Resuelve el problema de diseño P-05 del Taller de Patrones de Diseño: los
módulos de Banco Senior+ deben comunicarse sin quedar acoplados entre sí.

Dónde está cada patrón:
    observer.py         Patrón Observer: Suscriptor y PublicadorEventos.
    mediator.py         Patrón Mediator: solicitudes, Mediador, Modulo y
                        MediadorModulos.
    eventos.py          Los hechos que se publican (AbonoRegistrado,
                        CuentaBloqueada y AccesoSospechoso).

Módulos del sistema que usan los patrones:
    pension.py          ProcesadorConsignacion (publica) e
                        HistorialConsignaciones (suscriptor nuevo).
    gestion_usuario.py  GestionUsuario (publica y es componente del mediador).
    notificaciones.py   Notificaciones (suscriptor y componente del mediador).
    auditoria.py        Auditoria (suscriptor y componente del mediador).

Apoyo:
    simuladores.py      Core bancario y operador de mensajería simulados.
    sistema.py          Arma el sistema y conecta los dos patrones.
    traza.py            Traza en consola para seguir la demo.

Todos los datos son sintéticos (Ley 1581 de 2012).
"""
