# Normalizador de transacciones

Aplicación local de escritorio en Python y PySide6 para importar transacciones JSON de distintas fuentes, normalizarlas y explorar sus datos y métricas. La interfaz está en español y utiliza la paleta Minimalista + Indigo.

## Instalación y ejecución

Se requiere Python **3.11–3.14** y un sistema con entorno gráfico compatible con Qt. Python 3.13 es la versión usada para la validación del proyecto. Python 3.15 queda excluido por compatibilidad de las dependencias gráficas.

Siga estos pasos en orden desde una terminal de macOS o Linux:

1. **Entre a la carpeta del repositorio.** Reemplace la ruta si lo guardó en otra ubicación:

   ```bash
   cd /Users/main/Documents/transaction-normalizer
   ```

2. **Cree el entorno virtual una sola vez**, usando Python 3.13 instalado en su equipo. Si ya existe `.venv`, continúe al paso 3:

   ```bash
   python3.13 -m venv .venv
   ```

3. **Active el entorno virtual** en cada terminal nueva:

   ```bash
   source .venv/bin/activate
   python --version
   ```

   La versión debe estar entre 3.11 y 3.14. En Windows PowerShell, use `.venv\Scripts\Activate.ps1` para activar el entorno.

4. **Instale las dependencias y el proyecto** la primera vez, o cuando cambien las dependencias:

   ```bash
   python -m pip install -e '.[dev]'
   ```

5. **Inicie la aplicación:**

   ```bash
   python -m transaction_normalizer
   ```

   También puede ejecutar `transaction-normalizer` desde el entorno virtual activo. La ventana carga automáticamente el archivo de 500 transacciones incluido en el repositorio; no necesita seleccionarlo con un diálogo. La zona inicial para fechas sin zona es UTC.

6. **Compruebe el resultado inicial:** 500 procesadas, 300 válidas, 100 inválidas y 100 incompletas. Ya puede explorar las tres pestañas y exportar cada categoría.

En ejecuciones posteriores basta con entrar al repositorio, activar `.venv` y ejecutar el comando del paso 5. Para terminar, cierre la ventana; puede salir del entorno con `deactivate`.

## Archivo inicial de 500 transacciones

El archivo está en **`src/transaction_normalizer/data/transactions_500.json`**. Es un JSON UTF-8 con exactamente 500 objetos sintéticos de las tres fuentes, mezclados de forma reproducible. Se incluye también al instalar el paquete, y se localiza respecto al paquete para que la carga no dependa del directorio desde el cual se ejecute el comando.

| Categoría | Cantidad | Tratamiento |
| --- | ---: | --- |
| Válidas | 300 | Se normalizan, participan en métricas por estado y moneda y se exportan con el contrato común. |
| Inválidas | 100 | Tienen datos presentes pero incorrectos; se separan con sus errores y se pueden exportar como reporte. |
| Incompletas | 100 | Falta un campo obligatorio, es `null` o es una cadena vacía; se separan con los campos faltantes y se pueden exportar como reporte. |

Las categorías de la interfaz son excluyentes: **300 + 100 + 100 = 500**. Si un registro tiene campos faltantes y otros erróneos, se clasifica como incompleto y conserva todos sus diagnósticos. Las fuentes desconocidas o ambiguas se clasifican como inválidas, porque no puede determinarse su contrato de campos obligatorios.

Para conservar la métrica de válidas frente a inválidas del dominio, `metrics.invalid` cuenta todas las rechazadas (200), incluidas las 100 incompletas. `metrics.incomplete` cuenta las incompletas y `metrics.invalid_only` las inválidas de la pestaña (100). Ninguna rechazada participa en sumas monetarias ni en conteos por estado.

Con UTC, el archivo inicial produce 102 `SUCCESS`, 99 `FAILED` y 99 `PENDING`; los totales de válidas son **USD 21413.00** y **EUR 43031.50**. Los datos son de demostración y no contienen información financiera real.

## Uso

1. Espere a que termine la carga automática y revise las métricas del lote completo.
2. Explore **Válidas**, **Inválidas** e **Incompletas**, que muestran su cantidad de registros. Ordene las columnas y combine fuente y búsqueda por identificador; estado y moneda se aplican solo a las válidas.
3. Seleccione una fila para comparar los originales con el resultado y revisar la categoría, errores y advertencias.
4. Use **Exportar válidas…**, **Exportar inválidas…** o **Exportar incompletas…**, eligiendo **Lote completo** o **Vista filtrada**. Cada botón exporta su propia categoría y utiliza sus filtros, aunque esa pestaña no esté activa.
5. Para procesar otro archivo, seleccione la zona de origen y pulse **Abrir JSON…** o use el atajo estándar de apertura. Para volver a cargar el inicial con otra zona, seleccione `src/transaction_normalizer/data/transactions_500.json` desde ese diálogo.

