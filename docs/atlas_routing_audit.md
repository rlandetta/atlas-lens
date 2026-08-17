# ATLAS Routing Audit

Fecha de auditoria: 2026-08-16
Repositorio auditado: `/opt/atlas-lens`
Alcance: solo lectura del estado actual del proyecto, con creacion de este informe.

## 1. Estado actual de la arquitectura

ATLAS Lens es actualmente una aplicacion Flask unica que sirve varias superficies funcionales desde el mismo proceso:

- Dashboard general ATLAS.
- FLOW.
- LENS.
- DISPATCH.
- SETTINGS.
- Links publicos de descarga DISPATCH bajo `/d/<token>`.
- Archivos estaticos bajo `/static/...`.

La aplicacion interna no esta organizada como una app independiente por modulo a nivel de montaje WSGI. En su lugar:

- `web_bp` no tiene `url_prefix` y declara rutas raiz, FLOW, LENS y coberturas.
- `dispatch_bp` usa `url_prefix="/dispatch"`.
- `settings_bp` usa `url_prefix="/settings"`.
- `downloads_bp` no tiene `url_prefix` y declara `/d/...`.

En produccion, `atlas-lens.service` define:

```ini
Environment=ATLAS_URL_PREFIX=/lens
```

Con el estado actual del codigo, ese prefijo global activa `UrlPrefixMiddleware` y `APPLICATION_ROOT=/lens`. El resultado publico actual queda conceptualmente asi:

- `/lens/` sirve el dashboard general ATLAS.
- `/lens/flow` sirve FLOW.
- `/lens/lens` sirve el listado LENS.
- `/lens/dispatch/` sirve DISPATCH.
- `/lens/settings/` sirve SETTINGS.
- `/lens/static/...` sirve assets estaticos.
- `/lens/d/<token>` sirve links publicos de descarga si la request entra por el prefijo.

La arquitectura publica objetivo solicitada es:

- `/` -> Dashboard general ATLAS.
- `/flow/` -> FLOW.
- `/lens/` -> LENS.
- `/dispatch/` -> DISPATCH.
- `/settings/` -> SETTINGS.

La incompatibilidad central es que la URL publica actual `/lens/` significa "dashboard", pero la URL objetivo `/lens/` debe significar "modulo LENS".

## 2. Mapa completo de rutas actuales

Este mapa se genero desde `app.url_map` del estado actual. La columna "ruta interna" es la regla Flask sin considerar `ATLAS_URL_PREFIX`. La columna "URL publica actual" asume `ATLAS_URL_PREFIX=/lens`, como esta definido en `atlas-lens.service`.

