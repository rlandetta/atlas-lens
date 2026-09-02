# Export Engine Missing Photo Audit

Fecha: 2026-08-18

## Alcance

Auditoria de solo lectura para el caso reportado:

```text
Cobertura: 20260818-CAMPAMENTO-SIYUAN-EC
Foto reportada: CAMPAMENTO-SIYUAN-6623(1).jpg
Sintoma: se esperaban 9 fotografias y el DOCX genero 8; reintentos posteriores tampoco incorporaron esa foto, aunque otras fotos si exportaron.
```

No se modifico codigo, fotografias, permisos, coberturas, exportaciones, servicios, deploy ni Git.

## Cobertura Localizada

Cobertura:

```text
ID: cov-20260818165423-7419
Nombre: CAMPAMENTO-SIYUAN
Fecha evento: 2026-08-17
Fecha envio: 2026-08-18
Ciudad: Quito
Pais: Ecuador
Fotografo: Ricardo Landeta
Agencia: XINHUA
```

La cobertura actualmente tiene 12 fotografias asociadas en `instance/lens_coverages.json`.

## Fotografias Actualmente Asociadas

| Orden | ID | Archivo | Storage path | Caption |
|---:|---|---|---|---|
| 1 | `ec8390c7-fc95-4a84-ba28-7594e309da87` | `CAMPAMENTO-SIYUAN-5688.jpg` | `coverages/cov-20260818165423-7419/ec8390c7-fc95-4a84-ba28-7594e309da87_CAMPAMENTO-SIYUAN-5688.jpg` | Presente, 329 caracteres |
| 2 | `a1eb0d3d-c167-4adb-9b2d-6f8ced4aaafe` | `CAMPAMENTO-SIYUAN-6218.jpg` | `coverages/cov-20260818165423-7419/a1eb0d3d-c167-4adb-9b2d-6f8ced4aaafe_CAMPAMENTO-SIYUAN-6218.jpg` | Presente, 329 caracteres |
| 3 | `ee136727-0014-4135-9148-d15c3b838662` | `CAMPAMENTO-SIYUAN-6564.jpg` | `coverages/cov-20260818165423-7419/ee136727-0014-4135-9148-d15c3b838662_CAMPAMENTO-SIYUAN-6564.jpg` | Presente, 329 caracteres |
| 4 | `6fd0b1a3-70b0-4d01-bb33-6565b388f326` | `CAMPAMENTO-SIYUAN-6440.jpg` | `coverages/cov-20260818165423-7419/6fd0b1a3-70b0-4d01-bb33-6565b388f326_CAMPAMENTO-SIYUAN-6440.jpg` | Presente, 329 caracteres |
| 5 | `75740b86-45fd-449d-9bbf-aa310327ffd2` | `CAMPAMENTO-SIYUAN-7654.jpg` | `coverages/cov-20260818165423-7419/75740b86-45fd-449d-9bbf-aa310327ffd2_CAMPAMENTO-SIYUAN-7654.jpg` | Presente, 329 caracteres |
| 6 | `dfff887d-c475-4318-a126-d4c6c27af2d4` | `CAMPAMENTO-SIYUAN-5955.jpg` | `coverages/cov-20260818165423-7419/dfff887d-c475-4318-a126-d4c6c27af2d4_CAMPAMENTO-SIYUAN-5955.jpg` | Presente, 329 caracteres |
| 7 | `db33428b-1dce-4249-918f-3ac712e3f3a0` | `CAMPAMENTO-SIYUAN-7793.jpg` | `coverages/cov-20260818165423-7419/db33428b-1dce-4249-918f-3ac712e3f3a0_CAMPAMENTO-SIYUAN-7793.jpg` | Presente, 329 caracteres |
| 8 | `b06fd138-4c6f-4731-87bd-11bc6159f633` | `CAMPAMENTO-SIYUAN-7883.jpg` | `coverages/cov-20260818165423-7419/b06fd138-4c6f-4731-87bd-11bc6159f633_CAMPAMENTO-SIYUAN-7883.jpg` | Presente, 329 caracteres |
| 9 | `2358caf1-324c-488c-8bb3-ff508f1818bd` | `CAMPAMENTO-SIYUAN-5726.jpg` | `coverages/cov-20260818165423-7419/2358caf1-324c-488c-8bb3-ff508f1818bd_CAMPAMENTO-SIYUAN-5726.jpg` | Presente, 329 caracteres |
| 10 | `10fb7d4e-9bc6-401b-b32c-2f997aa156cb` | `CAMPAMENTO-SIYUAN-5643.jpg` | `coverages/cov-20260818165423-7419/10fb7d4e-9bc6-401b-b32c-2f997aa156cb_CAMPAMENTO-SIYUAN-5643.jpg` | Presente, 329 caracteres |
| 11 | `0f59363d-d1f1-4574-9977-532cea2a1086` | `CAMPAMENTO-SIYUAN-5716.jpg` | `coverages/cov-20260818165423-7419/0f59363d-d1f1-4574-9977-532cea2a1086_CAMPAMENTO-SIYUAN-5716.jpg` | Presente, 329 caracteres |
| 12 | `50bd2a98-6bba-4b44-b485-a1851cb6c803` | `CAMPAMENTO-SIYUAN-6122.jpg` | `coverages/cov-20260818165423-7419/50bd2a98-6bba-4b44-b485-a1851cb6c803_CAMPAMENTO-SIYUAN-6122.jpg` | Presente, 329 caracteres |

