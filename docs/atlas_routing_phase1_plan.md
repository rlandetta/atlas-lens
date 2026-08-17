# ATLAS Routing Architecture - Phase 1 Plan

Fecha: 2026-08-16

Repositorio: `/opt/atlas-lens`

Alcance: plan de implementacion segura dentro de Flask. No incluye cambios en Apache, DNS, VPS, systemd, firewall, certificados, Docker, Proxmox, deploy ni restart.

## 1. Resumen ejecutivo

La arquitectura objetivo publica de ATLAS es:

| Ruta canonica | Responsabilidad |
|---|---|
| `/` | Dashboard ATLAS |
| `/flow/` | FLOW |
| `/lens/` | LENS |
| `/lens/coverages/...` | Coberturas y acciones propias de LENS |
| `/dispatch/` | DISPATCH |
| `/settings/` | SETTINGS |
| `/d/...` | Entregas publicas |
| `/static/...` | Assets estaticos Flask |

El estado actual de produccion depende de `ATLAS_URL_PREFIX=/lens` y de un proxy Apache externo que conserva el prefijo `/lens` al enviar requests hacia Flask. Con ese prefijo activo, las rutas internas actuales se publican asi:

| Ruta interna actual Flask | URL publica actual con `ATLAS_URL_PREFIX=/lens` |
|---|---|
| `/` | `/lens/` |
| `/flow` | `/lens/flow` |
| `/lens` | `/lens/lens` |
| `/coverages/...` | `/lens/coverages/...` |
| `/dispatch/...` | `/lens/dispatch/...` |
| `/settings/...` | `/lens/settings/...` |
| `/d/...` | `/lens/d/...` |
| `/static/...` | `/lens/static/...` |

La fase 1 debe preparar el codigo para la arquitectura canonica, pero no debe activar el corte publico todavia. La restriccion central es evitar que `ATLAS_URL_PREFIX=/lens` convierta rutas canonicas internas `/lens/...` en URLs publicas `/lens/lens/...`.

Conclusion: en esta primera pasada no se debe mover aun los handlers reales de LENS a un blueprint con `url_prefix="/lens"` mientras produccion siga con `ATLAS_URL_PREFIX=/lens`. El paso seguro es introducir una capa de rutas canonicas/legacy controlada por configuracion o por registro dual, con pruebas que demuestren ambos modos antes del cambio de Apache.

## 2. Archivos que seria necesario modificar

Archivos de aplicacion:

| Archivo | Cambio propuesto |
|---|---|
| `app/routes/web.py` | Separar semanticamente Dashboard, FLOW y LENS. Mantener handlers existentes, pero anadir reglas canonicas `/lens/...` para LENS y reglas legacy `/coverages/...` con redirects/handlers seguros. |
| `app/__init__.py` | Registrar rutas canonicas/legacy sin duplicar blueprints ni romper `ATLAS_URL_PREFIX`. Mantener `UrlPrefixMiddleware` hasta el corte. |
| `app/config.py` | Mantener `ATLAS_URL_PREFIX`. Opcionalmente anadir flags internos seguros como `ATLAS_ENABLE_CANONICAL_LENS_ROUTES` y `ATLAS_ENABLE_LEGACY_ROUTE_REDIRECTS`, por defecto compatibles con produccion. |
| `app/templates/_header.html` | Verificar que toda navegacion siga usando `url_for()`. No hardcodear prefijos. |
| `app/templates/index.html` | Verificar enlaces Dashboard -> FLOW/LENS/DISPATCH con `url_for()`. |
| `app/templates/lens_index.html` | Verificar nueva cobertura, detalle, editar y delete action con `url_for()`/data attributes. |
| `app/templates/new_coverage.html` | Verificar back link y form action. |
| `app/templates/coverage_detail.html` | Verificar autoguardado, captions, fotos, IA, exportaciones, media, thumbnails, FLOW handoff y DISPATCH usando `url_for()`/data attributes. |
| `app/static/js/coverage_delete.js` | Verificar que usa `data-delete-action`; no construir URLs absolutas. |
| `app/static/js/photo_workspace.js` | Verificar que usa data attributes para fotos, captions, thumbnails, media e IA. |
| `app/static/js/export_panel.js` | Verificar que usa `data-export-url`. |
| `app/static/js/coverage_edit.js` | Verificar que no hardcodea rutas. |