| Endpoint Flask | Metodo | Ruta interna | URL publica actual | Modulo | URL publica objetivo |
|---|---:|---|---|---|---|
| `web.home` | GET | `/` | `/lens/` | Dashboard | `/` |
| `web.flow_home` | GET | `/flow` | `/lens/flow` | FLOW | `/flow/` |
| `web.flow_photo_thumbnail` | GET | `/flow/photos/<photo_id>/thumbnail` | `/lens/flow/photos/<photo_id>/thumbnail` | FLOW | `/flow/photos/<photo_id>/thumbnail` |
| `web.flow_new_coverage` | GET, POST | `/flow/sessions/<session_id>/coverage/new` | `/lens/flow/sessions/<session_id>/coverage/new` | FLOW/LENS handoff | `/flow/sessions/<session_id>/coverage/new` |
| `web.flow_open_lens` | POST | `/flow/sessions/<session_id>/lens/open` | `/lens/flow/sessions/<session_id>/lens/open` | FLOW/LENS handoff | `/flow/sessions/<session_id>/lens/open` |
| `web.lens_home` | GET | `/lens` | `/lens/lens` | LENS | `/lens/` |
| `web.new_coverage` | GET, POST | `/coverages/new` | `/lens/coverages/new` | LENS | `/lens/coverages/new` |
| `web.coverage_detail` | GET | `/coverages/<coverage_id>` | `/lens/coverages/<coverage_id>` | LENS | `/lens/coverages/<coverage_id>` |
| `web.edit_coverage` | POST | `/coverages/<coverage_id>/edit` | `/lens/coverages/<coverage_id>/edit` | LENS | `/lens/coverages/<coverage_id>/edit` |
| `web.save_coverage_ai_context` | POST | `/coverages/<coverage_id>/ai-context` | `/lens/coverages/<coverage_id>/ai-context` | LENS | `/lens/coverages/<coverage_id>/ai-context` |
| `web.delete_coverage` | POST | `/coverages/<coverage_id>/delete` | `/lens/coverages/<coverage_id>/delete` | LENS | `/lens/coverages/<coverage_id>/delete` |
| `web.create_coverage_export` | POST | `/coverages/<coverage_id>/exports` | `/lens/coverages/<coverage_id>/exports` | LENS export | `/lens/coverages/<coverage_id>/exports` |
| `web.add_coverage_photo` | POST | `/coverages/<coverage_id>/photos` | `/lens/coverages/<coverage_id>/photos` | LENS AJAX | `/lens/coverages/<coverage_id>/photos` |
| `web.coverage_photo_thumbnail` | GET | `/coverages/<coverage_id>/photos/<photo_id>/thumbnail` | `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` | LENS media | `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` |
| `web.coverage_photo_media` | GET | `/coverages/<coverage_id>/photos/<photo_id>/media` | `/lens/coverages/<coverage_id>/photos/<photo_id>/media` | LENS media | `/lens/coverages/<coverage_id>/photos/<photo_id>/media` |
| `web.save_coverage_photo_caption` | POST | `/coverages/<coverage_id>/photos/<photo_id>/caption` | `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` | LENS captions | `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` |
| `web.copy_caption_to_empty_photos` | POST | `/coverages/<coverage_id>/captions/copy-caption-empty` | `/lens/coverages/<coverage_id>/captions/copy-caption-empty` | LENS captions | `/lens/coverages/<coverage_id>/captions/copy-caption-empty` |
| `web.generate_photo_narration` | POST | `/coverages/<coverage_id>/photos/<photo_id>/generate-narration` | `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` | LENS AI | `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` |
| `web.get_photo_ai_context` | GET | `/coverages/<coverage_id>/photos/<photo_id>/ai-context` | `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` | LENS AI | `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` |
| `web.delete_coverage_photo` | POST | `/coverages/<coverage_id>/photos/<photo_id>/delete` | `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` | LENS media | `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` |
| `dispatch.index` | GET | `/dispatch/` | `/lens/dispatch/` | DISPATCH | `/dispatch/` |
| `dispatch.new` | GET, POST | `/dispatch/new` | `/lens/dispatch/new` | DISPATCH | `/dispatch/new` |
| `dispatch.detail` | GET | `/dispatch/<shipment_id>` | `/lens/dispatch/<shipment_id>` | DISPATCH | `/dispatch/<shipment_id>` |
| `dispatch.edit` | GET, POST | `/dispatch/<shipment_id>/edit` | `/lens/dispatch/<shipment_id>/edit` | DISPATCH | `/dispatch/<shipment_id>/edit` |
| `dispatch.duplicate` | POST | `/dispatch/<shipment_id>/duplicate` | `/lens/dispatch/<shipment_id>/duplicate` | DISPATCH | `/dispatch/<shipment_id>/duplicate` |
| `dispatch.cancel` | POST | `/dispatch/<shipment_id>/cancel` | `/lens/dispatch/<shipment_id>/cancel` | DISPATCH | `/dispatch/<shipment_id>/cancel` |
| `dispatch.revoke_delivery_link` | POST | `/dispatch/<shipment_id>/delivery-link/revoke` | `/lens/dispatch/<shipment_id>/delivery-link/revoke` | DISPATCH | `/dispatch/<shipment_id>/delivery-link/revoke` |
| `dispatch.regenerate_delivery_link` | POST | `/dispatch/<shipment_id>/delivery-link/regenerate` | `/lens/dispatch/<shipment_id>/delivery-link/regenerate` | DISPATCH | `/dispatch/<shipment_id>/delivery-link/regenerate` |
| `dispatch.delete` | POST | `/dispatch/<shipment_id>/delete` | `/lens/dispatch/<shipment_id>/delete` | DISPATCH | `/dispatch/<shipment_id>/delete` |
| `dispatch.delete_cancelled` | POST | `/dispatch/delete-cancelled` | `/lens/dispatch/delete-cancelled` | DISPATCH | `/dispatch/delete-cancelled` |
| `settings.index` | GET | `/settings/` | `/lens/settings/` | SETTINGS | `/settings/` |
| `settings.channels` | GET | `/settings/channels` | `/lens/settings/channels` | SETTINGS | `/settings/channels` |
| `settings.new_channel` | GET, POST | `/settings/channels/new` | `/lens/settings/channels/new` | SETTINGS | `/settings/channels/new` |
| `settings.edit_channel` | GET, POST | `/settings/channels/<channel_id>/edit` | `/lens/settings/channels/<channel_id>/edit` | SETTINGS | `/settings/channels/<channel_id>/edit` |
| `settings.delete_channel` | POST | `/settings/channels/<channel_id>/delete` | `/lens/settings/channels/<channel_id>/delete` | SETTINGS | `/settings/channels/<channel_id>/delete` |
| `downloads.landing` | GET | `/d/<token>` | `/lens/d/<token>` | Public delivery | `/d/<token>` |
| `downloads.preview` | GET | `/d/<token>/preview/<preview_id>` | `/lens/d/<token>/preview/<preview_id>` | Public delivery | `/d/<token>/preview/<preview_id>` |
| `downloads.download_zip` | GET | `/d/<token>/download` | `/lens/d/<token>/download` | Public delivery | `/d/<token>/download` |
| `downloads.download_file` | GET | `/d/<token>/file/<file_id>` | `/lens/d/<token>/file/<file_id>` | Public delivery | `/d/<token>/file/<file_id>` |
| `static` | GET | `/static/<path:filename>` | `/lens/static/<path:filename>` | Static | `/static/<path:filename>` |

