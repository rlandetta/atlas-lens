# Export Integrity And History Implementation

Fecha: 2026-08-18

## Causa Original

La auditoria en `docs/export_engine_missing_photo_audit.md` identifico que una foto rechazada durante importacion podia seguir siendo visible temporalmente en el workspace del navegador, aunque nunca hubiese quedado persistida en LENS. La exportacion se generaba correctamente desde la fuente de verdad del backend, pero el usuario podia esperar N fotos mientras el servidor solo tenia N-1.

El caso observado fue compatible con rechazo `413` por superar `LENS_MAX_PHOTO_BYTES`, manteniendo el limite actual de 25 MiB.

## Solucion Implementada

- La importacion rechazada devuelve payload estructurado con `filename`, `declared_size`, `limit`, `status_code`, `reason` y mensaje legible.
- El backend registra rechazos con logging estructurado sin incluir base64.
- La UI conserva las fotos fallidas como `No importada` y muestra el motivo real.
- El payload de exportacion incluye `requested_photo_count` y `omitted_photos` derivados del workspace.
- El resultado de exportacion diferencia `COMPLETE`, `PARTIAL` y `FAILED`.
- El resumen visual de exportacion muestra conteos, formatos, paquete ZIP y fotos omitidas.
- DISPATCH parcial requiere confirmacion fuerte.
- Los formatos editoriales son DOCX, HTML y PDF; ZIP se genera automaticamente cuando corresponde.
- El historial nuevo registra conteos, estado, omitidas, artifacts y metadatos.
- El historial antiguo se lee de forma tolerante.
- El borrado de historial elimina solo el registro logico, no coberturas, fotos ni artifacts.

## Archivos Modificados Por Esta Implementacion

```text
app/dispatch/delivery_package.py
app/export/engine.py
app/export/models.py
app/export/naming.py
app/export/service.py
app/routes/web.py
app/static/css/main.css
app/static/js/export_panel.js
app/static/js/photo_workspace.js
app/templates/coverage_detail.html
tests/test_lens_persistence_routes.py
docs/export_integrity_history_implementation.md
```

Nota: el working tree contiene cambios previos no relacionados con esta fase, especialmente FLOW delete y documentacion operativa.

## Comportamiento De Importacion

Si una foto supera el limite actual:

```json
{
  "error": "La fotografía supera el límite máximo permitido de 25 MiB.",
  "filename": "large.jpg",
  "declared_size": 123456,
  "limit": 26214400,
  "status_code": 413,
  "reason": "too_large"
}
```

La tarjeta queda visible como `No importada` y no se presenta como lista.

## COMPLETE / PARTIAL / FAILED

- `COMPLETE`: fotos solicitadas/exportadas coinciden y no hay omitidas.
- `PARTIAL`: existe artifact utilizable pero al menos una foto fue omitida.
- `FAILED`: no se pudo generar un resultado utilizable.

El backend devuelve:

```text
requested_photo_count
persisted_photo_count
exported_photo_count
captions_included
omitted_photos
status
```

## Nuevo Resumen De Exportacion

La UI reemplaza el texto simple por un panel con:

- titulo segun estado;
- filename/artifact;
- conteo exportadas/solicitadas;
- captions incluidos;
- formatos generados;
- paquete ZIP si aplica;
- lista de omitidas y motivo;
- boton `Volver a cobertura`.

## Formatos Y ZIP Automatico

UI:

```text
FORMATOS: DOCX, HTML, PDF
ARCHIVOS: Incluir fotografias originales
```

Reglas:

- DOCX solo -> `.docx`
- PDF solo -> `.pdf`
- HTML solo -> `.html`
- multiples documentos -> `.zip`
- cualquier seleccion con originales -> `.zip`
- solo originales -> `.zip`

## Volver A Cobertura

El boton usa `data-coverage-url` generado por Flask:

```text
/lens/coverages/<coverage_id>
```

segun el routing/prefijo vigente.

## Historial

Cada registro nuevo incluye:

```text
export_id
coverage_id
coverage_name
created_at
user
destination
formats
filename
artifacts
requested_photo_count
persisted_photo_count
exported_photo_count
requested_photos
exported_photos
omitted_photos
captions_included
status
warnings
dispatch_reference
files_created
```

