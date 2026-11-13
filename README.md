# Banco Senior+: prototipo de Observer y Mediator

Taller de Patrones de Diseño, parte 3 (Diseño Detallado de Software, Universidad de San Buenaventura Cali).
Integrantes: Juan Sebastián Arévalo Vásquez y María Fernanda Giraldo Duque.

El prototipo aplica **Observer** y **Mediator** al problema de diseño **P-05 (comunicación entre módulos)**
en la funcionalidad de consignación de la pensión y aviso del abono (US-201, US-301 y US-302). También cubre el
registro con código de verificación (US-101 y US-102), las alertas de seguridad (US-303 y US-108) y el
historial de consignaciones (US-203).

## Cómo correrlo

Requiere Python 3.8 o superior. No usa librerías externas (la interfaz gráfica usa Tkinter, que viene con Python).

```
python app.py             # interfaz gráfica (Tkinter)
python demo.py            # los cuatro escenarios seguidos
python demo.py --pausa    # se detiene entre escenarios (para la presentación)
python -m unittest -v     # 25 pruebas automatizadas
```

En Windows, si `python` no responde, use `py` (por ejemplo, `py demo.py`). Los comandos se ejecutan desde
esta carpeta.

## Regla para elegir el patrón

| Si un módulo...                                   | Se usa   | Ejemplo                                   |
|---------------------------------------------------|----------|-------------------------------------------|
| avisa un **hecho** que ya ocurrió (uno a muchos)  | Observer | `AbonoRegistrado`, `CuentaBloqueada`      |
| **pide** algo a otro módulo (puede esperar respuesta) | Mediator | `ConsultarContacto`, `EnviarCodigo`   |

## Dónde está cada patrón

| Patrón   | Papel (Refactoring Guru)    | Clase en Banco Senior+                               | Archivo                     |
|----------|-----------------------------|------------------------------------------------------|-----------------------------|
| Observer | Notificador (publisher)     | `PublicadorEventos`                                  | `banco_senior/observer.py`  |
| Observer | Interfaz suscriptora        | `Suscriptor`                                         | `banco_senior/observer.py`  |
| Observer | Suscriptores concretos      | `Notificaciones`, `Auditoria`, `HistorialConsignaciones` | `notificaciones.py`, `auditoria.py`, `pension.py` |
| Observer | Clientes que publican       | `ProcesadorConsignacion`, `GestionUsuario`           | `pension.py`, `gestion_usuario.py` |
| Observer | Mensajes (eventos)          | `AbonoRegistrado`, `CuentaBloqueada`, `AccesoSospechoso` | `banco_senior/eventos.py` |
| Mediator | Interfaz mediadora          | `Mediador`                                           | `banco_senior/mediator.py`  |
| Mediator | Mediador concreto           | `MediadorModulos`                                    | `banco_senior/mediator.py`  |
| Mediator | Componentes                 | `Modulo` y sus subclases `GestionUsuario`, `Notificaciones`, `Auditoria` | `mediator.py` y los módulos |
| Mediator | Mensajes (solicitudes)      | `ConsultarContacto`, `EnviarCodigo`, `RegistrarResultado` | `banco_senior/mediator.py` |
| Ambos    | Conexión de los patrones    | `armar_sistema()`                                    | `banco_senior/sistema.py`   |

## Diagramas de arquitectura (C4)

La carpeta `docs/arquitectura` tiene el código C4-PlantUML de los tres diagramas de la sección 5 del trabajo
final, cada uno con su imagen:

| Diagrama                          | Nivel C4 | Código                 | Imagen                |
|-----------------------------------|----------|------------------------|-----------------------|
| Contexto                          | 1        | `c4_contexto.puml`     | `c4_contexto.png`     |
| Contenedores                      | 2        | `c4_contenedores.puml` | `c4_contenedores.png` |
| Componentes de la API del sistema | 3        | `c4_componentes.puml`  | `c4_componentes.png`  |

Los componentes del nivel 3 corresponden a las clases de este prototipo:

| Componente C4                       | Clases del prototipo                                |
|-------------------------------------|-----------------------------------------------------|
| Controlador de Gestión de Usuario   | `GestionUsuario`                                    |
| Controlador de Pensión y Productos  | `ProcesadorConsignacion`, `HistorialConsignaciones` |
| Controlador de Notificaciones       | `Notificaciones`                                    |
| Controlador de Auditoría            | `Auditoria`                                         |
| Controlador de Mediador de módulos  | `Mediador`, `MediadorModulos`, `Modulo`             |
| Controlador Publicador de eventos   | `Suscriptor`, `PublicadorEventos`                   |

Para volver a generar las imágenes desde esta carpeta (requiere Java; en Linux y macOS, también Graphviz):

```
java -jar plantuml.jar -tpng docs/arquitectura/*.puml
```