## 3. Mapa de rutas objetivo

La migracion objetivo debe publicar los modulos en raiz de dominio:

| Modulo | URL objetivo | Endpoint principal |
|---|---|---|
| Dashboard ATLAS | `/` | `web.home` |
| FLOW | `/flow/` | `web.flow_home` |
| LENS | `/lens/` | `web.lens_home` |
| DISPATCH | `/dispatch/` | `dispatch.index` |
| SETTINGS | `/settings/` | `settings.index` |
| Links publicos de entrega | `/d/<token>` | `downloads.landing` |
| Static | `/static/...` | `static` |

Para LENS, una decision de diseno sigue pendiente: hoy las subrutas de cobertura son internas `/coverages/...`. En el objetivo modular limpio, conviene que permanezcan publicamente bajo `/lens/coverages/...` para que el modulo LENS sea autocontenido. Eso requiere mover las rutas internas de cobertura bajo un `url_prefix="/lens"` o introducir rutas alias/redirects. No debe resolverse de forma parcial durante la auditoria.

## 4. Matriz URL actual -> URL objetivo

| URL actual | URL objetivo |
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
| `/lens/coverages/<coverage_id>/delete` | `/lens/coverages/<coverage_id>/delete` |
| `/lens/coverages/<coverage_id>/exports` | `/lens/coverages/<coverage_id>/exports` |
| `/lens/coverages/<coverage_id>/photos` | `/lens/coverages/<coverage_id>/photos` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` | `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` |
| `/lens/coverages/<coverage_id>/captions/copy-caption-empty` | `/lens/coverages/<coverage_id>/captions/copy-caption-empty` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` | `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` | `/lens/coverages/<coverage_id>/photos/<photo_id>/ai-context` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` | `/lens/coverages/<coverage_id>/photos/<photo_id>/thumbnail` |
| `/lens/coverages/<coverage_id>/photos/<photo_id>/media` | `/lens/coverages/<coverage_id>/photos/<photo_id>/media` |
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

## 5. Funcionamiento actual de `ATLAS_URL_PREFIX`

`ATLAS_URL_PREFIX` se define en `app/config.py`:

```python
ATLAS_URL_PREFIX = get_url_prefix_env("ATLAS_URL_PREFIX")
```

`get_url_prefix_env()`:

- lee el valor del entorno;
- aplica `strip()`;
- garantiza slash inicial;
- elimina slash final;
- devuelve `""` si el resultado seria `/`.

`ATLAS_URL_PREFIX` se consume en `app/__init__.py`:

```python
if ATLAS_URL_PREFIX:
    app.config["APPLICATION_ROOT"] = ATLAS_URL_PREFIX
    app.wsgi_app = UrlPrefixMiddleware(app.wsgi_app, ATLAS_URL_PREFIX)