Los registros legacy se normalizan en lectura con valores por defecto.

## Borrado Seguro De Historial

Endpoint:

```text
POST /coverages/<coverage_id>/exports/history/<export_id>/delete
```

Solo elimina el registro visible/logico de `export_history`.

No elimina:

- cobertura;
- fotografias;
- originales;
- captions;
- FLOW;
- LENS;
- artifacts exportados.

## Compatibilidad Con Registros Antiguos

Los registros que solo tienen campos como `format`, `created_at`, `photo_count` y `filename` siguen renderizando sin error. Se muestran como `COMPLETE` salvo que traigan omitidas.

## Tests Ejecutados

```text
.venv/bin/python -m unittest tests.test_lens_persistence_routes
Ran 60 tests - OK

.venv/bin/python -m unittest tests.test_docx_export tests.test_delivery_package_links tests.test_dispatch_service tests.test_dispatch_routes
Ran 157 tests - OK

git diff --check
OK

.venv/bin/python -m unittest discover -s tests
Ran 342 tests - OK
```

Durante la suite aparecen warnings esperados de tests con imagenes dummy y ResourceWarnings preexistentes, sin fallos.

## Riesgos Pendientes

- El historial aun no conserva artifacts fisicos en una store dedicada con politica de retencion.
- La confirmacion parcial en UI cubre omitidas conocidas del workspace; el backend tambien protege DISPATCH parcial por si aparecen omitidas durante export.
- `DeliveryPackageService` ajusta temporalmente `config.LENS_MEDIA_ROOT` al generar DOCX de DISPATCH para respetar su `media_root`; es acotado, pero a futuro conviene inyectar `media_root` en el export engine.
- No se aumento `LENS_MAX_PHOTO_BYTES`; fotos mayores de 25 MiB seguiran siendo rechazadas, ahora con error visible.

## Git Status

```text
 M app/__init__.py
 M app/config.py
 M app/dispatch/delivery_package.py
 M app/export/engine.py
 M app/export/models.py
 M app/export/naming.py
 M app/export/service.py
 M app/routes/web.py
 M app/static/css/main.css
 M app/static/js/export_panel.js
 M app/static/js/photo_workspace.js
 M app/templates/coverage_detail.html
 M app/templates/flow/index.html
 M tests/test_lens_persistence_routes.py
?? app/static/js/flow_session_delete.js
?? atlas-convert-prototype.zip
?? atlas_convert_hif_fix_report.md
?? atlas_convert_install_report.md
?? docs/atlas_flow_mount_verification.md
?? docs/atlas_flow_organizer_service_before_posix_change.txt
?? docs/atlas_flow_permissions_predeploy.md
?? docs/atlas_flow_session_delete_report.md
?? docs/atlas_flow_session_reappears_analysis.md
?? docs/atlas_flow_session_trash_report.md
?? docs/atlas_routing_closeout.md
?? docs/dispatch_download_link_diagnosis.md
?? docs/export_engine_missing_photo_audit.md
?? docs/export_integrity_history_implementation.md
?? docs/flow_delete_acl_ux_fix_report.md
?? docs/flow_delete_deploy_validation.md
?? docs/flow_delete_posix_apply_report.md
?? docs/flow_delete_posix_permissions_plan.md
?? docs/flow_delete_predeploy_validation.md
?? docs/flow_delete_real_failure_diagnosis.md
?? docs/flow_delete_runtime_final.md
?? docs/flow_delete_runtime_permissions.md
?? docs/flow_events_permissions_before_posix_change.txt
?? docs/flow_session_persistence_audit.md
?? docs/flow_trash_runtime_ready.md
?? tests/test_flow_session_delete.py
```

## Confirmaciones

- No se aumento `LENS_MAX_PHOTO_BYTES`.
- No se alteraron fotografias originales.
- No se borraron coberturas.
- No se borro FLOW.
- No se borro LENS.
- No se modifico infraestructura, nginx, systemd ni Proxmox.
- No se hizo deploy.
- No se hizo restart.
- No se hizo commit.
- No se hizo push.

