# Banco Senior+ — prototipo con Observer, Mediator e interfaz gráfica

Proyecto académico de Diseño Detallado de Software. Incluye el prototipo Python original, sus datos sintéticos, los cuatro escenarios de demostración, 25 pruebas automatizadas y una interfaz de escritorio Tkinter integrada.

## Requisitos

- Python 3.8 o superior.
- Tkinter (incluido en la mayoría de instalaciones de Python; en algunas distribuciones Linux se instala como paquete `python3-tk`).
- No requiere librerías Python externas.

## Ejecutar la interfaz

Desde la carpeta raíz del proyecto:

```bash
python app.py
```

En Windows también puedes usar `py app.py`.

## Ejecutar la demostración original y las pruebas

```bash
python demo.py
python demo.py --pausa
python -m unittest -v
```

## Interfaz gráfica

- **Inicio:** indicadores calculados a partir del estado de la sesión y accesos a los escenarios.
- **Usuarios:** consulta los pensionados cargados, registra personas mediante `GestionUsuario.registrar`, permite cambiar el canal preferido y simular intentos fallidos.
- **Pensión y productos:** procesa los CSV con `ProcesadorConsignacion.procesar`; consulta saldos desde `CoreBancarioSimulado`.
- **Notificaciones:** muestra los envíos del `OperadorMensajeriaSimulado` y permite cambiar el canal preferido a través de `Notificaciones.preferir_canal`.
- **Auditoría:** consulta los objetos `RegistroAuditable` de `Auditoria.registros` y filtra por tipo.
- **Patrones (laboratorio en vivo):** dos diagramas, Observer y Mediator, que se iluminan paso a paso leyendo la traza del backend (la animación espera en cola hasta que se abre esta página). Desde aquí se puede registrar un pago, simular un intento fallido, registrar un usuario de prueba y suscribir o retirar `HistorialConsignaciones` en caliente. La velocidad de la animación es ajustable.
- **Pago manual:** en *Pensión y productos* y en *Patrones*. Genera un CSV de una fila y se lo entrega a `ProcesadorConsignacion.procesar`; un documento sin cuenta en el banco va al reporte de diferencias.
- **Detalle por pensionado:** en *Usuarios*, al seleccionar una fila se ven saldo, abonos, avisos, historial y auditoría de esa persona. Los indicadores del inicio son clicables y el doble clic en un saldo abre el detalle.
- **Reiniciar sistema:** botón de la barra superior; crea un backend nuevo para repetir los escenarios.
- **Escenarios:** ejecuta los cuatro flujos originales y presenta la traza de consola del backend, distinguiendo `[OBSERVER]` y `[MEDIATOR]`.

## Integración y preservación de arquitectura

La interfaz crea el backend mediante `armar_desde_csv` de `banco_senior.sistema`, y delega las operaciones en las instancias reales de `Sistema`. No contiene reglas que reimplementen los patrones. Los archivos `banco_senior/observer.py` y `banco_senior/mediator.py` se conservan sin modificaciones: `PublicadorEventos`, `Suscriptor`, `Mediador`, `MediadorModulos`, las solicitudes y sus rutas siguen siendo los del prototipo original.

La traza del backend se captura durante las operaciones ejecutadas en segundo plano y se presenta en la interfaz. Las operaciones de la interfaz se ejecutan en un hilo de trabajo para evitar bloquear la ventana.

## Los cuatro escenarios originales

1. **Día de pago:** procesa `datos/pagos_2026-11.csv`; cuatro abonos, un registro en diferencias y fallo simulado de notificación a Jorge. El abono no se revierte.
2. **Registro con código:** registra a Ana Beatriz Gómez; `GestionUsuario` solicita `EnviarCodigo` mediante `MediadorModulos`.
3. **Seguridad:** registra cinco intentos fallidos de Luis; Observer publica `AccesoSospechoso` al cuarto y `CuentaBloqueada` al quinto.
4. **Escalabilidad:** suscribe `HistorialConsignaciones` y procesa `datos/pagos_2026-12.csv` sin modificar `ProcesadorConsignacion`.

Se pueden ejecutar desde la sección **Escenarios** o desde los accesos rápidos del inicio.

## Datos y límites conocidos del prototipo

Todos los datos son sintéticos y viven en memoria. El core bancario y el operador de mensajería son simuladores. El proyecto no implementa autenticación real, persistencia, cifrado ni conexión con servicios bancarios externos. La interfaz refleja estas limitaciones y no presenta el prototipo como un sistema bancario productivo.
