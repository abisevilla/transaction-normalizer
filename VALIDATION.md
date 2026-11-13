# Validación de la implementación

Fecha: 13 de noviembre de 2026.

## Entorno y resultados

- macOS (Darwin), arm64; Python 3.13.18 en `.venv`.
- PySide6 6.12.0, simplejson 3.20.2 y pytest 9.2.0.
- Instalación editable del paquete completada con sus dependencias de desarrollo.
- Comando: `.venv/bin/python -m pytest -q`.
- Resultado: **50 pruebas aprobadas en 2,13 segundos**, sin advertencias de deprecación y con código de salida 0.
- La suite contiene 43 pruebas de dominio sin sesión gráfica y 7 pruebas de interfaz Qt.
- Medición adicional: 12 000 registros sintéticos válidos normalizados en **0,083 segundos**. Corresponde solo al motor, con datos ya en memoria; no incluye lectura, dibujo de tablas ni exportación. No constituye una garantía para otros equipos o archivos.

## Cobertura verificada

- Tres adaptadores y detección independiente del orden; fuentes incompletas, desconocidas y ambiguas.
- Precisión monetaria con Decimal, montos cero y negativos, precisión excesiva, booleanos y valores no finitos.
- Estados, monedas, identificadores y fechas; conversión UTC y rechazo de horas ambiguas o inexistentes.
- Errores por registro, acumulación de diagnósticos, advertencias de duplicidad y zona asumida.
- Métricas por estado y moneda; totales que incluyen todos los estados válidos.
- Lectura JSON, raíz inválida, archivo inexistente y exportación exacta sin montos textuales.
- Reporte de inválidas, selección de registros exportados y preservación del destino ante fallo de reemplazo.
- Ordenación numérica y selección después de filtrar en modelos Qt.
- Filtros combinados, comparación de detalles y actualización de métricas y conteos de pestañas según la vista filtrada; resumen del lote completo separado.
- Trabajador Qt con 12 000 registros, atención de eventos durante el proceso, cierre con trabajo activo y conservación del lote anterior tras una importación fallida.
- Exportación desde la ventana con alcance filtrado y aceptación/rechazo de sobrescritura, usando respuestas simuladas de los diálogos.

## Revisión visual y límites

Se generaron y revisaron capturas reales de widgets Qt con el complemento `offscreen`, con el ejemplo principal y el de inválidas, en tamaños de 1250 × 820 y 900 × 700. Se comprobó la disposición de controles, paleta, métricas, tablas y paneles de comparación. Los paneles y tablas permiten desplazamiento cuando el contenido supera el espacio disponible.

La validación no abrió una ventana nativa interactiva. Quedan pendientes la comprobación manual de los diálogos del sistema, navegación con teclado, foco y comportamiento con el escalado de pantalla del usuario. Las pruebas offscreen no sustituyen esas comprobaciones. El complemento emite mensajes informativos sobre fuentes y soporte de `propagateSizeHints`; no se observaron errores funcionales asociados.

Al ejecutar la primera suite se detectó un fallo de liberación de objetos Qt al cerrar el entorno de pruebas. Se corrigió la limpieza explícita de ventanas y eventos de eliminación diferida en las pruebas. La suite final terminó sin ese fallo.

## Comprobación manual recomendada

1. Activar `.venv` y ejecutar `python -m transaction_normalizer`.
2. Abrir `examples/transactions.json` con UTC y confirmar 3 válidas, USD 201.00 y EUR 99.99.
3. Filtrar EUR, ordenar y seleccionar A-77 para comparar los paneles.
4. Exportar la vista filtrada y el lote completo; comprobar los diálogos y el rechazo de sobrescritura.
5. Abrir `examples/invalid.json`, revisar las 5 inválidas y los duplicados conservados; exportar sus motivos.
6. Recorrer controles mediante teclado, comprobar el foco y redimensionar la ventana.

## Ampliación: archivo inicial de 500 transacciones

- Verificado JSON con exactamente 500 objetos: 300 válidas, 100 inválidas y 100 incompletas.
- Comprobados 102 SUCCESS, 99 FAILED y 99 PENDING; USD 21413.00 y EUR 43031.50 en transacciones válidas.
- Probada la clasificación de campos faltantes, nulos y vacíos, incluso junto con otros errores.
- Probadas exportaciones separadas de las tres categorías y carga automática al iniciar desde otro directorio.
- Revisada captura offscreen de la nueva pestaña Incompletas y de los controles de exportación.
- Construidos sdist y wheel en `/tmp/transaction-normalizer-dist`; ambos incluyen el archivo de 500 transacciones. La revisión nativa pendiente indicada anteriormente se mantiene.

## Corrección de filtros y conteos

- Verificado fuente `source_a` + moneda USD: 50 válidas, 17 inválidas y 13 incompletas (80 registros filtrados).
- Verificado fuente `source_a` + Sin moneda: 6 incompletas y cero registros en las otras categorías.
- Verificado fuente `source_c` + EUR: 100 válidas, 33 inválidas y 25 incompletas.
- Probados el resultado vacío, la restauración de las 500 transacciones al limpiar filtros y el reinicio de moneda al elegir una fuente incompatible.
- Revisada captura offscreen de la pestaña Incompletas con fuente y moneda combinadas; sus conteos coinciden con el resumen filtrado.