## Foto Problematica

Busqueda realizada sobre:

```text
instance/ingest.json
instance/lens_coverages.json
instance/dispatch_shipments.json
instance/delivery_links.json
/opt/atlas-lens/instance
/data/FLOW/sftpgo/storage/events
/data/FLOW/sftpgo/storage/archive
/data/FLOW/trash
```

Terminos:

```text
CAMPAMENTO-SIYUAN-6623(1).jpg
CAMPAMENTO-SIYUAN-6623
6623
SIYUAN.*6623
```

Resultado:

```text
No existe referencia a CAMPAMENTO-SIYUAN-6623(1).jpg ni a 6623 en los stores actuales ni en los archivos fisicos inspeccionados.
```

## Seguimiento Por Etapas

| Etapa | Estado | Evidencia |
|---|---|---|
| Archivo fisico en servidor | AUSENTE | No aparece en `/opt/atlas-lens/instance`, `/data/FLOW/events`, `/data/FLOW/archive` ni `/data/FLOW/trash`. |
| FLOW | AUSENTE | `instance/ingest.json` no contiene `6623` ni `CAMPAMENTO-SIYUAN`. |
| LENS media | AUSENTE | `instance/lens_media/coverages/cov-20260818165423-7419` tiene 12 archivos, ninguno `6623`. |
| Cobertura LENS | AUSENTE | `instance/lens_coverages.json` no contiene `6623`; la foto no tiene ID ni caption. |
| Seleccion de exportacion | AUSENTE | `ExportService.select_photos()` exporta la lista persistida en `coverage["photos"]`; como `6623` no esta ahi, no puede seleccionarse. |
| Export Engine | AUSENTE | El engine recibe solo las fotos persistidas. En las pruebas actuales recibe 12/12, ninguna `6623`. |
| DOCX | AUSENTE | El DOCX no puede incluir una foto que no recibio el engine. |

## Estado Del Archivo

Para `CAMPAMENTO-SIYUAN-6623(1).jpg`:

```text
Formato real: no verificable; archivo no localizado en servidor.
MIME: no verificable.
Extension: .jpg segun nombre reportado.
Dimensiones: no verificables.
Tamano: no verificable.
Lectura por Pillow/ATLAS: no verificable; archivo no existe en el servidor.
Ruta: no localizada.
Owner/group/mode: no aplica.
Caracteres problematicos: el nombre contiene parentesis; ATLAS sanitiza nombres y los parentesis no son por si solos la causa observada.
Duplicado de nombre: no localizado.
Duplicado de ID: no localizado.
Colision con otra fotografia: no localizada.
```

## Evidencia De Fallo Durante Incorporacion

En logs de `atlas-lens.service` alrededor de la operacion se observaron cargas exitosas y dos rechazos `413`:

```text
2026-08-18 11:54:38 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:54:47 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:54:48 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:54:53 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:54:56 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:54:59 POST /coverages/cov-20260818165423-7419/photos -> 413
2026-08-18 11:55:00 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:55:13 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:56:25 POST /coverages/cov-20260818165423-7419/exports -> 200
```

Luego:

```text
2026-08-18 11:57:18 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:57:20 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:57:20 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 11:59:12 POST /coverages/cov-20260818165423-7419/photos -> 413
2026-08-18 11:59:16 POST /coverages/cov-20260818165423-7419/exports -> 200
2026-08-18 12:00:04 POST /coverages/cov-20260818165423-7419/photos -> 201
2026-08-18 12:00:09 POST /coverages/cov-20260818165423-7419/exports -> 409
2026-08-18 12:00:47 POST /coverages/cov-20260818165423-7419/exports -> 200
2026-08-18 12:06:28 POST /coverages/cov-20260818165423-7419/exports -> 200
2026-08-18 12:08:52 POST /coverages/cov-20260818165423-7419/exports -> 200
```

El endpoint devuelve `413` cuando `build_persisted_photo()` detecta:

```python
if declared_size > max_photo_bytes():
    raise OverflowError("La imagen supera el tamaño máximo permitido.")
```

El limite efectivo actual:

```text
LENS_MAX_PHOTO_BYTES = 26214400 bytes
```

Es decir, 25 MiB.

La respuesta del endpoint para ese caso es:

```python
return jsonify({"error": "La fotografia supera el tamaño maximo permitido."}), 413
```

Nota: los logs de acceso no incluyen el nombre del archivo rechazado. Por tanto, la asociacion exacta con `CAMPAMENTO-SIYUAN-6623(1).jpg` se basa en la combinacion de: ausencia total de `6623` en stores/FS, dos rechazos `413` en los periodos de intento, y posterior exito de otras fotos.

## Export Engine

Codigo principal:

```text
app/export/service.py
app/export/engine.py
app/export/builders/docx_builder.py
app/export/builders/image_sources.py
```

Flujo:

1. `ExportService.create_export()` valida request.
2. `select_photos()` devuelve `coverage["photos"]` completa.
3. `build_warnings()` solo advierte captions vacios.
4. `ExportEngine.build_export()` convierte cada dict en `ExportPhoto`.
5. `build_docx()` llama `build_embedded_images()`.
6. `build_document_xml()` genera un bloque textual por cada `ExportPhoto`.

Hallazgos:

- El engine no recibe fotos que no esten persistidas en `coverage["photos"]`.
- El builder DOCX no valida "esperadas vs insertadas".
- Si falla la miniatura de una foto, `build_embedded_images()` omite solo la imagen embebida, pero `build_document_xml()` aun genera el bloque de texto con `Sin miniatura`.
- `load_docx_image_source()` y `build_docx_jpeg_preview()` registran warnings en logs para fallos de imagen, pero no devuelven una estructura de omisiones al resultado.
- No hay estado `COMPLETE / PARTIAL / FAILED`.
- `ExportResult.photo_count` representa fotos recibidas por el engine, no fotos esperadas por el usuario ni imagenes realmente embebidas.

## Prueba En Memoria Del Estado Actual

Se genero un DOCX en memoria usando la cobertura actual, sin escribir archivos:

```text
Export Engine recibe: 12 fotos
ExportResult.photo_count: 12
DOCX media embebida: 12 imagenes
Bloques con filenames en document.xml: 12
Resultado: 12/12 para el estado actual
```

Todas las 12 imagenes actuales fueron leidas por Pillow y por `load_docx_image_source()`.

## Historial Actual

La cobertura ya contiene `export_history`, pero es insuficiente para diagnosticar omisiones:

```text
2026-08-18T16:56:25Z photo_count=8  filename=20260818-CAMPAMENTO-SIYUAN-PRUEBA.docx
2026-08-18T16:57:39Z photo_count=11 filename=20260818-CAMPAMENTO-SIYUAN-Ecuador.docx
2026-08-18T16:59:16Z photo_count=11 filename=20260818-CAMPAMENTO-SIYUAN-12.docx
2026-08-18T17:00:47Z photo_count=12 filename=20260818-CAMPAMENTO-SIYUAN-13.docx
2026-08-18T17:06:28Z photo_count=12 filename=20260818-CAMPAMENTO-SIYUAN-EC.docx
2026-08-18T17:08:51Z photo_count=12 filename=20260818-CAMPAMENTO-SIYUAN-EC.docx
```

Problemas del historial actual:

- No guarda ID unico de exportacion.
- No guarda fotos solicitadas por ID/nombre.
- No guarda fotos omitidas.
- No guarda motivos de omision.
- No distingue `COMPLETE`, `PARTIAL` o `FAILED`.
- No conserva el archivo exportado en una ubicacion consultable desde historial.
- No permite borrar entradas desde UI.

## Causa Exacta

La foto reportada no esta en el Export Engine ni en DOCX porque no quedo persistida en LENS.

La etapa donde desaparece es la incorporacion de fotografias a la cobertura (`POST /coverages/cov-20260818165423-7419/photos`), antes de la seleccion de exportacion.

La evidencia operacional muestra respuestas `413` durante los intentos de incorporacion. El codigo devuelve `413` cuando una imagen supera `LENS_MAX_PHOTO_BYTES` (25 MiB). Al fallar, no se crea archivo en `instance/lens_media`, no se agrega entrada en `coverage["photos"]`, no se guarda caption y no hay forma de que el Export Engine la incluya.

Ademas, la UI cliente mantiene temporalmente la tarjeta de la foto fallida en `selectedPhotos` con estado `Error`, pero el export se ejecuta contra el store del servidor. Esto puede hacer que el usuario vea o recuerde 9 fotos en la interfaz mientras el backend solo tiene 8 persistidas.

## Por Que Puede Verse "Exportacion Generada" Con Menos Fotos

ATLAS considera exitosa la exportacion si el engine genera el DOCX con las fotos persistidas en el servidor.

No existe actualmente una comparacion entre:

```text
fotos que el usuario intento importar
vs.
fotos persistidas
vs.
fotos solicitadas para exportar
vs.
fotos realmente procesadas/embebidas
```

Por eso una exportacion que el usuario espera como 9 puede quedar registrada como 8 y presentarse como correcta: desde el punto de vista del servidor, solo existian 8 fotos persistidas.

## Propuesta De Correccion

### Correccion minima

1. En la importacion de fotos, mantener una lista visible y persistente en UI de importaciones fallidas.
2. Bloquear o advertir exportacion si hay fotos en estado `Error` en el workspace.
3. Mostrar el nombre real y motivo devuelto por backend, por ejemplo:

```text
CAMPAMENTO-SIYUAN-6623(1).jpg no se importo: supera el limite de 25 MiB.
```

4. Agregar logging backend estructurado para rechazos de foto con `coverage_id`, `filename`, `declared_size`, `limit`, `status_code`.
5. En el resultado de exportacion, devolver `requested_photo_count`, `persisted_photo_count`, `exported_photo_count`, `omitted_photos`.

### Correccion de integridad

Agregar estados:

```text
COMPLETE: solicitadas == exportadas y sin omisiones.
PARTIAL: se genero archivo, pero hay fotos omitidas o errores recuperables.
FAILED: no se genero archivo util.
```

Una exportacion `PARTIAL` no debe ofrecerse a DISPATCH sin advertencia explicita.

## Propuesta UX

Resultado exitoso:

```text
Exportacion completada
20260818-CAMPAMENTO-SIYUAN-EC.docx

12 de 12 fotografias exportadas
12 captions incluidos
Sin errores

[Descargar DOCX] [Volver a cobertura] [Enviar a DISPATCH]
```

Resultado parcial:

```text
Exportacion parcial
20260818-CAMPAMENTO-SIYUAN-EC.docx

8 de 9 fotografias exportadas
8 captions incluidos
1 fotografia no pudo procesarse

CAMPAMENTO-SIYUAN-6623(1).jpg
Motivo: supera el limite de 25 MiB / no fue importada a LENS

[Descargar DOCX] [Volver a cobertura]
[Enviar a DISPATCH] deshabilitado o con confirmacion fuerte
```

