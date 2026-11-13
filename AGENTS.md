# Instrucciones del repositorio

## Objetivo y alcance

Construir una aplicación de escritorio en Python con **PySide6 (Qt for Python)** para importar un archivo JSON con transacciones de múltiples fuentes, detectar su formato, normalizarlas y permitir su exploración interactiva. Estas instrucciones aplican a todo el repositorio.

La aplicación debe exponer datos y métricas de forma comprensible para una persona. Una solución basada únicamente en `print` o salida de consola no satisface el objetivo. La interfaz y los mensajes dirigidos al usuario deben estar en español.

## Contrato de entrada y salida

La entrada es un archivo UTF-8 cuyo elemento raíz es una lista de transacciones. Cada elemento debe ser un objeto; los elementos de otro tipo se registran como inválidos sin detener el procesamiento de los demás. Un JSON mal formado o una raíz que no sea una lista debe generar un error de importación claro.

La exportación de transacciones válidas debe ser una lista JSON con este esquema común, sin campos de diagnóstico adicionales:

```json
[
  {
    "id": "string",
    "amount": 99.99,
    "currency": "USD",
    "timestamp": "2025-03-10T14:22:00Z",
    "status": "SUCCESS",
    "source": "string"
  }
]
```

- `id`: cadena no vacía. Convertir identificadores enteros a texto; no aceptar booleanos como identificadores.
- `amount`: número JSON finito expresado en unidades mayores de la moneda, nunca una cadena ni un valor booleano.
- `currency`: código de moneda de tres letras mayúsculas reconocido por la configuración de monedas admitidas.
- `timestamp`: fecha y hora ISO-8601 con zona horaria explícita, normalizada a UTC y con sufijo `Z`.
- `status`: exclusivamente `SUCCESS`, `FAILED` o `PENDING`.
- `source`: identificador estable del adaptador que detectó la transacción.

## Fuentes y detección

Implementar un registro extensible de adaptadores. Cada adaptador debe declarar su nombre, firma de campos, unidades monetarias, formatos de fecha y mapa de estados. Separar detección, conversión y validación; no concentrar todas las reglas en la interfaz.

Soportar inicialmente estos formatos, derivados del ejemplo del proyecto:

| Fuente | Campos de identificación | Monto | Moneda | Fecha | Estado |
| --- | --- | --- | --- | --- | --- |
| `source_a` | `id`, `amount`, `currency`, `timestamp`, `status` | `amount` en unidades mayores, p. ej. `"100.50"` | `currency` | `timestamp` | `status` |
| `source_b` | `transaction_id`, `total`, `currency_code`, `created_at`, `state` | `total` entero en unidades menores; `10050` USD equivale a `100.50` USD | `currency_code` | `created_at` | `state` |
| `source_c` | `ref`, `amount`, `date`, `result` | `amount` con símbolo y coma decimal, p. ej. `"€99,99"` | inferida del símbolo inequívoco `€` → `EUR` | `date` | `result` |

Estos nombres describen formatos, no proveedores reales. No inventar nombres de empresas. Documentar la interpretación de unidades menores de `source_b` como una regla explícita del proyecto.

Detectar la fuente mediante firmas de campos, nunca por posición en la lista. Permitir detectar una fuente aun cuando le falte un campo obligatorio si sus campos distintivos la identifican sin ambigüedad, para informar el campo faltante. Si ninguna fuente coincide, registrar `UNKNOWN_SOURCE`; si varias coinciden, registrar `AMBIGUOUS_SOURCE`. No elegir silenciosamente la primera coincidencia.

## Reglas explícitas de normalización

### Montos y monedas

- Usar `decimal.Decimal` durante lectura, conversión, validación y agregación monetaria. Evitar cálculos financieros con `float` y dependencias del locale del sistema.
- Aceptar el punto decimal en `source_a`; aceptar el símbolo `€` y la coma decimal en `source_c`. Quitar espacios exteriores. Rechazar separadores ambiguos o formatos no declarados en el adaptador.
- Para `source_b`, exigir un entero de unidades menores y convertir según el exponente configurado para la moneda. USD y EUR tienen exponente 2. No asumir dos decimales para cualquier moneda futura.
- Normalizar códigos eliminando espacios exteriores y convirtiendo a mayúsculas. Admitir inicialmente USD y EUR mediante un registro extensible. Rechazar códigos no admitidos y símbolos ambiguos como `$` sin contexto suficiente.
- No realizar conversión entre divisas ni sumar monedas distintas en un único total.
- Rechazar valores vacíos, no numéricos, booleanos, `NaN` e infinitos. Admitir cero y valores negativos finitos; no deducir que una transacción es inválida únicamente por su signo.
- Rechazar precisión superior a la admitida por la moneda, sin redondeo silencioso. Serializar `Decimal` como número JSON preservando su valor monetario.

