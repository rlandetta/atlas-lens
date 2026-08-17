# ATLAS Routing Architecture - Phase 1B Results

Fecha: 2026-08-17

Repositorio: `/opt/atlas-lens`

Alcance: cambios Flask locales para soportar rutas canonicas cuando `ATLAS_URL_PREFIX=""`, preservando el comportamiento actual con `ATLAS_URL_PREFIX=/lens`.

## 1. Archivos modificados

Implementacion de esta fase:

| Archivo | Cambio |
|---|---|
| `app/__init__.py` | Agrega aliases canonicos condicionales para modo sin prefijo y los registra sobre los mismos handlers existentes. |
| `docs/atlas_routing_phase1b_results.md` | Informe de resultados de Fase 1B. |

Archivos ya presentes en el worktree antes de esta fase y preservados:

| Archivo | Estado |
|---|---|
| `app/config.py` | Cambio previo de `ATLAS_URL_PREFIX`. |
| `tests/test_lens_persistence_routes.py` | Cambio previo de tests de prefijo. |
| `tests/test_atlas_routing_phase1.py` | Test de Fase 1A usado como base para validar Fase 1B. |

## 2. Arquitectura implementada

Se implemento soporte dual:

| Modo | Comportamiento |
|---|---|
| `ATLAS_URL_PREFIX=/lens` | Se mantienen solo las rutas internas/productivas actuales. No se registran aliases canonicos que produzcan `/lens/lens/...`. |
| `ATLAS_URL_PREFIX=""` | Se registran aliases canonicos adicionales para `/flow/`, `/lens/` y `/lens/coverages/...`. |

Los aliases canonicos se definen en `CANONICAL_ROUTE_ALIASES` y se registran mediante `register_canonical_route_aliases(app)` solo cuando `ATLAS_URL_PREFIX` esta vacio.

## 3. Como se resolvio `/flow/`

La ruta legacy `/flow` permanece en `web_bp`.

En modo sin prefijo se agrega el alias:

```text
/flow/ -> web.flow_home
```

En modo productivo con `/lens`, el alias no se registra. Por eso el mapa publico actual sigue siendo:

```text
/lens/flow -> FLOW
```

No aparece `/flow/flow`.

## 4. Como se resolvio `/lens/`

La ruta legacy interna `/lens` permanece en `web_bp`.

En modo sin prefijo se agrega el alias:

```text
/lens/ -> web.lens_home
```

En produccion actual con `ATLAS_URL_PREFIX=/lens`, el alias no se registra. Por eso el mapa publico actual sigue siendo:

```text
/lens/lens -> LENS
```

No aparece `/lens/lens/lens`.

## 5. Aliases canonicos de coberturas

En modo sin prefijo se agregan aliases para todas las acciones LENS:

| Ruta canonica | Handler reutilizado |
|---|---|
| `/lens/coverages/new` | `web.new_coverage` |
| `/lens/coverages/<coverage_id>` | `web.coverage_detail` |
| `/lens/coverages/<coverage_id>/edit` | `web.edit_coverage` |
| `/lens/coverages/<coverage_id>/ai-context` | `web.save_coverage_ai_context` |
| `/lens/coverages/<coverage_id>/delete` | `web.delete_coverage` |
| `/lens/coverages/<coverage_id>/exports` | `web.create_coverage_export` |
| `/lens/coverages/<coverage_id>/photos` | `web.add_coverage_photo` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` | `web.coverage_photo_thumbnail` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/media` | `web.coverage_photo_media` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` | `web.save_coverage_photo_caption` |
| `/lens/coverages/<coverage_id>/captions/copy-caption-empty` | `web.copy_caption_to_empty_photos` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` | `web.generate_photo_narration` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` | `web.get_photo_ai_context` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` | `web.delete_coverage_photo` |

## 6. Como se evito duplicar logica

No se copiaron handlers ni se introdujo una segunda implementacion funcional.

Cada alias usa:

```python
view_func=app.view_functions[endpoint]
```

Esto significa que la ruta canonica y la legacy llaman al mismo view function, con el mismo manejo de `request.form`, JSON, `FormData`, media, persistencia, IA y exportaciones.

## 7. Comportamiento con `ATLAS_URL_PREFIX=/lens`

Resultado esperado y verificado:

| URL publica actual | Estado |
|---|---|
| `/lens/` | Dashboard actual |
| `/lens/flow` | FLOW |
| `/lens/lens` | LENS |
| `/lens/coverages/...` | Coberturas |
| `/lens/dispatch/...` | DISPATCH |
| `/lens/settings/...` | SETTINGS |
| `/lens/d/...` | Entregas |
| `/lens/static/...` | Static |

