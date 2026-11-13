# Plan de implementación

Implementar la aplicación de escritorio definida en `AGENTS.md`. Este documento organiza el trabajo; las reglas funcionales y los contratos de datos se mantienen en `AGENTS.md`.

Estado: implementación completada y suite automatizada aprobada (50 pruebas). Se revisaron capturas de la interfaz en modo offscreen. La comprobación manual de diálogos nativos y navegación con teclado en una sesión gráfica sigue pendiente; consulte `VALIDATION.md`.

## 1. Preparar el proyecto

- [x] Crear `pyproject.toml` con Python 3.11 o superior, PySide6, `simplejson` para serializar `Decimal` como números JSON y `pytest` como dependencia de desarrollo.
- [x] Crear el paquete `src/transaction_normalizer/` con punto de entrada `python -m transaction_normalizer`.
- [x] Organizar módulos de dominio, adaptadores, servicios e interfaz; agregar `tests/` y `examples/`.
- [x] Crear un README inicial con instalación en entorno virtual y comandos de ejecución y pruebas.

**Verificación:** el paquete se instala y su punto de entrada abre una ventana mínima de PySide6. Las pruebas pueden importar el dominio sin importar Qt.

## 2. Definir los modelos y las reglas compartidas

- [x] Crear modelos tipados para transacción normalizada, error de validación, advertencia, resultado por registro, resultado del lote y métricas.
- [x] Usar `Decimal` para montos y `datetime` con zona para fechas; definir los tres estados permitidos mediante un enum.
- [x] Definir un registro de monedas con USD y EUR y sus exponentes.
- [x] Crear utilidades de validación de identificadores, montos, moneda, estados y fechas, con códigos de error estables y mensajes en español.
- [x] Definir configuración de zona de origen con UTC como valor inicial. Detectar horas ambiguas o inexistentes mediante `zoneinfo`, sin depender de la zona del equipo.
- [x] Mantener separados los errores que invalidan un registro y las advertencias que permiten conservarlo.

**Verificación:** pruebas de precisión monetaria, booleanos, valores no finitos, negativos y cero, campos vacíos, estados desconocidos, fechas imposibles y cambios de horario estacional.

## 3. Implementar detección y adaptadores

- [x] Definir una interfaz de adaptador con detección, conversión y validación independientes.
- [x] Crear `source_a`: montos en unidades mayores, moneda explícita y fecha convencional o ISO-8601.
- [x] Crear `source_b`: identificador entero convertido a texto, monto entero en unidades menores y fecha día/mes/año.
- [x] Crear `source_c`: referencia textual, monto con símbolo de euro y coma decimal y fecha ISO-8601 con zona.
- [x] Declarar firmas distintivas explícitas y probar sus combinaciones. Permitir reconocer registros incompletos; varias firmas coincidentes producen `AMBIGUOUS_SOURCE` y ninguna produce `UNKNOWN_SOURCE`.
- [x] Definir mapas de estados por adaptador y recopilar todos los errores de campos que puedan validarse de forma independiente.
- [x] Guardar la zona asumida para fechas sin zona en los detalles del procesamiento, fuera del contrato exportado.

**Verificación:** los tres ejemplos producen exactamente los identificadores, montos, monedas, fechas, estados y fuentes de `AGENTS.md`. La detección es independiente del orden del lote y no selecciona un adaptador arbitrariamente.

## 4. Construir importación, procesamiento y métricas

- [x] Leer JSON UTF-8 preservando los números decimales como `Decimal`; identificar valores no finitos para rechazarlos con diagnósticos por registro.
- [x] Distinguir errores de archivo o estructura global de los errores individuales. Rechazar una raíz que no sea una lista.
- [x] Procesar cada elemento conservando índice y contenido original, incluso cuando no sea un objeto.
- [x] Separar válidas e inválidas y detectar duplicados por `(source, id)` sin eliminarlos.
- [x] Calcular las métricas desde el resultado del lote: procesadas, válidas, inválidas, conteos por estado y sumas por moneda sobre todas las válidas.
- [x] Exponer progreso mediante una función de notificación independiente de Qt para conectar posteriormente con el trabajador de la interfaz.
- [x] Crear ejemplos sintéticos válidos e inválidos, incluyendo registros incompletos, ambiguos y duplicados.

**Verificación:** cada elemento de entrada tiene un resultado; válidas + inválidas = procesadas. El lote de referencia produce 3 válidas, USD 201.00 y EUR 99.99. Un registro incorrecto no detiene los demás.

## 5. Implementar las exportaciones

- [x] Exportar válidas con únicamente los seis campos del contrato, fechas UTC con `Z` y montos como números JSON exactos.
- [x] Exportar inválidas con índice, original, fuente disponible y lista de errores con código, campo y descripción.
- [x] Permitir seleccionar lote completo o vista filtrada de manera explícita; documentar el esquema del reporte de inválidas y su representación de valores no compatibles con JSON estricto.
- [x] Escribir mediante un archivo temporal en el mismo directorio y reemplazar el destino al terminar, para reducir el riesgo de archivos incompletos.
- [x] Propagar errores de permisos, disco o ruta a la capa de presentación sin perder el lote cargado.

**Verificación:** releer los archivos exportados y comprobar esquema, precisión y alcance. Probar un fallo de escritura y confirmar que no deja una exportación parcial como resultado final.

## 6. Construir la interfaz PySide6

