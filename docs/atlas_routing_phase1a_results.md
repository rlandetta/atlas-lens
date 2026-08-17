# ATLAS Routing Architecture - Phase 1A Results

Fecha: 2026-08-17

Repositorio: `/opt/atlas-lens`

Alcance ejecutado: pruebas de caracterizacion de routing Flask. No se modifico Apache, VPS, DNS, systemd, Docker, firewall, certificados, despliegue ni runtime productivo.

## 1. Pruebas creadas

Archivo creado:

```text
tests/test_atlas_routing_phase1.py
```

El archivo contiene 8 tests:

| Test | Proposito |
|---|---|
| `test_mode_a_current_production_entrypoints_with_lens_prefix` | Congela entrypoints productivos actuales con `ATLAS_URL_PREFIX=/lens`. |
| `test_mode_a_current_production_lens_critical_actions_keep_method_and_body` | Congela acciones criticas LENS con POST/JSON/body en modo productivo actual. |
| `test_mode_a_flow_dispatch_settings_and_public_delivery_posts_keep_body` | Congela FLOW/DISPATCH/SETTINGS/public delivery bajo prefijo actual. |
| `test_mode_a_flow_to_lens_handoff_keeps_post_body` | Congela POST FLOW -> LENS bajo prefijo actual. |
| `test_mode_b_canonical_target_routes_without_prefix` | Define expectativas canonicas objetivo con `ATLAS_URL_PREFIX=""`. |
| `test_current_unprefixed_legacy_coverages_routes_are_direct_handlers` | Documenta comportamiento legacy interno actual `/coverages/...` sin prefijo. |
| `test_templates_render_url_for_data_attributes_for_lens_actions` | Verifica URLs renderizadas via `url_for()`/data attributes en templates. |
| `test_javascript_uses_data_attributes_instead_of_hardcoded_route_roots` | Verifica que JS critico no hardcodea raices de rutas. |

## 2. Comportamiento modo produccion

Modo A usa app de prueba con:

```text
ATLAS_URL_PREFIX=/lens
```

Resultado: el comportamiento productivo actual queda congelado y pasa.

Rutas verificadas:

| URL actual | Resultado |
|---|---:|
| `/lens/` | 200, Dashboard actual |
| `/lens/flow` | 200, FLOW |
| `/lens/lens` | 200, LENS |
| `/lens/coverages/<coverage_id>` | 200, detalle cobertura |
| `/lens/dispatch/` | 200, DISPATCH |
| `/lens/settings/` | 200, SETTINGS |
| `/lens/static/css/main.css` | 200, static |
| `/lens/d/<token>` | 200, entrega publica |

Acciones criticas verificadas en modo produccion:

| Accion | Ruta actual | Resultado |
|---|---|---:|
| Crear cobertura | `POST /lens/coverages/new` | 302 a `/lens/coverages/<id>` |
| Abrir cobertura | `GET /lens/coverages/<id>` | 200 |
| Editar cobertura | `POST /lens/coverages/<id>/edit` | 302 y persiste body |
| Eliminar cobertura | `POST /lens/coverages/<id>/delete` | 302 a `/lens/lens` |
| Guardar caption | `POST /lens/coverages/<id>/photos/<photo_id>/caption` | 200 JSON |
| Autoguardado caption | segundo POST caption | 200 JSON con ultimo valor |
| Add photo | `POST /lens/coverages/<id>/photos` | 201 JSON |
| Delete photo | `POST /lens/coverages/<id>/photos/<photo_id>/delete` | 200 JSON |
| Media | `GET /lens/coverages/<id>/photos/<photo_id>/media` | 200 |
| Thumbnail | `GET /lens/coverages/<id>/photos/<photo_id>/thumbnail` | 200 |
| IA context | `GET /lens/coverages/<id>/photos/<photo_id>/ai-context` | 200 JSON |
| IA narracion | `POST /lens/coverages/<id>/photos/<photo_id>/generate-narration` | 200 JSON |
| Export DOCX | `POST /lens/coverages/<id>/exports` | 200 JSON |
| FLOW -> LENS | `POST /lens/flow/sessions/<id>/lens/open` | 302 a `/lens/coverages/<id>` |
| DISPATCH | `POST /lens/dispatch/new` | 302, crea shipment |
| SETTINGS | `POST /lens/settings/channels/new` | 302, crea canal |

## 3. Comportamiento modo canonico

Modo B usa app de prueba con:

```text
ATLAS_URL_PREFIX=""
```

Expectativas objetivo probadas:

| Ruta objetivo | Resultado actual | Estado |
|---|---:|---|
| `/` | 200 | Ya funciona |
| `/flow/` | 404 | Falla |
| `/lens/` | 404 | Falla |
| `/lens/coverages/new` | 404 | Falla |
| `/lens/coverages/<coverage_id>` | 404 | Falla |
| `/dispatch/` | 200 | Ya funciona |
| `/settings/` | 200 | Ya funciona |
| `/static/css/main.css` | 200 | Ya funciona |
| `/d/<token>` | 200 | Ya funciona |

## 4. Pruebas que pasan

En `tests.test_atlas_routing_phase1`, pasan 7 de 8 tests de metodo unittest. El test canonico usa subtests y registra 4 fallos dentro del mismo metodo.

Pasan:

```text
test_mode_a_current_production_entrypoints_with_lens_prefix
test_mode_a_current_production_lens_critical_actions_keep_method_and_body
test_mode_a_flow_dispatch_settings_and_public_delivery_posts_keep_body
test_mode_a_flow_to_lens_handoff_keeps_post_body
test_current_unprefixed_legacy_coverages_routes_are_direct_handlers
test_templates_render_url_for_data_attributes_for_lens_actions
test_javascript_uses_data_attributes_instead_of_hardcoded_route_roots
```

En la suite completa, pasan todos los tests existentes salvo los 4 subtest failures canonicos nuevos.

## 5. Pruebas que fallan

Comando dedicado:

```bash
.venv/bin/python -m unittest tests.test_atlas_routing_phase1
```

Resultado:

```text
Ran 8 tests
FAILED (failures=4)
```

Fallos:

| Test | Subtest | Esperado | Actual |
|---|---|---:|---:|
| `test_mode_b_canonical_target_routes_without_prefix` | `/flow/` | 200 | 404 |
| `test_mode_b_canonical_target_routes_without_prefix` | `/lens/` | 200 | 404 |
| `test_mode_b_canonical_target_routes_without_prefix` | `/lens/coverages/new` | 200 | 404 |
| `test_mode_b_canonical_target_routes_without_prefix` | `/lens/coverages/<coverage_id>` | 200 | 404 |

Suite completa:

```bash
.venv/bin/python -m unittest discover -s tests
```

Resultado:

```text
Ran 304 tests
FAILED (failures=4)
```

Los 4 fallos son los mismos subtests canonicos listados arriba.

## 6. Causa de cada fallo canonico

| Ruta canonica fallida | Causa |
|---|---|
| `/flow/` | Flask registra actualmente `@web_bp.get("/flow")`, sin slash final. La ruta objetivo con slash final todavia no esta registrada ni normalizada. |
| `/lens/` | Flask registra actualmente `@web_bp.get("/lens")`, sin slash final. La ruta objetivo con slash final todavia no esta registrada ni normalizada. |
| `/lens/coverages/new` | Las coberturas LENS siguen registradas internamente en `/coverages/new`. Aun no existe alias canonico bajo `/lens/coverages/new`. |
| `/lens/coverages/<coverage_id>` | El detalle LENS sigue registrado internamente en `/coverages/<coverage_id>`. Aun no existe alias canonico bajo `/lens/coverages/<coverage_id>`. |

## 7. Rutas que ya quedan correctas sin prefijo

Con `ATLAS_URL_PREFIX=""`, ya quedan en ubicacion canonica:

| Ruta | Estado |
|---|---|
| `/` | Dashboard canonico ya funciona |
| `/dispatch/` | DISPATCH canonico ya funciona |
| `/settings/` | SETTINGS canonico ya funciona |
| `/static/css/main.css` | Static canonico ya funciona |
| `/d/<token>` | Entrega publica canonica ya funciona |

Adicionalmente, existen hoy rutas sin slash final que funcionan pero no coinciden exactamente con la canonica solicitada:

| Ruta actual sin prefijo | Observacion |
|---|---|
| `/flow` | Funciona, pero objetivo solicitado es `/flow/`. |
| `/lens` | Funciona, pero objetivo solicitado es `/lens/`. |

## 8. Rutas que requieren modificacion Flask

Requieren Fase 1B en Flask:

| Ruta objetivo | Cambio requerido |
|---|---|
| `/flow/` | Anadir slash canonico o normalizacion segura desde `/flow` a `/flow/`. |
| `/lens/` | Anadir slash canonico o normalizacion segura desde `/lens` a `/lens/`. |
| `/lens/coverages/new` | Crear ruta canonica LENS. |
| `/lens/coverages/<coverage_id>` | Crear ruta canonica LENS. |
| `/lens/coverages/<coverage_id>/edit` | Crear ruta canonica POST o alias compatible. |
| `/lens/coverages/<coverage_id>/delete` | Crear ruta canonica POST o alias compatible. |
| `/lens/coverages/<coverage_id>/ai-context` | Crear ruta canonica POST o alias compatible. |
| `/lens/coverages/<coverage_id>/exports` | Crear ruta canonica POST o alias compatible. |
| `/lens/coverages/<coverage_id>/photos` | Crear ruta canonica POST o alias compatible. |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` | Crear ruta canonica GET o alias compatible. |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/media` | Crear ruta canonica GET o alias compatible. |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` | Crear ruta canonica POST o alias compatible. |
| `/lens/coverages/<coverage_id>/captions/copy-caption-empty` | Crear ruta canonica POST o alias compatible. |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` | Crear ruta canonica POST o alias compatible. |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` | Crear ruta canonica GET o alias compatible. |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` | Crear ruta canonica POST o alias compatible. |

## 9. Rutas que requieren Apache

Estas rutas ya pueden existir o prepararse en Flask, pero no deben publicarse como arquitectura final hasta cambiar Apache y retirar/cambiar `ATLAS_URL_PREFIX=/lens`:

| Objetivo publico | Motivo |
|---|---|
| `/` | Hoy el dominio raiz esta servido por Apache/Next.js, no por esta app Flask. |
| `/flow/` | Apache actual publica Flask bajo `/lens...`; necesita proxy nuevo para `/flow/`. |
| `/lens/` | Debe pasar de dashboard actual prefijado a modulo LENS canonico. Requiere coordinacion para no generar `/lens/lens/...`. |
| `/dispatch/` | Flask ya funciona sin prefijo, pero Apache debe publicar `/dispatch/` hacia este backend. |
| `/settings/` | Flask ya funciona sin prefijo, pero Apache debe publicar `/settings/` hacia este backend. |
| `/d/` | Flask ya funciona sin prefijo, pero Apache debe publicar entregas publicas fuera de `/lens/d`. |
| `/static/` | Flask ya funciona sin prefijo, pero Apache debe exponer static fuera de `/lens/static`. |

## 10. Requiere compatibilidad legacy

URLs legacy que deben mantenerse temporalmente:

| Legacy actual | Razon |
|---|---|
| `/lens/` | Dashboard actual en produccion hasta corte. |
| `/lens/flow` | FLOW actual en produccion. |
| `/lens/lens` | LENS actual en produccion. |
| `/lens/coverages/...` | Coberturas LENS productivas actuales. |
| `/lens/dispatch/...` | DISPATCH productivo actual. |
| `/lens/settings/...` | SETTINGS productivo actual. |
| `/lens/static/...` | Assets productivos actuales. |
| `/lens/d/...` | Entregas publicas existentes bajo prefijo. |
| `/coverages/...` | Legacy interno sin prefijo; actualmente es handler directo y luego debera ser alias o redirect hacia `/lens/coverages/...`. |
| `/flow` | Alias/redirect temporal hacia `/flow/`. |
| `/lens` | Alias/redirect temporal hacia `/lens/`. |

## 11. Revision JavaScript y templates

Resultado: no se encontro hardcode peligroso de raices `/coverages`, `/lens/coverages`, `/dispatch`, `/settings`, `/flow` o `/d` en los JS revisados.

Verificado:

| Archivo | Fuente de URL |
|---|---|
| `app/static/js/coverage_delete.js` | `button.dataset.deleteAction` y `deleteForm.action`. |
| `app/static/js/photo_workspace.js` | `photoWorkspace.dataset.photosUrl`, `photoDeleteUrlTemplate`, `photoCaptionUrlTemplate`, `copyCaptionUrl`, `photoAiUrlTemplate`, `photoAiContextUrlTemplate`. |
| `app/static/js/export_panel.js` | `exportSection.dataset.exportUrl`. |

Templates verificados por render:

| Elemento | Resultado con `ATLAS_URL_PREFIX=/lens` |
|---|---|
| `data-photos-url` | `/lens/coverages/<id>/photos` |
| `data-photo-delete-url-template` | `/lens/coverages/<id>/photos/__PHOTO_ID__/delete` |
| `data-photo-caption-url-template` | `/lens/coverages/<id>/photos/__PHOTO_ID__/caption` |
| `data-copy-caption-url` | `/lens/coverages/<id>/captions/copy-caption-empty` |
| `data-photo-ai-url-template` | `/lens/coverages/<id>/photos/__PHOTO_ID__/generate-narration` |
| `data-photo-ai-context-url-template` | `/lens/coverages/<id>/photos/__PHOTO_ID__/ai-context` |
| `data-export-url` | `/lens/coverages/<id>/exports` |
| edit form action | `/lens/coverages/<id>/edit` |

## 12. Riesgos detectados

| Riesgo | Impacto | Mitigacion |
|---|---|---|
| Registrar rutas internas `/lens/coverages/...` mientras `ATLAS_URL_PREFIX=/lens` siga activo | Puede producir URLs publicas `/lens/lens/coverages/...` | En Fase 1B, condicionar generacion canonica o mantener aliases directos hasta el corte Apache. |
| Convertir POST legacy a redirect demasiado pronto | Riesgo para bodies JSON/multipart/autosave | En Fase 1B, no introducir 307/308 todavia salvo tests especificos; preferir handler compatible directo. |
| Slash final en `/flow/` y `/lens/` | Actualmente 404 en objetivo exacto | Anadir canonical slash o aliases seguros con tests. |
| Entregas `/d/...` | Flask ya funciona sin prefijo, pero enlaces existentes pueden vivir en `/lens/d/...` | Mantener compatibilidad legacy hasta corte y revisar `PUBLIC_BASE_URL`. |
| Worktree ya tenia cambios previos | Riesgo de mezclar responsabilidades | Esta fase solo agrego tests e informe; no se revirtieron cambios existentes. |

## 13. Recomendacion exacta para Fase 1B

1. No tocar Apache ni systemd todavia.
2. En Flask, anadir aliases canonicos para `/flow/` y `/lens/` sin romper `/flow` y `/lens`.
3. Para LENS, extraer o reutilizar handlers actuales de `/coverages/...` y registrar tambien `/lens/coverages/...`.
4. Mientras `ATLAS_URL_PREFIX` siga activo, mantener templates apuntando a las rutas productivas actuales para evitar `/lens/lens/coverages/...`.
5. Mantener POST legacy como handler compatible directo en Fase 1B; no introducir redirects 307/308 todavia.
6. Hacer pasar `tests.test_atlas_routing_phase1` sin modificar las expectativas productivas.
7. Solo despues de que las pruebas pasen en ambos modos, preparar la fase Apache/systemd.

## 14. Comandos ejecutados

```bash
.venv/bin/python -m unittest tests.test_atlas_routing_phase1
git diff --check
.venv/bin/python -m unittest discover -s tests
```

Resultados:

```text
.venv/bin/python -m unittest tests.test_atlas_routing_phase1
Ran 8 tests
FAILED (failures=4)

git diff --check
OK

.venv/bin/python -m unittest discover -s tests
Ran 304 tests
FAILED (failures=4)
```

Los fallos son intencionales de caracterizacion del modo canonico aun no implementado.

## 15. git status --short

```text
 M app/__init__.py
 M app/config.py
 M tests/test_lens_persistence_routes.py
?? atlas-convert-prototype.zip
?? atlas_convert_hif_fix_report.md
?? atlas_convert_install_report.md
?? docs/atlas_reverse_proxy_audit.md
?? docs/atlas_routing_audit.md
?? docs/atlas_routing_phase1_plan.md
?? tests/test_atlas_routing_phase1.py
?? tests/test_url_prefix.py
```

Nota: los cambios modificados/no rastreados previos ya existian antes de esta fase, salvo `tests/test_atlas_routing_phase1.py` y este informe.

## 16. Confirmacion de no alteracion de produccion

Confirmado:

- No se modifico `/etc/systemd/system/atlas-lens.service`.
- No se modifico Apache.
- No se modifico DNS.
- No se modifico VPS/firewall/certificados.
- No se modifico Docker ni Proxmox.
- No se hizo deploy.
- No se hizo restart.
- No se hizo commit, push, pull, reset ni checkout.
- No se altero el valor real productivo `ATLAS_URL_PREFIX=/lens`; solo se parcheo en apps temporales de test.