### Estados

Eliminar espacios exteriores y comparar sin distinguir mayúsculas de minúsculas. Mantener los mapas de equivalencias explícitos por adaptador; las equivalencias iniciales son:

| Estado normalizado | Valores de origen |
| --- | --- |
| `SUCCESS` | `completed`, `OK`, `success`, `SUCCESS` |
| `FAILED` | `failed`, `error`, `FAILED` |
| `PENDING` | `pending`, `processing`, `PENDING` |

Un valor desconocido o ausente es inválido. No convertir un estado desconocido a `PENDING` como valor por defecto.

### Fechas

- `source_a`: admitir `YYYY-MM-DD HH:mm:ss` e ISO-8601.
- `source_b`: interpretar `DD/MM/YYYY HH:mm`; `10/03/2025 14:22` significa 10 de marzo, no 3 de octubre.
- `source_c`: admitir ISO-8601 con `Z` o desplazamiento horario explícito.
- Convertir las fechas con zona a UTC. Para fechas sin zona, ofrecer una zona de origen configurable, con UTC como valor inicial visible, y registrar esa suposición en los detalles de procesamiento. Nunca usar implícitamente la zona local del equipo.
- Rechazar fechas imposibles o ambiguas por cambios de horario estacional si no hay una política explícita para resolverlas. No usar parsers heurísticos para adivinar día y mes.

## Transacciones inválidas y trazabilidad

Separar las transacciones inválidas de las válidas; no descartarlas silenciosamente ni incluir registros parciales en la exportación normalizada.

Conservar por cada entrada su índice original, datos originales, fuente detectada si existe, resultado normalizado si es válido y una lista de errores con código, campo y explicación legible. Mostrar todos los errores detectables del registro. Permitir exportar un reporte de inválidas con sus motivos.

No inventar identificadores, montos, monedas, fechas o estados para completar datos faltantes. No eliminar transacciones con identificadores repetidos automáticamente: conservarlas y mostrar una advertencia de duplicidad por `(source, id)`.

Un error de una transacción no debe interrumpir el lote. Los errores de lectura y escritura de archivos deben mostrarse sin bloquear ni cerrar la aplicación. No registrar datos financieros completos en logs por defecto.

## Métricas

Calcular a partir de un único resultado de procesamiento:

- Total procesadas: número de elementos de la lista de entrada.
- Total válidas y total inválidas; su suma debe coincidir con el total procesado.
- Conteo por `SUCCESS`, `FAILED` y `PENDING`, exclusivamente sobre transacciones válidas.
- Totales monetarios por moneda, exclusivamente sobre transacciones válidas, incluyendo todos los estados y etiquetando ese alcance claramente. Si se muestran totales solo de éxitos, presentarlos como una métrica separada.

Mostrar en el resumen principal las métricas de la vista filtrada y actualizar los conteos de las tres categorías, estados y sumas con cada filtro. Conservar un resumen separado del lote completo. No mezclar ambos alcances. Los filtros de fuente, moneda, estado y búsqueda se aplican a las tres categorías; en rechazadas usar solo los campos reconocibles del original sin normalizar el registro como válido. Adaptar las monedas disponibles a la fuente y permitir localizar registros sin moneda reconocible.

## Interfaz de escritorio

Usar widgets y modelos de PySide6. Como mínimo, incluir:

- Acción para abrir un archivo JSON mediante diálogo, con nombre del archivo y resultado de la importación visibles.
- Tarjetas o resumen de métricas del lote.
- Tabla de transacciones normalizadas con ordenación y filtros por fuente, estado, moneda y validez, además de búsqueda por identificador. La selección de validez puede implementarse mediante pestañas de válidas e inválidas.
- Vista de inválidas con motivos y acceso a sus datos originales.
- Panel de detalle que compare los datos originales y normalizados del registro seleccionado.
- Acciones para limpiar filtros, exportar válidas y exportar el reporte de inválidas. Indicar si cada exportación corresponde al lote completo o a la selección filtrada.
- Estados vacíos, progreso de procesamiento y mensajes de error útiles. Pedir confirmación antes de sobrescribir un archivo existente.

Usar `QAbstractTableModel` y `QSortFilterProxyModel` para tablas y filtros. Procesar lotes grandes fuera del hilo de la interfaz mediante trabajadores y señales de Qt; actualizar widgets únicamente desde el hilo principal. No dejar resultados parciales de una importación anterior mezclados con el lote nuevo.