El mapa de rutas no contiene:

```text
/lens/lens/coverages/...
/lens/lens/lens
/flow/flow
```

## 8. Comportamiento con `ATLAS_URL_PREFIX=""`

Resultado esperado y verificado:

| Ruta canonica | Estado |
|---|---|
| `/` | Dashboard |
| `/flow/` | FLOW |
| `/lens/` | LENS |
| `/lens/coverages/new` | Nueva cobertura |
| `/lens/coverages/<coverage_id>` | Detalle cobertura |
| `/dispatch/` | DISPATCH |
| `/settings/` | SETTINGS |
| `/d/<token>` | Entrega publica |
| `/static/...` | Static |

Las rutas legacy internas `/coverages/...`, `/flow` y `/lens` siguen disponibles para compatibilidad temporal.

## 9. Resultado de los 8 tests

Comando:

```bash
.venv/bin/python -m unittest tests.test_atlas_routing_phase1
```

Resultado:

```text
Ran 8 tests in 1.659s
OK
```

## 10. Resultado de la suite completa

Comando:

```bash
.venv/bin/python -m unittest discover -s tests
```

Resultado:

```text
Ran 304 tests in 10.493s
OK
```

Tambien se ejecuto:

```bash
git diff --check
```

Resultado: OK.

## 11. Mapa resumido de rutas

### Modo A: `ATLAS_URL_PREFIX=/lens`

| Interna Flask | Publica actual |
|---|---|
| `/` | `/lens/` |
| `/flow` | `/lens/flow` |
| `/lens` | `/lens/lens` |
| `/coverages/new` | `/lens/coverages/new` |
| `/coverages/<coverage_id>` | `/lens/coverages/<coverage_id>` |
| `/coverages/<coverage_id>/...` | `/lens/coverages/<coverage_id>/...` |
| `/dispatch/` | `/lens/dispatch/` |
| `/settings/` | `/lens/settings/` |
| `/d/<token>` | `/lens/d/<token>` |
| `/static/<path>` | `/lens/static/<path>` |

Aliases canonicos `/lens/coverages/...` no se registran en este modo.

### Modo B: `ATLAS_URL_PREFIX=""`

| Ruta | Estado |
|---|---|
| `/` | Canonica |
| `/flow/` | Canonica |
| `/flow` | Legacy compatible |
| `/lens/` | Canonica |
| `/lens` | Legacy compatible |
| `/lens/coverages/...` | Canonica |
| `/coverages/...` | Legacy compatible |
| `/dispatch/` | Canonica |
| `/settings/` | Canonica |
| `/d/<token>` | Canonica |
| `/static/<path>` | Canonica |

Auditoria de duplicaciones:

```text
BAD_DUPLICATES=none
```

en ambos modos.

## 12. Riesgos restantes

| Riesgo | Estado |
|---|---|
| `url_for()` sigue generando rutas legacy de cobertura porque las rutas legacy se conservan como endpoint principal | Intencional en Fase 1B para no romper produccion. En una fase posterior se debe decidir cuando cambiar templates a endpoints canonicos o introducir seleccion dinamica. |
| Apache aun publica la app bajo `/lens` | Debe esperar Fase 2/corte coordinado. |
| Links publicos existentes pueden apuntar a `/lens/d/...` | Mantener compatibilidad hasta cambio de proxy y revisar `PUBLIC_BASE_URL`. |
| Worktree contiene cambios previos no relacionados estrictamente con Fase 1B | No se revirtieron ni tocaron destructivamente. |

## 13. `git status --short`

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
?? docs/atlas_routing_phase1a_results.md
?? docs/atlas_routing_phase1b_results.md
?? tests/test_atlas_routing_phase1.py
?? tests/test_url_prefix.py
```

## 14. `git diff --stat`

```text
 app/__init__.py                       | 84 +++++++++++++++++++++++++++++++++++
 app/config.py                         |  9 ++++
 tests/test_lens_persistence_routes.py | 30 +++++++++++++
 3 files changed, 123 insertions(+)
```

Nota: `git diff --stat` no lista archivos no rastreados como este informe o `tests/test_atlas_routing_phase1.py`.

## 15. Confirmacion de no modificacion productiva externa

Confirmado:

- No se modifico Apache.
- No se modifico `/etc/systemd/system/atlas-lens.service`.
- No se modifico DNS.
- No se modifico VPS.
- No se modifico firewall.
- No se modificaron certificados.
- No se modifico Docker.
- No se modifico Proxmox.
- No se hizo deploy.
- No se hizo restart.
- No se hizo push, pull, reset ni checkout.
- No se cambio el valor productivo real de `ATLAS_URL_PREFIX=/lens`.