Archivos de pruebas:

| Archivo | Cambio propuesto |
|---|---|
| `tests/test_atlas_routing_phase1.py` | Nuevo set enfocado de routing canonico/legacy. |
| `tests/test_url_prefix.py` | Actualizar expectativas para demostrar que `ATLAS_URL_PREFIX=/lens` sigue compatible mientras no se corte Apache. |
| `tests/test_lens_persistence_routes.py` | Extender helpers para probar acciones criticas por rutas canonicas y legacy. |
| `tests/test_dispatch_routes.py` | Confirmar DISPATCH bajo `/dispatch/` en modo canonico y compatibilidad prefijada en modo legacy de produccion. |
| `tests/test_settings_routes.py` | Confirmar SETTINGS bajo `/settings/` en modo canonico y compatibilidad prefijada. |
| `tests/test_delivery_package_links.py` | Confirmar `/d/<token>` en modo canonico y no romper enlaces existentes durante la transicion. |

Documentacion:

| Archivo | Cambio propuesto |
|---|---|
| `docs/atlas_routing_phase1_plan.md` | Este plan. |
| `docs/atlas_routing_audit.md` | Actualizar despues de implementar fase 1, no antes. |
| Documento tecnico o ADR nuevo | Recomendado para registrar la decision de mantener `ATLAS_URL_PREFIX` hasta el cambio Apache. |

## 3. Rutas canonicas propuestas

### Dashboard

| Endpoint | Metodo | Ruta canonica |
|---|---:|---|
| `web.home` | GET | `/` |

### FLOW

| Endpoint | Metodo | Ruta canonica |
|---|---:|---|
| `web.flow_home` | GET | `/flow/` |
| `web.flow_photo_thumbnail` | GET | `/flow/photos/<photo_id>/thumbnail` |
| `web.flow_new_coverage` | GET, POST | `/flow/sessions/<session_id>/coverage/new` |
| `web.flow_open_lens` | POST | `/flow/sessions/<session_id>/lens/open` |

Nota: `web.flow_new_coverage` y `web.flow_open_lens` pertenecen al contrato FLOW -> LENS, pero la URL canonica debe permanecer bajo `/flow/...` porque la accion nace en FLOW.

### LENS

| Endpoint | Metodo | Ruta canonica |
|---|---:|---|
| `web.lens_home` | GET | `/lens/` |
| `web.new_coverage` | GET, POST | `/lens/coverages/new` |
| `web.coverage_detail` | GET | `/lens/coverages/<coverage_id>` |
| `web.edit_coverage` | POST | `/lens/coverages/<coverage_id>/edit` |
| `web.save_coverage_ai_context` | POST | `/lens/coverages/<coverage_id>/ai-context` |
| `web.delete_coverage` | POST | `/lens/coverages/<coverage_id>/delete` |
| `web.create_coverage_export` | POST | `/lens/coverages/<coverage_id>/exports` |
| `web.add_coverage_photo` | POST | `/lens/coverages/<coverage_id>/photos` |
| `web.coverage_photo_thumbnail` | GET | `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` |
| `web.coverage_photo_media` | GET | `/lens/coverages/<coverage_id>/photos/<photo_id>/media` |
| `web.save_coverage_photo_caption` | POST | `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` |
| `web.copy_caption_to_empty_photos` | POST | `/lens/coverages/<coverage_id>/captions/copy-caption-empty` |
| `web.generate_photo_narration` | POST | `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` |
| `web.get_photo_ai_context` | GET | `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` |
| `web.delete_coverage_photo` | POST | `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` |

### DISPATCH

