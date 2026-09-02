# Export Engine v2 de ATLAS LENS

El Export Engine genera un paquete editorial ZIP listo para descargar o entregar posteriormente mediante DISPATCH. Esta capa no envía archivos y no contiene lógica de interfaz.

## Arquitectura

- `app/export/models.py`: define `ExportRequest`, `ExportResult` y `ExportPhoto`.
- `app/export/naming.py`: centraliza el nombre `AAAAMMDD-Cobertura-Pais.zip`.
- `app/export/service.py`: valida solicitudes, selecciona cobertura completa, emite advertencias y registra historial.
- `app/export/engine.py`: orquesta metadatos, manifest y construcción del paquete.
- `app/export/builders/zip_builder.py`: genera el ZIP final sin carpetas vacías.
- `app/export/builders/docx_builder.py`: genera `captions.docx` con el formato existente.
- `app/export/builders/html_builder.py`: genera `captions.html` offline con HTML y CSS locales.
- `app/export/builders/pdf_builder.py`: genera `captions.pdf` con la misma información base del DOCX.

## Formatos visibles

La interfaz muestra únicamente:

- ZIP
- DOCX
- HTML
- PDF

El resultado descargado es siempre un ZIP. DOCX, HTML y PDF controlan qué documentos de captions se incluyen dentro del paquete cuando `Incluir captions` está activo.

## Contenido del paquete

Valores predeterminados:

- Incluir fotografías: activo.
- Incluir captions: activo.
- Incluir metadatos: inactivo.
- Incluir manifiesto: inactivo.

El ZIP incluye únicamente los elementos seleccionados. No se crean carpetas vacías.

## Conteos, omisiones y persistencia

La pertenencia de una fotografía a una cobertura es independiente del estado de su caption. Guardar captions, cambiar pestañas, exportar o volver a la cobertura no debe eliminar asociaciones de `coverage["photos"]`.

Export Engine v2 diferencia estos conteos:

- `requested_photo_count`: fotografías que el usuario tenía en el workspace al pedir exportación.
- `persisted_photo_count`: fotografías asociadas a la cobertura persistida recibida por el servidor.
- `exported_photo_count`: fotografías incluidas en los documentos o paquete generado.
- `captions_included`: captions no vacíos incluidos.

Cuando la interfaz envía `requested_photos`, el engine puede diagnosticar diferencias entre lo visible en el navegador y lo persistido. Una fotografía omitida se registra en `omitted_photos` con `filename`, `stage` y `reason`, por ejemplo:

- `caption` / `Caption ausente.`
- `persistence` / `No está asociada a la cobertura persistida.`
- `export` / `Archivo no disponible para exportación.`

Una exportación parcial con omisiones no debe presentarse como “Sin errores”. “Sin errores” queda reservado para generaciones sin fallos técnicos y sin fotografías omitidas.

## Estructura del ZIP

```text
20260729-Capacitacion-Policia-Ecuador.zip
├── Fotografias/
│   ├── IMG0001.CR3
│   └── IMG0002.CR3
├── captions.docx
├── captions.pdf
├── captions.html
├── metadata.json
└── manifest.json
```

Las fotografías conservan exactamente el nombre original importado.
El DOCX de captions incrusta una imagen reducida: primero reutiliza la miniatura existente de ATLAS cuando está disponible y, si no existe una miniatura utilizable, genera una variante JPEG temporal para el documento con un lado largo máximo aproximado de 800 px. Esta variante no modifica ni reemplaza la fotografía original.
PDF resuelve imágenes desde `data_url`, `storage_path` o `flow_path` para su vista de captions. El ZIP escribe los archivos originales desde esas mismas fuentes; si una fotografía no puede resolverse, la exportación falla explícitamente con su nombre e ID en lugar de crear un archivo vacío.

Cada fotografía puede marcarse individualmente con `is_drone`. En captions Xinhua, este atributo solo cambia el inicio de la narración generada:

- Foto normal con fecha de toma diferente: `Imagen del [fecha] de [narración] ...`.
- Foto normal con fecha de toma igual al envío: `[narración] ... el [fecha].`.
- Foto con dron y fecha de toma diferente: `Vista aérea tomada con un dron el [fecha] de [narración] ...`.
- Foto con dron y fecha de toma igual al envío: `Vista aérea tomada con un dron de [narración] ... el [fecha].`.

Si `is_drone` no existe en una cobertura antigua, LENS lo interpreta como `false`.

## Nomenclatura

`ExportNamingService` normaliza automáticamente:

- tildes;
- caracteres inválidos;
- espacios a guiones;
- dobles guiones;
- símbolos no compatibles.

Formato final: `AAAAMMDD-Cobertura-Pais.zip`.

## Agregar nuevos formatos

1. Crear un builder en `app/export/builders/`.
2. Agregar el formato al contrato de `ExportRequest` si debe ser visible.
3. Conectarlo en `zip_builder.py` para que se escriba solo cuando el usuario lo seleccione.
4. Agregar su checkbox en la pestaña `Exportaciones` si aplica al usuario final.

## Uso futuro por DISPATCH

DISPATCH debe consumir el `ExportResult.archive_path`/archivo ZIP generado por LENS. No debe regenerar documentos ni reconstruir el paquete; solo tomar el ZIP final y entregarlo por el canal configurado.