```

Efectos actuales:

- `APPLICATION_ROOT=/lens` hace que `url_for()` genere URLs con prefijo cuando Flask conoce el `SCRIPT_NAME`.
- `UrlPrefixMiddleware` acepta requests entrantes con path `/lens` o `/lens/...`, mueve ese prefijo a `SCRIPT_NAME` y deja a Flask resolver el resto como ruta interna.
- Static tambien queda bajo el prefijo, por ejemplo `/lens/static/css/main.css`.
- Redirects via `url_for()` heredan el prefijo, por ejemplo delete coverage redirige a `/lens/lens` cuando el prefijo esta activo.
- No hay uso de `ProxyFix` ni lectura de `X-Forwarded-Prefix`.

El middleware tambien contempla el caso en que un proxy ya haya establecido `SCRIPT_NAME=/lens`, pero no recorta path si el request no llega con `/lens` en `PATH_INFO`.

## 6. Configuracion relevante de Flask

Puntos observados:

- `Flask(__name__)` sin `static_url_path` custom.
- Static route por defecto: `/static/<path:filename>`.
- Registro de blueprints:
  - `web_bp`: sin `url_prefix`.
  - `dispatch_bp`: `url_prefix="/dispatch"`.
  - `downloads_bp`: sin `url_prefix`.
  - `settings_bp`: `url_prefix="/settings"`.
- Navegacion global en `ATLAS_NAVIGATION`:
  - Dashboard -> `web.home`.
  - FLOW -> `web.flow_home`.
  - LENS -> `web.lens_home`.
  - DISPATCH -> `dispatch.index`.
  - SETTINGS -> `settings.index`.
- El contexto global inyecta `atlas_navigation` y `_header.html` usa `url_for(item.endpoint)`.

Implicacion: al quitar `ATLAS_URL_PREFIX`, las rutas internas actuales se publicaran tal como estan. Eso arregla Dashboard, FLOW, DISPATCH, SETTINGS y static, pero deja una decision pendiente sobre si las coberturas deben quedar en `/coverages/...` o moverse/aliasarse a `/lens/coverages/...`.

## 7. Configuracion relevante de Nginx/reverse proxy

En este host no existe `/etc/nginx`:

```text
ls: cannot access '/etc/nginx': No such file or directory
```

La busqueda en `/etc` no encontro configuracion Nginx, Caddy, Traefik ni archivos de sitio relacionados con ATLAS. Por tanto:

- No se pudo identificar en este host ningun `server_name atlas.lavoceria.com`.
- No se pudo identificar `location /lens`, `location /flow`, `location /dispatch` ni `location /settings`.
- No se pudo confirmar si el reverse proxy conserva o recorta prefijos.
- No se encontro `proxy_pass` local hacia `127.0.0.1:5001`.

Inferencia operacional: el reverse proxy puede estar en otra maquina, contenedor, VM, host Proxmox o proveedor externo. Antes de migrar en produccion se debe auditar ese punto fuera de este filesystem.

## 8. Configuracion relevante de `atlas-lens.service`

Archivo leido: `/etc/systemd/system/atlas-lens.service`

```ini
[Unit]
Description=ATLAS LENS Editorial Application
After=network.target
Wants=network.target

[Service]
Type=simple
User=atlas
WorkingDirectory=/opt/atlas-lens
Environment=PYTHONUNBUFFERED=1
Environment=ATLAS_URL_PREFIX=/lens
ExecStart=/opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Puntos relevantes:

- `WorkingDirectory=/opt/atlas-lens`.
- `ExecStart` usa Flask CLI directamente.
- Puerto interno: `5001`.
- Host interno: `0.0.0.0`.
- `ATLAS_URL_PREFIX=/lens` esta definido en systemd, no en un archivo `.env` observado.
- El nombre del servicio sigue siendo `atlas-lens.service` aunque sirve mas que LENS.

## 9. Inventario de `url_for`, redirects, fetch, form actions y URLs hardcodeadas

### Referencias que usan `url_for()` correctamente

Estas referencias deberian adaptarse automaticamente al cambio de `APPLICATION_ROOT` mientras se mantengan endpoints coherentes:

- `_header.html`: marca ATLAS a `web.home`; nav global por `item.endpoint`.
- `base.html`: CSS principal con `url_for("static", ...)`.
- `index.html`: CTAs a `web.flow_home`, `web.lens_home`, `dispatch.index`.
- `lens_index.html`: crear, abrir, editar y borrar coberturas con `url_for`.
- `coverage_detail.html`: crear despacho, contexto IA, volver a coberturas, data URLs AJAX, export, edit, scripts estaticos.
- `flow/index.html`: usa URLs preconstruidas por Python desde `url_for`.
- `flow/new_coverage.html`: volver a FLOW con `url_for`.
- `dispatch/*.html`: formularios, acciones, filtros y links con `url_for`.
- `settings/*.html`: formularios, acciones y links con `url_for`.
- `downloads/landing.html`: assets y descargas con `url_for`.
- `app/routes/web.py`, `dispatch.py`, `settings.py`, `downloads.py`: redirects y URLs internas con `url_for`.

### Fetch y URLs derivadas de data attributes

Estos dependen de que el HTML haya sido generado correctamente con `url_for()`:

- `coverage_delete.js`: `fetch(deleteForm.action)`; action viene de `data-delete-action` en `lens_index.html`.
- `export_panel.js`: `fetch(exportSection.dataset.exportUrl)`.
- `photo_workspace.js`:
  - `photoWorkspace.dataset.photosUrl`.
  - `data-photo-delete-url-template`.
  - `data-photo-caption-url-template`.
  - `data-copy-caption-url`.
  - `data-photo-ai-url-template`.
  - `data-photo-ai-context-url-template`.

Riesgo: si durante la migracion se cambian rutas internas sin actualizar los `url_for()` que generan los data attributes, los fetch fallaran de forma silenciosa o con mensajes de conexion/HTTP.

### URL hardcodeadas o dependientes de path

- `app/dispatch/delivery_links.py` construye `path = f"/d/{token}"`. Si `PUBLIC_BASE_URL` esta vacio, genera `/d/<token>` sin `ATLAS_URL_PREFIX`. Con el deployment actual bajo `/lens`, esto puede producir links publicos incompatibles si el proxy no expone `/d`.
- Tests contienen muchas URLs hardcodeadas (`/lens`, `/dispatch/`, `/settings/`, `/flow`, `/coverages/...`). Son utiles para documentar comportamiento, pero deberan actualizarse o dividirse entre compatibilidad legacy y objetivo.
- `tests/test_url_prefix.py` documenta explicitamente que con prefijo `/lens`, LENS vive en `/lens/lens`; esto se volvera legado.
- `coverage_detail.html` tiene un enlace de Configuracion como `href="#"`, no es una ruta real.
- `new_coverage.html` contiene `Volver a coberturas` apuntando a `web.home`; en estado actual eso envia al dashboard. Esto debe revisarse fuera de esta auditoria si se busca consistencia UX.

### Riesgos por redirects

- `web.delete_coverage` redirige a `web.lens_home`; con prefijo actual genera `/lens/lens`, objetivo `/lens`.
- Creacion de cobertura redirige a `web.coverage_detail`; con objetivo modular conviene decidir si eso debe ser `/lens/coverages/<id>` en vez de `/coverages/<id>`.
- FLOW handoff redirige a `web.coverage_detail`; mismo riesgo de ubicacion modular.
- DISPATCH redirects usan `dispatch.*` y deberian migrar bien si se elimina el prefijo global.
- SETTINGS redirects usan `settings.*` y deberian migrar bien si se elimina el prefijo global.