| Endpoint | Metodo | Ruta canonica |
|---|---:|---|
| `dispatch.index` | GET | `/dispatch/` |
| `dispatch.new` | GET, POST | `/dispatch/new` |
| `dispatch.detail` | GET | `/dispatch/<shipment_id>` |
| `dispatch.edit` | GET, POST | `/dispatch/<shipment_id>/edit` |
| `dispatch.duplicate` | POST | `/dispatch/<shipment_id>/duplicate` |
| `dispatch.cancel` | POST | `/dispatch/<shipment_id>/cancel` |
| `dispatch.revoke_delivery_link` | POST | `/dispatch/<shipment_id>/delivery-link/revoke` |
| `dispatch.regenerate_delivery_link` | POST | `/dispatch/<shipment_id>/delivery-link/regenerate` |
| `dispatch.delete` | POST | `/dispatch/<shipment_id>/delete` |
| `dispatch.delete_cancelled` | POST | `/dispatch/delete-cancelled` |

### SETTINGS

| Endpoint | Metodo | Ruta canonica |
|---|---:|---|
| `settings.index` | GET | `/settings/` |
| `settings.channels` | GET | `/settings/channels` |
| `settings.new_channel` | GET, POST | `/settings/channels/new` |
| `settings.edit_channel` | GET, POST | `/settings/channels/<channel_id>/edit` |
| `settings.delete_channel` | POST | `/settings/channels/<channel_id>/delete` |

### Entregas publicas y static

| Endpoint | Metodo | Ruta canonica |
|---|---:|---|
| `downloads.landing` | GET | `/d/<token>` |
| `downloads.preview` | GET | `/d/<token>/preview/<preview_id>` |
| `downloads.download_zip` | GET | `/d/<token>/download` |
| `downloads.download_file` | GET | `/d/<token>/file/<file_id>` |
| `static` | GET | `/static/<path:filename>` |

## 4. Rutas legacy y mapa legacy -> canonica

### Legacy interno actual sin prefijo global

Estas rutas existen hoy dentro de Flask y deben seguir funcionando durante la transicion:

| Ruta legacy | Metodo | Ruta canonica |
|---|---:|---|
| `/lens` | GET | `/lens/` |
| `/coverages/new` | GET, POST | `/lens/coverages/new` |
| `/coverages/<coverage_id>` | GET | `/lens/coverages/<coverage_id>` |
| `/coverages/<coverage_id>/edit` | POST | `/lens/coverages/<coverage_id>/edit` |
| `/coverages/<coverage_id>/ai-context` | POST | `/lens/coverages/<coverage_id>/ai-context` |
| `/coverages/<coverage_id>/delete` | POST | `/lens/coverages/<coverage_id>/delete` |
| `/coverages/<coverage_id>/exports` | POST | `/lens/coverages/<coverage_id>/exports` |
| `/coverages/<coverage_id>/photos` | POST | `/lens/coverages/<coverage_id>/photos` |
| `/coverages/<coverage_id>/photos/<photo_id>/thumbnail` | GET | `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` |
| `/coverages/<coverage_id>/photos/<photo_id>/media` | GET | `/lens/coverages/<coverage_id>/photos/<photo_id>/media` |
| `/coverages/<coverage_id>/photos/<photo_id>/caption` | POST | `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` |
| `/coverages/<coverage_id>/captions/copy-caption-empty` | POST | `/lens/coverages/<coverage_id>/captions/copy-caption-empty` |
| `/coverages/<coverage_id>/photos/<photo_id>/generate-narration` | POST | `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` |
| `/coverages/<coverage_id>/photos/<photo_id>/ai-context` | GET | `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` |
| `/coverages/<coverage_id>/photos/<photo_id>/delete` | POST | `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` |

### Legacy publico actual con `ATLAS_URL_PREFIX=/lens`

Mientras produccion mantenga `ATLAS_URL_PREFIX=/lens`, las URLs publicas actuales son:

| URL publica legacy actual | Ruta canonica despues del corte |
|---|---|
| `/lens/` | `/` |
| `/lens/flow` | `/flow/` |
| `/lens/flow/photos/<photo_id>/thumbnail` | `/flow/photos/<photo_id>/thumbnail` |
| `/lens/flow/sessions/<session_id>/coverage/new` | `/flow/sessions/<session_id>/coverage/new` |
| `/lens/flow/sessions/<session_id>/lens/open` | `/flow/sessions/<session_id>/lens/open` |
| `/lens/lens` | `/lens/` |
| `/lens/coverages/new` | `/lens/coverages/new` |
| `/lens/coverages/<coverage_id>` | `/lens/coverages/<coverage_id>` |
| `/lens/coverages/<coverage_id>/edit` | `/lens/coverages/<coverage_id>/edit` |
| `/lens/coverages/<coverage_id>/ai-context` | `/lens/coverages/<coverage_id>/ai-context` |
| `/lens/coverages/<coverage_id>/delete` | `/lens/coverages/<coverage_id>/delete` |
| `/lens/coverages/<coverage_id>/exports` | `/lens/coverages/<coverage_id>/exports` |
| `/lens/coverages/<coverage_id>/photos` | `/lens/coverages/<coverage_id>/photos` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` | `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/media` | `/lens/coverages/<coverage_id>/photos/<photo_id>/media` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` | `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` |
| `/lens/coverages/<coverage_id>/captions/copy-caption-empty` | `/lens/coverages/<coverage_id>/captions/copy-caption-empty` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` | `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` | `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` | `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` |
| `/lens/dispatch/` | `/dispatch/` |
| `/lens/dispatch/new` | `/dispatch/new` |
| `/lens/dispatch/<shipment_id>` | `/dispatch/<shipment_id>` |
| `/lens/dispatch/<shipment_id>/edit` | `/dispatch/<shipment_id>/edit` |
| `/lens/dispatch/<shipment_id>/duplicate` | `/dispatch/<shipment_id>/duplicate` |
| `/lens/dispatch/<shipment_id>/cancel` | `/dispatch/<shipment_id>/cancel` |
| `/lens/dispatch/<shipment_id>/delivery-link/revoke` | `/dispatch/<shipment_id>/delivery-link/revoke` |
| `/lens/dispatch/<shipment_id>/delivery-link/regenerate` | `/dispatch/<shipment_id>/delivery-link/regenerate` |
| `/lens/dispatch/<shipment_id>/delete` | `/dispatch/<shipment_id>/delete` |
| `/lens/dispatch/delete-cancelled` | `/dispatch/delete-cancelled` |
| `/lens/settings/` | `/settings/` |
| `/lens/settings/channels` | `/settings/channels` |
| `/lens/settings/channels/new` | `/settings/channels/new` |
| `/lens/settings/channels/<channel_id>/edit` | `/settings/channels/<channel_id>/edit` |
| `/lens/settings/channels/<channel_id>/delete` | `/settings/channels/<channel_id>/delete` |
| `/lens/d/<token>` | `/d/<token>` |
| `/lens/d/<token>/download` | `/d/<token>/download` |
| `/lens/d/<token>/file/<file_id>` | `/d/<token>/file/<file_id>` |
| `/lens/d/<token>/preview/<preview_id>` | `/d/<token>/preview/<preview_id>` |
| `/lens/static/<path>` | `/static/<path>` |

## 5. Estrategia GET

Objetivo: GET legacy debe redirigir de forma segura hacia la ruta canonica cuando sea apropiado, sin romper produccion con `ATLAS_URL_PREFIX=/lens`.

Estrategia propuesta:

1. Registrar rutas canonicas LENS bajo `/lens/...` solo en modo sin prefijo global o con flag de fase 1 controlado por tests/local.
2. Mantener handlers legacy `/coverages/...` mientras `ATLAS_URL_PREFIX=/lens` siga activo en produccion.
3. Para GET legacy internos:
   - `/coverages/new` -> `302` o `308` hacia `url_for("web.new_coverage_canonical")`.
   - `/coverages/<coverage_id>` -> `302` o `308` hacia `url_for("web.coverage_detail_canonical", coverage_id=coverage_id, **request.args)`.
   - `/coverages/<coverage_id>/photos/<photo_id>/thumbnail` -> preferir handler compatible directo durante fase 1 para evitar cache churn; despues del corte puede redirigir `308`.
   - `/coverages/<coverage_id>/photos/<photo_id>/media` -> preferir handler compatible directo durante fase 1; despues del corte puede redirigir `308`.
   - `/coverages/<coverage_id>/photos/<photo_id>/ai-context` -> puede redirigir `308` o llamar al handler canonico, preservando query string.
4. Para `/lens` vs `/lens/`, permitir normalizacion por Flask `strict_slashes` o registrar explicitamente `/lens/` como canonica y `/lens` como alias GET.
5. No usar strings hardcodeados para construir Location. Usar `url_for()` para que `SCRIPT_NAME` y `ATLAS_URL_PREFIX` sean respetados.

Durante la fase previa al corte, si `ATLAS_URL_PREFIX=/lens` esta activo, no conviene emitir redirects desde `/coverages/...` a `/lens/coverages/...`, porque publicamente eso se convierte en `/lens/lens/coverages/...`. En ese modo las rutas legacy deben seguir como handlers compatibles.

## 6. Estrategia POST

Objetivo: POST legacy debe preservar metodo y body.

Estrategia propuesta:

1. Para acciones criticas POST legacy, preferir handlers compatibles directos durante fase 1 mientras `ATLAS_URL_PREFIX` este activo. Esto evita perder bodies JSON o multipart y evita URLs publicas duplicadas.
2. En modo canonico sin prefijo global, los POST legacy pueden redirigir a canonico con `307 Temporary Redirect` durante pruebas de compatibilidad o `308 Permanent Redirect` despues de validar clientes.
3. Para formularios HTML tradicionales:
   - `307` preserva metodo y body.
   - `308` tambien preserva metodo y body, pero puede quedar cacheado por clientes/proxies; reservarlo para una fase posterior.
4. Para `fetch()` JSON usado por autoguardado, fotos, captions, IA y exportaciones, mantener handler compatible directo es mas seguro que depender de follow-redirect en todos los navegadores/clientes.
5. Acciones POST que deben mantenerse sin regresiones:
   - crear cobertura;
   - editar cobertura;
   - eliminar cobertura;
   - guardar contexto IA;
   - subir fotos;
   - borrar fotos;
   - guardar caption/autoguardado;
   - copiar caption a fotos vacias;
   - generar narracion IA;
   - crear export DOCX;
   - preparar handoff a DISPATCH;
   - acciones DISPATCH;
   - acciones SETTINGS.

Recomendacion concreta: implementar un helper `redirect_preserving_method(endpoint, code=307, **values)` y usarlo solo cuando `ATLAS_URL_PREFIX` este vacio o cuando un flag de migracion lo active explicitamente. En produccion actual, dejar POST legacy como alias directo.

## 7. Riesgos

| Riesgo | Impacto | Mitigacion |
|---|---|---|
| Duplicar `/lens` por `ATLAS_URL_PREFIX=/lens` mas rutas internas `/lens/...` | URLs publicas `/lens/lens/...`, ruptura de navegacion y AJAX | No activar canonicas internas como destino de `url_for()` mientras el prefijo global siga activo. Cubrir con tests. |
| Cambiar endpoint Flask y romper templates/JS | Autoguardado, captions, exportaciones o delete dejan de apuntar al handler correcto | Mantener nombres de endpoint o aliases compatibles. Revisar templates con tests HTML. |
| Redireccionar POST con `302` | Perdida de metodo/body | Usar `307`/`308` o handler compatible directo. |
| Redirects en `fetch()` JSON/multipart | Diferencias de cliente, errores CORS/cache o cuerpos no reusables | Handler directo para POST criticos durante fase 1. |
| Static bajo prefijo actual | CSS/JS no cargan en produccion | Mantener `APPLICATION_ROOT`/middleware hasta el corte. Tests para `/lens/static/...` y `/static/...` por modo. |
| `/d/<token>` publico bajo prefijo actual | Enlaces de entrega existentes podrian cambiar | Mantener compatibilidad con `/lens/d/...` hasta el corte y probar `/d/...` en modo canonico. |
| Slash final `/flow` vs `/flow/`, `/lens` vs `/lens/` | Redirects inesperados o duplicados | Definir canonicas con slash para landing de modulos y probar ambos. |
| Cambios sobre worktree sucio | Mezcla de tareas y regresiones dificiles de revisar | Mantener cambios pequenos y revisar `git status` antes/despues. |

## 8. Pruebas

Pruebas nuevas recomendadas en `tests/test_atlas_routing_phase1.py`:

1. Modo canonico sin prefijo global:
   - `GET /` -> 200 Dashboard.
   - `GET /flow/` -> 200 FLOW.
   - `GET /lens/` -> 200 LENS.
   - `GET /lens/coverages/new` -> 200.
   - `POST /lens/coverages/new` -> redirect a `/lens/coverages/<id>`.
   - `GET /lens/coverages/<id>` -> 200.
   - `GET /dispatch/` -> 200.
   - `GET /settings/` -> 200.
   - `GET /static/css/main.css` -> 200.
2. Legacy LENS sin prefijo global:
   - `GET /coverages/new` -> redirect seguro a `/lens/coverages/new`.
   - `GET /coverages/<id>` -> redirect seguro a `/lens/coverages/<id>`.
   - `POST /coverages/<id>/edit` -> `307`/handler compatible y persiste cambios.
   - `POST /coverages/<id>/delete` -> `307`/handler compatible y elimina.
3. Modo produccion actual con `ATLAS_URL_PREFIX=/lens`:
   - `GET /lens/` sigue sirviendo Dashboard actual o el comportamiento existente esperado hasta el corte.
   - `GET /lens/lens` sigue sirviendo LENS actual.
   - `POST /lens/coverages/new` sigue funcionando.
   - Redirects no contienen `/lens/lens/coverages/...` salvo el LENS home legacy actual `/lens/lens`.
   - `GET /lens/static/css/main.css` -> 200.
4. Acciones criticas LENS:
   - crear cobertura;
   - editar cobertura;
   - eliminar cobertura;
   - guardar contexto IA con `AI_ENABLED`;
   - subir foto;
   - thumbnail;
   - media;
   - guardar caption;
   - copiar caption;
   - generar narracion IA;
   - preview contexto IA;
   - borrar foto;
   - export DOCX;
   - export destino DISPATCH / handoff.
5. Public delivery:
   - `GET /d/<token>` en modo canonico.
   - `GET /lens/d/<token>` en modo prefijado de produccion.
   - preview, download zip y download file.
6. DISPATCH y SETTINGS:
   - rutas canonicas sin prefijo.
   - rutas prefijadas con `ATLAS_URL_PREFIX=/lens`.
   - POST importantes preservan metodo y body.

Comandos de verificacion solicitados:

```bash
git diff --check
.venv/bin/python -m unittest tests.test_atlas_routing_phase1
.venv/bin/python -m unittest
```

Si las pruebas se implementan con pytest en una fase posterior, el equivalente seria:

```bash
.venv/bin/python -m pytest tests/test_atlas_routing_phase1.py
.venv/bin/python -m pytest
```

El entorno actual no tiene `pytest` documentado en `requirements.txt`; la suite existente usa `unittest`.

## 9. Partes que pueden implementarse sin tocar produccion

Estas tareas son seguras dentro del repositorio si se mantienen desactivadas o compatibles con `ATLAS_URL_PREFIX=/lens`:

1. Anadir pruebas de routing para modo canonico sin prefijo usando patch de `app.config.ATLAS_URL_PREFIX=""`.
2. Anadir pruebas de compatibilidad para modo prefijado `ATLAS_URL_PREFIX="/lens"`.
3. Crear helpers internos para redirects GET/POST sin cambiar todavia los destinos generados por templates en produccion.
4. Registrar aliases legacy que llamen al mismo handler y no modifiquen comportamiento productivo.
5. Verificar y, si hace falta, corregir templates para usar exclusivamente `url_for()` y data attributes.
6. Documentar el mapa de rutas y el procedimiento de corte.
7. Mantener `ATLAS_URL_PREFIX` intacto.

## 10. Partes que deben esperar al cambio de Apache

Estas tareas deben esperar a una ventana coordinada con Apache/VPS:

1. Quitar o cambiar `ATLAS_URL_PREFIX=/lens` en systemd.
2. Cambiar Apache para publicar:
   - `/` -> Dashboard ATLAS;
   - `/flow/` -> FLOW;
   - `/lens/` -> LENS;
   - `/dispatch/` -> DISPATCH;
   - `/settings/` -> SETTINGS;
   - `/d/` -> entregas;
   - `/static/` -> static.
3. Activar redirects publicos desde `/lens/flow`, `/lens/dispatch`, `/lens/settings`, `/lens/d` hacia sus canonicas.
4. Convertir redirects POST legacy de handlers compatibles a `307`/`308` si se decide hacerlo.
5. Cambiar `PUBLIC_BASE_URL` si actualmente genera links bajo `/lens/d/...`.
6. Reiniciar servicios o recargar Apache/systemd.
7. Validar DNS/TLS/firewall/proxy externo.

## 11. Procedimiento de rollback

Rollback de fase 1 codigo solamente:

1. No tocar systemd, Apache ni DNS.
2. Revertir el commit o cambios de codigo de fase 1 dentro de `/opt/atlas-lens`.
3. Restaurar el comportamiento actual:
   - `ATLAS_URL_PREFIX=/lens`;
   - rutas internas `/`, `/flow`, `/lens`, `/coverages/...`, `/dispatch/...`, `/settings/...`, `/d/...`;
   - URLs publicas actuales bajo `/lens/...`.
4. Ejecutar:

```bash
git diff --check
.venv/bin/python -m unittest tests.test_url_prefix tests.test_lens_persistence_routes
.venv/bin/python -m unittest
```

Rollback durante corte Apache futuro:

1. Restaurar la configuracion Apache previa que proxya solo `/lens...` hacia Flask.
2. Restaurar `ATLAS_URL_PREFIX=/lens` en `atlas-lens.service`.
3. Reiniciar o recargar servicios solo dentro de la ventana aprobada.
4. Validar URLs legacy:
   - `/lens/`;
   - `/lens/lens`;
   - `/lens/coverages/...`;
   - `/lens/dispatch/...`;
   - `/lens/settings/...`;
   - `/lens/d/...`;
   - `/lens/static/...`.
5. Revisar logs de Flask y Apache buscando 404/405/500.

## 12. Plan de implementacion recomendado

Fase 1A - pruebas y mapa:

1. Crear `tests/test_atlas_routing_phase1.py`.
2. Congelar comportamiento actual con `ATLAS_URL_PREFIX=/lens`.
3. Definir expectativas canonicas sin prefijo global.
4. Ejecutar la suite y confirmar fallos esperados antes de tocar rutas.

Fase 1B - rutas LENS canonicas internas seguras:

1. Extraer la logica de handlers LENS a funciones privadas o mantener handlers actuales y anadir aliases con endpoint separado.
2. Registrar canonicas `/lens/...` en modo sin prefijo global.
3. Mantener legacy `/coverages/...` como handler directo cuando `ATLAS_URL_PREFIX` no este vacio.
4. En modo sin prefijo, usar redirects GET legacy a canonico.
5. Para POST legacy, usar handler directo o `307` segun flag de migracion.

Fase 1C - templates y JavaScript:

1. Asegurar que `url_for()` apunta al endpoint canonico en modo sin prefijo.
2. Confirmar que los JS leen URLs desde data attributes:
   - `data-delete-action`;
   - `data-photos-url`;
   - `data-photo-delete-url-template`;
   - `data-photo-caption-url-template`;
   - `data-copy-caption-url`;
   - `data-photo-ai-url-template`;
   - `data-photo-ai-context-url-template`;
   - `data-export-url`.
3. No construir URLs absolutas en JS.

Fase 1D - verificacion:

1. `git diff --check`.
2. Tests especificos de routing.
3. Suite completa.
4. Generar mapa final desde `app.url_map`.
5. Documentar cualquier desviacion.

## 13. Decision para esta primera pasada

No implementar todavia cambios de routing Flask en esta pasada. La razon es que el cambio puede afectar produccion mientras `ATLAS_URL_PREFIX=/lens` siga activo:

- mover handlers LENS a `/lens/...` dentro de Flask puede producir URLs publicas `/lens/lens/...`;
- redirigir legacy `/coverages/...` a `/lens/coverages/...` con el prefijo global activo puede romper acciones productivas;
- POST AJAX de fotos/captions/IA/export requiere compatibilidad directa antes de usar redirects.

Lo seguro ahora es dejar este plan, implementar pruebas en la siguiente pasada y solo despues introducir aliases/redirects controlados.
