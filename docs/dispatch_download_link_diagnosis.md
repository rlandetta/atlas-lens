# DISPATCH Download Link Diagnosis

Fecha: 2026-08-18

## Alcance

Diagnostico de solo lectura del problema reportado en DISPATCH: el link/boton de descarga no lleva a un destino util o, al copiar el enlace generado, no aparece el contenido esperado.

No se modifico codigo, Apache, permisos, Proxmox/VirtioFS, datos, servicios ni Git.

## Arquitectura Actual De DISPATCH

### Rutas Flask

DISPATCH administrativo:

```text
dispatch.index                         GET       /dispatch/
dispatch.new                           GET,POST  /dispatch/new
dispatch.detail                        GET       /dispatch/<shipment_id>
dispatch.edit                          GET,POST  /dispatch/<shipment_id>/edit
dispatch.duplicate                     POST      /dispatch/<shipment_id>/duplicate
dispatch.cancel                        POST      /dispatch/<shipment_id>/cancel
dispatch.revoke_delivery_link          POST      /dispatch/<shipment_id>/delivery-link/revoke
dispatch.regenerate_delivery_link      POST      /dispatch/<shipment_id>/delivery-link/regenerate
dispatch.delete                        POST      /dispatch/<shipment_id>/delete
dispatch.delete_cancelled              POST      /dispatch/delete-cancelled
```

Entregas publicas:

```text
downloads.landing       GET  /d/<token>
downloads.preview       GET  /d/<token>/preview/<preview_id>
downloads.download_zip  GET  /d/<token>/download
downloads.download_file GET  /d/<token>/file/<file_id>
```

### Archivos Implicados

```text
app/routes/dispatch.py
app/routes/downloads.py
app/dispatch/delivery_links.py
app/dispatch/delivery_package.py
app/templates/dispatch/detail.html
app/templates/downloads/landing.html
app/static/js/delivery_backgrounds.js
instance/dispatch_shipments.json
instance/delivery_links.json
instance/deliveries/<shipment_id>/
```

### Flujo Funcional

1. El usuario crea o regenera una entrega en DISPATCH.
2. `prepare_download_link_delivery()` prepara el paquete con `DeliveryPackageService.prepare_package()`.
3. Los archivos se copian en `DELIVERY_ROOT`, actualmente `instance/deliveries`.
4. Se crea/regenera un token con `DeliveryLinkService.regenerate_for_shipment()`.
5. `DeliveryLinkService.with_url()` construye el valor mostrado como enlace.
6. La vista de detalle renderiza ese valor en `app/templates/dispatch/detail.html`.
7. El usuario abre `/d/<token>`.
8. `app/routes/downloads.py` resuelve token, shipment, manifest y archivos.
9. `/d/<token>/download` entrega el ZIP con `send_file()`.
10. `/d/<token>/file/<file_id>` entrega un archivo individual con `send_file()`.

## Entrega Inspeccionada

Shipment:

```text
ship-20260815040520-3170
```

Nombre:

```text
QUITO-DRONE
```

Token activo:

```text
uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk
```

## URL Generada

La pantalla de detalle publica actualmente:

```html
<input class="dispatch-link-field" type="text" value="/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk" readonly>
<a href="/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk" target="_blank" rel="noopener">Abrir</a>
```

La URL generada es relativa:

```text
/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk
```

La URL publica esperada para copiar/compartir es absoluta:

```text
https://atlas.lavoceria.com/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk
```

## Causa Exacta

`PUBLIC_BASE_URL` no esta definido en runtime.

La unidad actual de `atlas-lens.service` contiene:

```text
Environment=ATLAS_URL_PREFIX=
```

No contiene `PUBLIC_BASE_URL`.

En `app/dispatch/delivery_links.py`, `DeliveryLinkService.with_url()` construye:

```python
path = f"/d/{enriched.get('token', '')}"
enriched["url"] = f"{self.public_base_url}{path}" if self.public_base_url else path
```

Como `PUBLIC_BASE_URL` esta vacio, la URL guardada/renderizada queda como path relativo `/d/<token>`. Eso funciona si se pulsa desde el mismo dominio, pero no es un enlace publico completo y al copiarlo fuera del navegador/app no contiene host ni esquema.

## Verificaciones HTTP

Detalle DISPATCH local:

```text
GET http://127.0.0.1:5001/dispatch/ship-20260815040520-3170 -> 200
```

Landing publica local:

```text
GET http://127.0.0.1:5001/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk -> 200
```

Landing publica externa:

```text
GET https://atlas.lavoceria.com/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk -> 200
```

ZIP:

```text
HEAD http://127.0.0.1:5001/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk/download -> 200
HEAD https://atlas.lavoceria.com/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk/download -> 200
Content-Disposition: attachment; filename=QUITO-DRONE.zip
Content-Type: application/zip
Content-Length: 144510874
```

Archivo individual:

```text
GET https://atlas.lavoceria.com/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk/file/captions-docx -> 200
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
```

Preview:

```text
HEAD https://atlas.lavoceria.com/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk/preview/thumbnail:94848d95-3f14-45c4-972f-7f4d6daaa06f -> 200
Content-Type: image/jpeg
```