- [x] Crear ventana principal con apertura de JSON, nombre del archivo, selector visible de zona de origen y acciones de exportación.
- [x] Centralizar la paleta: blanco `#FFFFFF`, indigo `#4F46E5`, gris `#64748B`, fondo `#F8FAFC` y éxito `#16A34A`.
- [x] Incorporar tarjetas de métricas del lote y totales separados por moneda, identificados como correspondientes a todas las válidas.
- [x] Implementar modelos `QAbstractTableModel` y proxies `QSortFilterProxyModel` para válidas e inválidas, con ordenación numérica y cronológica correcta.
- [x] Agregar pestañas de validez, filtros por fuente, estado y moneda, búsqueda por identificador y acción para limpiar filtros. En inválidas, usar los campos disponibles y deshabilitar filtros que no sean aplicables.
- [x] Mostrar un panel de detalle con original, normalizado, errores, advertencias y zona asumida; resolver la selección desde el proxy hacia el registro original.
- [x] Agregar estados vacíos, mensajes de error, controles accesibles por teclado y foco visible. Los estados deben incluir texto además del color.
- [x] Presentar diálogos de exportación con alcance explícito y confirmación antes de sobrescribir.

**Verificación:** importar los ejemplos y revisar búsqueda, filtros combinados, ordenación, selección y comparación de datos. Los importes se ordenan por su valor, no por su texto. Las métricas principales y los conteos de pestañas se actualizan al filtrar, mientras el resumen del lote permanece separado.

## 7. Integrar trabajo en segundo plano

- [x] Ejecutar lectura y normalización en un trabajador con `QThread` y señales de progreso, finalización y error. Ejecutar exportaciones grandes fuera del hilo principal.
- [x] Actualizar widgets y modelos exclusivamente desde el hilo principal.
- [x] Mantener un solo trabajo activo y deshabilitar acciones incompatibles durante su ejecución.
- [x] Reemplazar el resultado visible de forma completa cuando termine una importación exitosa. Si falla, conservar el lote anterior y dejar claro que la nueva importación no se cargó.
- [x] Manejar el cierre de la ventana sin destruir hilos activos; incorporar cancelación cooperativa entre registros si hace falta para un cierre seguro.
- [x] Agrupar notificaciones de progreso para evitar saturar el hilo de la interfaz.

**Verificación:** usar un lote sintético grande y confirmar que la ventana responde, el progreso avanza y no aparecen registros de distintos lotes mezclados. Comprobar cierre y errores durante el trabajo. Registrar el tamaño del lote y el entorno usado, sin prometer un límite de rendimiento no medido.

## 8. Validar y documentar la entrega

- [x] Ejecutar la suite `pytest` de dominio, adaptadores, importación, métricas y exportación.
- [x] Añadir pruebas de integración de modelos y filtros Qt cuando permitan verificar riesgos reales como selección incorrecta después de ordenar.
- [ ] Completar la revisión manual del recorrido en una sesión gráfica nativa. El procesamiento, los filtros, el detalle, la exportación y su confirmación tienen cobertura automatizada offscreen.
- [ ] Completar la revisión de foco y navegación con teclado en una sesión gráfica nativa. Se revisaron visualmente capturas de textos, tablas y redimensionado a 1250 × 820 y 900 × 700.
- [x] Completar README con reglas, ejemplos, estructura, comandos, alcance de las exportaciones y limitaciones verificadas.
- [x] Informar pruebas ejecutadas y resultados, incluyendo cualquier comprobación gráfica que no haya podido realizarse.

**Aceptación final:** se cumplen todos los criterios de `AGENTS.md`, la aplicación permite explorar las transacciones desde una interfaz de escritorio y los archivos exportados respetan el contrato común.

## Orden y dependencias

La secuencia principal es **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8**. Las pruebas se agregan junto con cada etapa, sin posponerlas hasta el final. La interfaz consume los servicios y resultados ya definidos; no vuelve a implementar reglas de normalización.

El primer hito funcional comprende las etapas 1 a 5: normalización y exportación verificadas. El segundo comprende las etapas 6 y 7: recorrido completo de escritorio. La etapa 8 cierra la entrega con revisión visual y documentación.

## Ampliación: lote inicial y control de categorías

- [x] Incluir un archivo JSON de 500 registros en `src/transaction_normalizer/data/`, con 300 válidas, 100 inválidas y 100 incompletas.
- [x] Cargarlo automáticamente al iniciar, independientemente del directorio de ejecución, e incluirlo en el paquete distribuido.
- [x] Clasificar los campos obligatorios ausentes, nulos o vacíos como incompletos, conservando todos los diagnósticos.
- [x] Agregar pestaña, conteo y exportación propios para las incompletas, con categorías excluyentes en pantalla.
- [x] Documentar instrucciones secuenciales de instalación, ejecución y uso del lote inicial en el README.
- [x] Verificar las cantidades, métricas, reportes, carga automática y contenido del paquete construido.

## Corrección: filtros combinados y métricas visibles

- [x] Actualizar conteos de válidas, inválidas e incompletas y métricas del resumen con los filtros activos.
- [x] Conservar un resumen del lote completo separado y etiquetar ambos alcances.
- [x] Permitir filtrar las tres categorías por fuente, moneda y estados reconocibles del original.
- [x] Ajustar opciones de moneda a la fuente y ofrecer Sin moneda para datos no reconocibles.
- [x] Probar combinaciones de fuente y moneda, resultados vacíos y restauración al limpiar filtros.