También se puede pegar el código en https://www.plantuml.com/plantuml. Las imágenes se generaron con
PlantUML 1.2026.10, que incluye C4-PlantUML 2.14.0. El título «Leyenda» necesita C4-PlantUML 2.11 o superior;
con una versión anterior la leyenda sale con su título en inglés.

## Interfaz gráfica

`python app.py` abre una interfaz de escritorio (Tkinter) que crea el backend con `armar_desde_csv` y delega
todo en las instancias reales de `Sistema`: no reimplementa los patrones, y `observer.py` y `mediator.py` no
se modifican. Las operaciones corren en un hilo de trabajo para no bloquear la ventana.

- **Inicio:** indicadores de la sesión (clicables) y accesos a los cuatro escenarios.
- **Usuarios:** pensionados cargados, registro con código, intentos fallidos y un panel de detalle por
  pensionado (saldo, abonos, avisos, historial y auditoría).
- **Pensión y productos:** procesa los CSV de pagos o un pago manual (se arma un CSV de una fila para
  `ProcesadorConsignacion.procesar`); muestra saldos y diferencias de conciliación.
- **Notificaciones y Auditoría:** envíos del operador simulado y registros de `Auditoria`, con filtro por tipo.
- **Patrones:** diagramas de Observer y Mediator que se iluminan paso a paso leyendo la traza del backend, con
  controles para registrar un pago, simular un intento fallido, registrar un usuario de prueba y suscribir o
  retirar `HistorialConsignaciones` en caliente.
- **Escenarios:** los cuatro flujos de la demo con su traza (`[OBSERVER]` y `[MEDIATOR]`).
- **Reiniciar sistema:** botón de la barra superior que crea un backend limpio para repetir los escenarios.

## Escenarios de la demo

| Escenario | Qué muestra | Requisitos |
|-----------|-------------|------------|
| 1. Día de pago | `ProcesadorConsignacion` abona y publica `AbonoRegistrado`; `Notificaciones` pide el contacto y reporta el resultado por el mediador. El aviso de Jorge falla y su abono no se revierte. | US-201, US-301, RNF-006 |
| 2. Registro con código | `GestionUsuario` y `Notificaciones` se piden cosas en ambos sentidos sin conocerse. | US-101, US-102 |
| 3. Seguridad | Al 4.º intento fallido se publica `AccesoSospechoso` (alerta por dos canales) y al 5.º, `CuentaBloqueada`. | US-303, US-108 |
| 4. Escalabilidad | Se suscribe `HistorialConsignaciones` sin tocar `ProcesadorConsignacion`. | US-203 |

## Estructura

```
banco_senior_patrones/
├── app.py                  punto de entrada de la interfaz gráfica
├── demo.py                 mini demo por consola
├── ui/                     interfaz de escritorio Tkinter (solo presentación)
├── banco_senior/
│   ├── observer.py         patrón Observer
│   ├── mediator.py         patrón Mediator
│   ├── eventos.py          hechos que se publican
│   ├── pension.py          Pensión y Productos (procesador e historial)
│   ├── gestion_usuario.py  Gestión de Usuario
│   ├── notificaciones.py   Notificaciones
│   ├── auditoria.py        auditoría (RNF-006)
│   ├── simuladores.py      core bancario y operador de mensajería simulados
│   ├── sistema.py          arma el sistema y conecta los patrones
│   ├── formato.py          formato de pesos
│   └── traza.py            traza de la demo
├── datos/                  pensionados y archivos de pago sintéticos
├── tests/                  pruebas de Observer, de Mediator y de los flujos
├── evidencias/             salida de la demo y de las pruebas
└── docs/arquitectura/      diagramas C4 de contexto, contenedores y componentes (.puml y .png)
```

## Datos y limitaciones

- Todos los datos son sintéticos (Ley 1581 de 2012). Los correos usan el dominio reservado `.test`.
- El core bancario y el operador de mensajería están simulados; en producción irían detrás de adaptadores (P-04).
- Todo vive en memoria y los eventos se entregan en el mismo hilo. En la arquitectura (`docs/arquitectura`), la
  API del sistema corre en varias réplicas para procesar 50.000 transacciones en menos de 3 horas (RNF-004), y
  Notificaciones guarda cada aviso como pendiente en la base de datos para enviarlo en segundo plano con
  reintentos (P-06).
- No hay cifrado (RNF-003) ni autenticación real: el prototipo se limita a los patrones. La interfaz gráfica
  solo muestra y dispara las operaciones del backend.

## Uso de inteligencia artificial

El código se generó con Claude (Anthropic) a partir del diagrama de clases y de las fichas de la parte 2 del
taller. Se revisó contra los requisitos de Banco Senior+ y se comprobó con las pruebas automatizadas. Los
diagramas C4 de `docs/arquitectura` también se elaboraron con Claude y se revisaron contra la sección 5 del
trabajo final. La interfaz gráfica (`ui/` y `app.py`) también se elaboró con Claude y se comprobó ejecutando
los escenarios.