Legacy:

```text
HEAD https://atlas.lavoceria.com/lens/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk -> 307
Location: https://atlas.lavoceria.com/d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk
```

## Archivo Fisico

Directorio de entrega:

```text
instance/deliveries/ship-20260815040520-3170
```

Archivos principales:

```text
instance/deliveries/ship-20260815040520-3170/manifest.json
instance/deliveries/ship-20260815040520-3170/package.zip
```

Estado:

```text
drwxrwxr-x 775 atlas atlas 4096 instance/deliveries
drwxr-xr-x 755 atlas atlas 4096 instance/deliveries/ship-20260815040520-3170
-rw-r--r-- 644 atlas atlas 144510874 instance/deliveries/ship-20260815040520-3170/package.zip
-rw-r--r-- 644 atlas atlas 2234 instance/deliveries/ship-20260815040520-3170/manifest.json
```

El archivo fisico existe y Flask puede servirlo.

Filesystem:

```text
/opt/atlas-lens -> ext4 rw
```

## Logs

Los logs recientes de `atlas-lens.service` confirman que Flask recibio y sirvio las rutas probadas:

```text
GET /d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk HTTP/1.1" 200
HEAD /d/uHQwSh8Se7X2uEezja6DaxW1H7iuPbMD_fLFQiNrVlk/download HTTP/1.1" 200
GET /dispatch/ship-20260815040520-3170 HTTP/1.1" 200
```

No se observo traceback ni error de permisos asociado a las descargas inspeccionadas.

## Ruteo

La URL canonica de DISPATCH es:

```text
/dispatch/
```

La URL canonica de entregas publicas es:

```text
/d/<token>
```

Apache actualmente enruta correctamente `/dispatch/...`, `/d/...` y mantiene compatibilidad legacy `/lens/d/... -> /d/...`.

No se encontro inconsistencia activa entre Flask, Apache y ruta fisica para el token inspeccionado. El problema esta en el formato del enlace presentado al usuario: relativo en lugar de absoluto.

## Clasificacion Del Boton/Link

Resultado:

```text
A. href esta vacio: NO
B. href contiene "#": NO
C. JavaScript no ejecuta: NO aplica; el boton es anchor HTML
D. URL mal construida: SI, es relativa para un enlace publico copiable
E. endpoint no existe: NO
F. endpoint devuelve 404: NO
G. endpoint devuelve 403: NO
H. archivo no existe: NO
I. Apache no enruta la URL: NO
J. otra causa: PUBLIC_BASE_URL no configurado/normalizado para enlaces publicos
```

## Correccion Minima Recomendada

Opcion operacional minima:

1. Definir en runtime:

```text
PUBLIC_BASE_URL=https://atlas.lavoceria.com
```

2. Reiniciar `atlas-lens.service` en una ventana controlada.
3. Verificar que el detalle de DISPATCH muestre:

```text
https://atlas.lavoceria.com/d/<token>
```

Opcion de codigo recomendable para robustez:

1. Mantener `PUBLIC_BASE_URL` como fuente canonica.
2. Agregar test que garantice que, con `PUBLIC_BASE_URL=https://atlas.lavoceria.com`, DISPATCH renderiza URL absoluta.
3. Opcionalmente hacer que la vista use `url_for("downloads.landing", token=..., _external=True)` como fallback cuando no exista `PUBLIC_BASE_URL`, tomando en cuenta reverse proxy headers.

## Riesgos De La Correccion

- Cambiar `PUBLIC_BASE_URL` requiere restart del servicio Flask para entrar en efecto.
- Si se configura con path obsoleto, por ejemplo `https://atlas.lavoceria.com/lens`, volveria a generar enlaces legacy.
- Si se usa `_external=True` sin `ProxyFix`/headers correctos, Flask podria generar host/esquema incorrectos en entornos con reverse proxy.
- Los links ya creados no necesitan migracion de token; `with_url()` enriquece la URL al renderizar/listar. Al definir `PUBLIC_BASE_URL`, los mismos tokens se mostraran con URL absoluta.

## Comandos Ejecutados

```bash
find app -maxdepth 4 -type f | sort | grep -Ei 'dispatch|delivery|deliver|download|web\.py|template|js'
grep -RIn "dispatch\|delivery\|deliver\|download\|send_file\|send_from_directory\|/d/" app tests docs --exclude-dir=.git
sed -n '1,220p' app/routes/downloads.py
sed -n '130,180p;520,580p;830,870p;1210,1255p' app/routes/dispatch.py
sed -n '1,260p' app/dispatch/delivery_links.py
sed -n '1,260p' app/dispatch/delivery_package.py
sed -n '1,260p' app/templates/dispatch/detail.html
sed -n '1,260p' app/templates/downloads/landing.html
sed -n '1,95p' app/config.py
python summary scripts for instance/dispatch_shipments.json and instance/delivery_links.json
curl checks against local and public /dispatch and /d routes
systemctl cat atlas-lens.service
journalctl -u atlas-lens.service -n 80 --no-pager
findmnt -T /opt/atlas-lens/instance/deliveries
stat -c '%A %a %U %G %s %n' ...
```

## Confirmacion

Cambios realizados: ninguno.