`Volver a cobertura` debe apuntar directamente a:

```text
/lens/coverages/cov-20260818165423-7419
```

## Propuesta Historial

Recomendado: SI.

Cada registro debe guardar:

- `export_id`
- `coverage_id`
- `coverage_name`
- `created_at`
- `user`
- `destination`
- `formats`
- `filename`
- `requested_photos`: ID, filename, storage/flow path
- `exported_photos`: ID, filename
- `omitted_photos`: ID/filename/motivo/etapa
- `captions_included`
- `status`: `COMPLETE`, `PARTIAL`, `FAILED`
- `warnings`
- `files`: nombre, formato, tamano, path si se conserva
- `dispatch_reference` si luego se envia

Debe poder consultarse desde Exportaciones.

Debe poder eliminarse una entrada con confirmacion.

Recomendacion sobre archivos exportados al borrar historial:

```text
Opcion mas segura: borrar solo el registro visible del historial y conservar el archivo/export artifact durante una ventana de retencion configurable, o hasta limpieza operativa separada.
```

Motivo: eliminar historial no debe borrar cobertura, fotos, originales, captions, FLOW ni LENS. Separar "historial" de "artifact" evita perdida accidental de entregas.

## Archivos Que Habria Que Modificar

Probables:

```text
app/routes/web.py
app/export/models.py
app/export/service.py
app/export/engine.py
app/export/builders/docx_builder.py
app/export/builders/image_sources.py
app/static/js/photo_workspace.js
app/static/js/export_panel.js
app/templates/coverage_detail.html
tests/test_lens_persistence_routes.py
tests/test_export_*.py
docs/...
```

Si se implementa historial durable separado:

```text
app/export/store.py
app/config.py
instance/export_history.json
tests/test_export_history.py
```

## Tests Necesarios

1. Foto mayor a `LENS_MAX_PHOTO_BYTES` devuelve `413` con filename/motivo.
2. UI mantiene y muestra error por foto no importada.
3. Export bloquea o advierte si hay importaciones fallidas activas.
4. Export DOCX `COMPLETE` con N/N fotos.
5. Export DOCX `PARTIAL` si una imagen no puede procesarse.
6. Export `FAILED` si no se puede generar ningun archivo.
7. Historial registra requested/exported/omitted con motivos.
8. Borrado de historial no elimina cobertura, fotos, originales, captions ni FLOW/LENS.
9. DISPATCH recibe advertencia/bloqueo para exportaciones `PARTIAL`.

## Riesgos

- Subir el limite global de fotos puede aumentar memoria, latencia y tamano de payload porque la importacion actual usa JSON base64.
- Hacer fail-hard ante cualquier miniatura fallida puede bloquear flujos donde el caption textual aun seria util.
- Usar `_client state_` como fuente de verdad para "fotos esperadas" puede divergir del backend si hay multiples pestanas.
- Guardar archivos exportados para historial requiere politica de retencion y limpieza.
- Cambiar DISPATCH para bloquear `PARTIAL` puede alterar flujos actuales; debe comunicarse en UI.

## Comandos Relevantes Ejecutados

```bash
grep -RIn "CAMPAMENTO-SIYUAN-6623\\|20260818-CAMPAMENTO-SIYUAN-EC\\|SIYUAN\\|6623" instance app docs tests
find /opt/atlas-lens /data/FLOW -type f | grep -Ei 'CAMPAMENTO.*SIYUAN|SIYUAN|6623'
python scripts de lectura sobre instance/lens_coverages.json e instance/ingest.json
file instance/lens_media/coverages/cov-20260818165423-7419/*.jpg
stat -c '%A %a %U %G %s %n' instance/lens_media/coverages/cov-20260818165423-7419/*.jpg
journalctl -u atlas-lens.service --since '2026-08-18 11:45:00' --until '2026-08-18 12:15:00'
python script de generacion DOCX en memoria y conteo de word/media/*
```

## Confirmacion

Cambios realizados: ninguno, salvo este informe Markdown.