## 10. Rutas de Dashboard, FLOW, LENS, DISPATCH y SETTINGS

### Dashboard ATLAS

- Endpoint principal: `web.home`.
- Ruta interna: `/`.
- URL publica actual: `/lens/`.
- URL objetivo: `/`.
- Riesgo: colisiona con el significado objetivo de `/lens/`.

### FLOW

- Endpoint principal: `web.flow_home`.
- Ruta interna: `/flow`.
- URL publica actual: `/lens/flow`.
- URL objetivo: `/flow/`.
- Endpoints relacionados:
  - `/flow/photos/<photo_id>/thumbnail`.
  - `/flow/sessions/<session_id>/coverage/new`.
  - `/flow/sessions/<session_id>/lens/open`.

### LENS

- Endpoint listado: `web.lens_home`.
- Ruta interna: `/lens`.
- URL publica actual: `/lens/lens`.
- URL objetivo: `/lens/`.
- Rutas de cobertura actuales:
  - `/coverages/new`.
  - `/coverages/<coverage_id>`.
  - `/coverages/<coverage_id>/edit`.
  - `/coverages/<coverage_id>/delete`.
  - `/coverages/<coverage_id>/exports`.
  - `/coverages/<coverage_id>/photos...`.
- Decision pendiente: mantener `/coverages/...` como ruta raiz interna o mover/aliasar a `/lens/coverages/...` para modularidad publica.

### DISPATCH

- Blueprint: `dispatch_bp`, `url_prefix="/dispatch"`.
- Endpoint principal: `dispatch.index`.
- Ruta interna: `/dispatch/`.
- URL publica actual: `/lens/dispatch/`.
- URL objetivo: `/dispatch/`.
- Links publicos de descarga no viven bajo el blueprint dispatch sino bajo `downloads_bp`.

### SETTINGS

- Blueprint: `settings_bp`, `url_prefix="/settings"`.
- Endpoint principal: `settings.index`.
- Ruta interna: `/settings/`.
- URL publica actual: `/lens/settings/`.
- URL objetivo: `/settings/`.

## 11. Riesgos e incompatibilidades encontrados

1. Colision critica `/lens/`.
   - Actual: `/lens/` -> dashboard.
   - Objetivo: `/lens/` -> LENS.
   - Requiere redirects de compatibilidad y comunicacion clara.

2. Duplicacion actual `/lens/lens`.
   - Es consecuencia directa de montar toda la app bajo `/lens` y tener un modulo interno tambien en `/lens`.
   - Debe ser legacy y redirigir a `/lens/` tras migracion.

3. Coberturas no estan bajo un prefijo interno LENS.
   - Internamente son `/coverages/...`.
   - Si se elimina el prefijo global sin mas cambios, se publicaran como `/coverages/...`, fuera del espacio modular `/lens/...`.
   - Recomendacion: exponer objetivo `/lens/coverages/...` y redirigir legacy `/lens/coverages/...` hacia el mismo path objetivo si se conserva, o `/coverages/...` hacia `/lens/coverages/...` durante transicion.

4. Links publicos `/d/<token>` pueden depender de `PUBLIC_BASE_URL`.
   - `DeliveryLinkService.with_url()` hardcodea path `/d/<token>`.
   - Si hoy la app solo es accesible bajo `/lens`, los enlaces con `PUBLIC_BASE_URL` vacio no incluyen `/lens`.
   - En objetivo esto es correcto, pero durante transicion puede haber links vivos en ambos esquemas.

5. Nginx/proxy no esta presente en este host.
   - No se puede garantizar que el proxy de produccion acepte `/`, `/flow`, `/dispatch`, `/settings` sin modificarlo.
   - Tampoco se sabe si actualmente recorta `/lens` o lo pasa intacto.

6. Tests existentes documentan comportamiento legacy.
   - `tests/test_url_prefix.py` espera `/lens/lens` con prefijo `/lens`.
   - La migracion debera actualizar tests para objetivo y agregar tests de redirects legacy.