### Paleta: Minimalista + Indigo

| Uso | Color |
| --- | --- |
| Superficies y tarjetas | `#FFFFFF` |
| Color principal, selección y acciones | `#4F46E5` |
| Texto secundario y elementos neutrales | `#64748B` |
| Fondo general | `#F8FAFC` |
| Éxito | `#16A34A` |

Centralizar los colores en un tema o una hoja de estilos. Priorizar tablas legibles, espaciado consistente, encabezados claros y navegación por teclado. Acompañar los estados con texto o iconos; no depender únicamente del color. Verificar contraste y foco visible, especialmente en textos pequeños y controles seleccionados.

## Organización y prácticas de desarrollo

- Mantener el dominio y la normalización independientes de Qt para poder probarlos sin iniciar la interfaz.
- Separar modelos de dominio, adaptadores de fuentes, validación, métricas, lectura/exportación y presentación. Una estructura inicial sugerida es `src/transaction_normalizer/` con módulos `domain`, `adapters`, `services` y `ui`, junto con `tests/` y `examples/`.
- Usar anotaciones de tipos y funciones pequeñas con responsabilidades claras. Centralizar reglas en los adaptadores y configuraciones, evitando duplicarlas en widgets.
- Declarar dependencias y versión de Python compatible en `pyproject.toml`. Documentar en `README.md` la instalación, ejecución, pruebas, reglas y supuestos.
- Incluir un archivo JSON de ejemplo con los tres formatos y otro con casos inválidos. No usar información financiera real en fixtures.
- Mantener el alcance en una aplicación local; no agregar backend, servicios externos o base de datos sin necesidad explícita.

## Verificación y criterios de aceptación

Agregar pruebas con `pytest` para detección de fuentes, montos exactos, monedas, estados, fechas y zonas horarias, datos incompletos, fuentes ambiguas/desconocidas, duplicados, métricas y exportación JSON. Cubrir archivos mal formados, raíz incorrecta y elementos que no sean objetos. Las pruebas del dominio no deben depender de una sesión gráfica.

El ejemplo de referencia debe producir tres transacciones válidas con estos resultados, usando UTC para las fechas sin zona:

| id | amount | currency | timestamp | status | source |
| --- | --- | --- | --- | --- | --- |
| `tx_001` | `100.50` | `USD` | `2025-03-10T14:22:00Z` | `SUCCESS` | `source_a` |
| `204` | `100.50` | `USD` | `2025-03-10T14:22:00Z` | `SUCCESS` | `source_b` |
| `A-77` | `99.99` | `EUR` | `2025-03-10T14:22:00Z` | `SUCCESS` | `source_c` |

Las métricas esperadas son 3 procesadas, 3 válidas, 0 inválidas, 3 éxitos, 0 fallidas y 0 pendientes; totales de USD 201.00 y EUR 99.99.

Antes de entregar una implementación, ejecutar las pruebas pertinentes y verificar manualmente la importación, los filtros, la comparación de detalles y las exportaciones en la interfaz. Informar qué se verificó y cualquier limitación real. Al modificar solo documentación, revisar su coherencia sin exigir pruebas de aplicación inexistentes.

## Carga inicial y categorías de calidad

Al ejecutar la aplicación, cargar automáticamente `src/transaction_normalizer/data/transactions_500.json` con UTC. Mantener ese archivo dentro del paquete y en las distribuciones instalables; resolver su ruta respecto al paquete, sin depender del directorio actual.

El archivo debe contener exactamente 500 transacciones sintéticas: 300 válidas, 100 inválidas y 100 incompletas, de las tres fuentes. La interfaz debe ofrecer conteos, pestañas, detalles y exportaciones para cada categoría, conservando los filtros correspondientes.

Clasificar como incompleto un registro de fuente reconocida con al menos un campo obligatorio ausente, nulo o textual vacío; usar el código `MISSING_FIELD`. Esta categoría tiene prioridad si además existen errores de valor. Clasificar como inválido un registro rechazado sin campos faltantes identificados, incluyendo fuentes desconocidas o ambiguas. No normalizar ni sumar importes de ninguna de estas dos categorías.

Las tres categorías de la interfaz son excluyentes. En el dominio, conservar `metrics.invalid` como total de rechazadas (incluidas las incompletas), agregar `metrics.incomplete` y exponer `metrics.invalid_only` para el conteo exclusivo de inválidas. Así se conserva la identidad válidas + rechazadas = procesadas.