Los ejemplos pequeños `examples/transactions.json` y `examples/invalid.json` siguen disponibles para explorar casos concretos. Los duplicados se conservan con advertencias.

La aplicación conserva el lote anterior cuando una importación nueva falla. La lectura, la normalización y las exportaciones se ejecutan fuera del hilo de la interfaz. Cerrar durante un trabajo solicita su interrupción y espera a que termine de forma segura; la lectura o escritura de un archivo en curso puede demorar el cierre.

## Reglas de normalización

| Fuente | Identificador | Monto y moneda | Fecha | Estado |
| --- | --- | --- | --- | --- |
| `source_a` | `id` | `amount` en unidades mayores, `currency` | `timestamp`: fecha/hora convencional o ISO-8601 | `status` |
| `source_b` | `transaction_id` | `total` entero en unidades menores, `currency_code` | `created_at`: `DD/MM/YYYY HH:mm` | `state` |
| `source_c` | `ref` | `amount` como `€99,99`, moneda EUR | `date`: ISO-8601 con zona | `result` |

La detección utiliza campos distintivos declarados por adaptador. `amount` por sí solo no identifica una fuente. Un campo distintivo basta para reconocer un registro incompleto y explicar sus campos faltantes. Campos distintivos de varias fuentes generan `AMBIGUOUS_SOURCE`; ninguno genera `UNKNOWN_SOURCE`.

- USD y EUR son las monedas iniciales; sus códigos se recortan y pasan a mayúsculas. No hay conversión de divisas.
- La interpretación de `total` como unidades menores es una regla explícita del proyecto: `10050` USD → `100.50` USD.
- Los cálculos usan `Decimal`, incluidos lectura, conversión y métricas. Cero y montos negativos son válidos; los valores no finitos, booleanos, formatos ambiguos y precisión monetaria excesiva se rechazan.
- Estados, sin distinguir mayúsculas: `completed`, `OK` y `success` → `SUCCESS`; `failed` y `error` → `FAILED`; `pending` y `processing` → `PENDING`. Los nombres canónicos también se aceptan.
- Las fechas se normalizan a UTC. Las fechas sin zona usan la selección visible, nunca la zona del equipo. Las horas locales ambiguas o inexistentes se rechazan.
- Los errores individuales no interrumpen el lote. Un archivo mal formado, ilegible o cuya raíz no sea una lista no se importa.

El ejemplo pequeño `examples/transactions.json` produce **3 válidas**, **0 inválidas**, **3 SUCCESS**, **USD 201.00** y **EUR 99.99** al usar UTC.

## Exportaciones

Las válidas se exportan como una lista con exactamente `id`, `amount`, `currency`, `timestamp`, `status` y `source`. El monto es un número JSON y la fecha termina en `Z`. La serialización no pasa por `float`.

Los reportes de inválidas e incompletas son listas con `index` (base cero), `original`, `source` (o `null`), `category` (`INVALID` o `INCOMPLETE`) y `errors`. Cada error tiene `code`, `field` y `message`. Los valores originales no finitos, que no pertenecen a JSON estricto, se representan mediante objetos etiquetados, por ejemplo `{"$nonfinite": "NaN"}`. Esta representación se usa también en el panel de detalle.

La escritura utiliza un archivo temporal en el directorio de destino y un reemplazo atómico al terminar. La interfaz confirma la sobrescritura de archivos existentes.

## Estructura

```text
src/transaction_normalizer/
  domain.py          # contratos y métricas, sin Qt
  adapters.py        # firmas, conversiones y validación
  services.py        # procesamiento, lectura y exportación
  data/transactions_500.json  # lote inicial incluido en el paquete
  ui/
    models.py        # modelos y proxies de tablas
    window.py        # ventana, interacción y trabajadores
    theme.py         # paleta y estilos
  __main__.py        # inicio de la aplicación
examples/            # datos sintéticos
tests/              # pruebas de dominio e integración Qt
```

Para agregar una fuente, declare otro `Adapter` con sus campos distintivos, correspondencia de campos y estados, amplíe sus conversiones si es necesario y agregue casos de prueba. Las monedas y sus exponentes se declaran en `CURRENCIES`.

## Pruebas

```bash
python -m pytest -q
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui.py -q
```

Las pruebas del dominio no requieren Qt ni sesión gráfica. Las pruebas de interfaz crean una aplicación Qt en modo `offscreen`: verifican ordenación numérica, selección después de filtrar, detalles, métricas y procesamiento de un lote sintético de 12 000 registros. La revisión de interacción nativa, diálogos y apariencia en pantalla debe realizarse en una sesión gráfica; consulte `VALIDATION.md` para los resultados de esta entrega.

La carga JSON conserva el archivo completo en memoria, junto con originales y resultados; no es un importador de flujo para archivos ilimitados. No incluye backend, base de datos, conversión de divisas ni empaquetado instalable por sistema operativo.