7. Static puede romperse si el proxy conserva un prefijo no coordinado.
   - Hoy `url_for("static")` bajo `APPLICATION_ROOT=/lens` produce `/lens/static/...`.
   - Objetivo sin prefijo produce `/static/...`.

8. Cambios pendientes en working tree.
   - El repositorio contiene cambios staged y unstaged de tareas previas.
   - La migracion de rutas no deberia iniciarse hasta limpiar o acordar el alcance del index.

## 12. Estrategia de compatibilidad con URLs antiguas

La estrategia mas segura es separar "rutas objetivo" de "rutas legacy":

1. Quitar el montaje global `ATLAS_URL_PREFIX=/lens` para que la app pueda responder en raiz.
2. Mantener endpoints objetivo canonicos:
   - `/` dashboard.
   - `/flow/` FLOW.
   - `/lens/` LENS.
   - `/dispatch/` DISPATCH.
   - `/settings/` SETTINGS.
   - `/d/<token>` descargas.
3. Agregar redirects legacy permanentes o temporales, idealmente HTTP 308 para preservar metodo en rutas POST donde aplique y 301/302 para GET segun politica:
   - `/lens/lens` -> `/lens/`.
   - `/lens/lens/...` -> `/lens/...` si existen subrutas futuras bajo LENS.
   - `/lens/flow/...` -> `/flow/...`.
   - `/lens/dispatch/...` -> `/dispatch/...`.
   - `/lens/settings/...` -> `/settings/...`.
   - `/lens/static/...` -> `/static/...` o servir ambos durante un periodo corto.
   - `/lens/d/...` -> `/d/...`.
4. Manejar especialmente `/lens/` legacy:
   - Hoy es dashboard.
   - Objetivo sera LENS.
   - No puede redirigirse automaticamente a `/` sin romper el objetivo.
   - Recomendacion: en el momento del corte, aceptar que `/lens/` cambia de significado y mantener compatibilidad del dashboard antiguo mediante `/atlas` o una pagina transitoria solo si se considera necesario. La opcion limpia es documentar que dashboard antiguo `/lens/` pasa a `/`.
5. Para acciones POST legacy, evitar 301/302 porque pueden convertir POST a GET en algunos clientes. Usar 307/308 o soportar rutas legacy directamente durante una ventana de compatibilidad.

## 13. Plan de migracion recomendado por fases

### Fase 0: congelar base de cambios

- Resolver o aislar el staging actual.
- Crear una rama o commit base limpio antes de tocar rutas.
- Auditar reverse proxy real de `atlas.lavoceria.com`.
- Confirmar si `PUBLIC_BASE_URL` esta configurado en produccion.

### Fase 1: preparar la aplicacion para funcionar sin prefijo global

- Hacer opcional `ATLAS_URL_PREFIX` en systemd/env y probar con valor vacio.
- Mantener `UrlPrefixMiddleware` temporalmente para entornos legacy, pero no depender de el.
- Agregar tests para `ATLAS_URL_PREFIX=""` como caso principal.
- Verificar `url_for()` para static, nav global, fetch y redirects.

### Fase 2: definir rutas canonicas modulares

- Dashboard: `/`.
- FLOW: `/flow/`.
- LENS: `/lens/`.
- DISPATCH: `/dispatch/`.
- SETTINGS: `/settings/`.
- Decidir y aplicar estructura canonica de LENS detail:
  - Recomendada: `/lens/coverages/...`.
  - Requiere mover/aliasar rutas de `web.coverage_*`.

### Fase 3: exponer nuevas URLs publicas en reverse proxy

- Configurar el proxy para pasar `/`, `/flow`, `/lens`, `/dispatch`, `/settings`, `/static` y `/d` al servicio Flask en `127.0.0.1:5001`.
- Evitar doble recorte de prefijo si se elimina `ATLAS_URL_PREFIX`.
- Validar que headers `Host`, `X-Forwarded-Proto` y, si se usa, `X-Forwarded-Prefix`, sean coherentes.

### Fase 4: compatibilidad legacy

- Agregar redirects o rutas legacy para:
  - `/lens/lens` -> `/lens/`.
  - `/lens/flow/...` -> `/flow/...`.
  - `/lens/dispatch/...` -> `/dispatch/...`.
  - `/lens/settings/...` -> `/settings/...`.
  - `/lens/d/...` -> `/d/...`.
  - `/lens/static/...` -> `/static/...`.
- Para POST legacy, usar 307/308 o handlers compat directos.
- Definir ventana de deprecacion.

### Fase 5: actualizar enlaces internos y tests

- Ajustar todos los tests que esperan `/lens/lens`.
- Agregar tests objetivo y tests legacy.
- Validar que `url_for()` genere rutas canonicas.
- Revisar links publicos de entrega generados antes de la migracion.

### Fase 6: verificacion manual y observabilidad

- Probar navegacion completa en navegador.
- Revisar logs por 404/405 en rutas legacy.
- Verificar descargas publicas.
- Verificar acciones POST: delete coverage, caption autosave, export, dispatch, settings.

## 14. Checklist de pruebas posteriores a la migracion

- `GET /` devuelve dashboard.
- `GET /lens/` devuelve listado de coberturas LENS.
- `GET /flow/` devuelve FLOW.
- `GET /dispatch/` devuelve DISPATCH.
- `GET /settings/` devuelve SETTINGS.
- Header global genera links sin duplicacion `/lens/lens`.
- Static carga desde `/static/...`.
- Crear cobertura redirige al detalle canonico.
- Abrir cobertura desde LENS funciona.
- Editar cobertura funciona.
- Eliminar cobertura funciona con confirmacion real.
- Upload de fotos funciona.
- Thumbnail y media de cobertura funcionan.
- Caption autosave funciona.
- IA narration/context endpoints funcionan si AI esta habilitado.
- Copy caption funciona.
- Export download funciona.
- Export to dispatch funciona.
- Crear dispatch desde cobertura funciona.
- DISPATCH new/detail/edit/duplicate/cancel/delete funcionan.
- SETTINGS channels new/edit/delete funcionan.
- Delivery link `/d/<token>` funciona.
- Legacy `/lens/lens` redirige o funciona segun estrategia.
- Legacy `/lens/flow` redirige o funciona.
- Legacy `/lens/dispatch` redirige o funciona.
- Legacy `/lens/settings` redirige o funciona.
- Legacy `/lens/d/<token>` redirige o funciona.
- Legacy POST routes preservan metodo o tienen handler dedicado.
- No hay 404/405 inesperados en logs inmediatos.
- `PUBLIC_BASE_URL` produce links publicos correctos.
- Tests de prefijo legacy y sin prefijo pasan.

## 15. Observaciones tecnicas antes de modificar arquitectura

- La migracion no deberia empezar mientras haya cambios staged/unstaged mezclados, salvo que se acuerde explicitamente el alcance.
- `atlas-lens.service` sirve toda la plataforma ATLAS actual aunque su nombre sugiere solo LENS. Renombrar el servicio no es necesario para la migracion, pero debe documentarse.
- Flask CLI se usa como servidor del servicio. Esto no afecta la ruta, pero es una consideracion operacional si se endurece produccion.
- La ausencia de Nginx local impide validar la capa publica real. La migracion requiere encontrar la configuracion del dominio `atlas.lavoceria.com` antes del corte.
- Si se cambia `ATLAS_URL_PREFIX` a vacio sin rutas alias para coberturas, LENS quedara parcialmente en `/lens` y parcialmente en `/coverages`. Eso puede funcionar, pero no es una arquitectura modular limpia.
- La decision mas importante antes de implementar es si LENS debe poseer publicamente todas sus subrutas bajo `/lens/...`.
- Los enlaces de descarga `/d/<token>` son publicos y pueden estar ya enviados a terceros. Deben tener compatibilidad legacy especial.
- Cualquier redirect de acciones POST debe preservar metodo y body.
- Los fetch del frontend dependen de data attributes generados por `url_for`; evitar hardcodear rutas nuevas en JS.
