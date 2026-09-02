# FLOW delete real failure diagnosis

Fecha: 2026-08-17

## Alcance

Diagnostico de la primera prueba real de eliminacion de sesiones FLOW despues del deploy.

No se modifico codigo, no se borraron ni movieron fotografias, no se cambiaron permisos, no se modifico Proxmox/VirtioFS/mounts/discos, no se modifico manualmente `instance/ingest.json`, no se hizo commit, push, pull, reset, checkout, deploy ni restart.

## 1. Causa exacta

La causa exacta es `FILE_MOVE_FAILED` por permisos insuficientes del usuario `atlas` sobre los directorios fuente que contienen los JPG.

Los archivos JPG son `atlas:atlas 644`, por lo que el servicio puede leerlos. Pero los directorios `JPG` que contienen esos archivos son `root:root 755`, por lo que `atlas` no puede escribir en esos directorios.

Para mover un archivo con `Path.replace()`/rename no basta con ser owner del archivo: hace falta permiso de escritura y ejecucion sobre el directorio padre del archivo fuente, porque el move elimina una entrada de ese directorio.

La implementacion detecta esto antes del move:

```python
if not os.access(source_parent, os.W_OK):
    raise FlowSessionFilesystemError(flow_filesystem_error_payload(session_id, len(photos), "source_unmovable"))
```

Por tanto el error interno exacto es:

```text
reason=filesystem_error
error_code=source_unmovable
```

No es `BLOCKED_BY_LENS`: el store LENS esta vacio.

## 2. Endpoint implicado

Endpoint de check:

```python
@web_bp.get("/flow/sessions/<session_id>/delete-check")
def flow_session_delete_check(session_id: str)
```

Endpoint de eliminacion:

```python
@web_bp.post("/flow/sessions/<session_id>/delete")
def flow_delete_session(session_id: str)
```

Rutas observadas en logs:

```text
GET /flow/sessions/session-d97e544b32914e958a4f49f50139a359/delete-check HTTP/1.1" 200
POST /flow/sessions/session-d97e544b32914e958a4f49f50139a359/delete HTTP/1.1" 409
GET /flow/sessions/session-1ed2e3298085416d976a8cb2c3d0ecc8/delete-check HTTP/1.1" 200
POST /flow/sessions/session-1ed2e3298085416d976a8cb2c3d0ecc8/delete HTTP/1.1" 409
```

## 3. Funcion que intenta retirar/mover originales

Flujo de funciones:

1. `flow_delete_session(session_id)`
2. `delete_flow_session(session_id)`
3. `build_flow_session_delete_check(session_id, payload=payload)`
4. `build_flow_trash_plan(session_id, photos)`
5. `move_flow_photos_to_trash(plan)`

El fallo ocurre en `build_flow_trash_plan()`, antes de entrar al rename real, porque `os.access(source_parent, os.W_OK)` devuelve falso.

Si ese preflight no existiera, el `Path.replace()` de `move_flow_photos_to_trash()` probablemente fallaria con `PermissionError: [Errno 13] Permission denied` al intentar retirar la entrada desde el directorio fuente.

## 4. Source real

`instance/ingest.json` contiene 2 sesiones cerradas y 193 fotos:

```text
sessions=2 photos=193
```

Sesion de 171 fotos:

```text
id=session-d97e544b32914e958a4f49f50139a359
status=closed
photo_count=171
stored_photos=171
sources=['canon-r6']
coverage_id=
```

Directorios source reales:

```text
/data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG
/data/FLOW/sftpgo/storage/events/2026/08/12/sabado/ricardo/canon-r6/JPG
/data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG
/data/FLOW/sftpgo/storage/events/2026/08/15/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
```

Archivo representativo:

```text
/data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG/_21A0627.JPG
```

Sesion de 22 fotos:

```text
id=session-1ed2e3298085416d976a8cb2c3d0ecc8
status=closed
photo_count=22
stored_photos=22
sources=['canon-r6']
coverage_id=
```

Directorio source real:

```text
/data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
```

Archivo representativo:

```text
/data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG/_21A5478.JPG
```

## 5. Destination/trash real

Configuracion esperada desplegada:

```text
FLOW_EVENTS_ROOT=/data/FLOW/sftpgo/storage/events
FLOW_TRASH_ROOT=/data/FLOW/trash
FLOW_WATCH_DIRECTORIES=/data/FLOW/sftpgo/storage/events
```

La funcion `build_flow_trash_batch_root()` genera destinos con este patron:

```text
/data/FLOW/trash/<session_id>-<YYYYMMDDTHHMMSSffffffZ>/<relative_source_under_events>
```

Ejemplo para la sesion de 22 fotos:

```text
/data/FLOW/trash/session-1ed2e3298085416d976a8cb2c3d0ecc8-<timestamp>/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG/_21A5478.JPG
```

Ejemplo para la sesion de 171 fotos:

```text
/data/FLOW/trash/session-d97e544b32914e958a4f49f50139a359-<timestamp>/2026/08/08/sabado/ricardo/canon-r6/JPG/_21A0627.JPG
```

Como el fallo ocurre en preflight `source_unmovable`, no se crea batch directory. `trash` sigue vacio.

## 6. Existencia de source y destination

Sources:

- Los directorios source existen.
- Los JPG representativos existen.

Trash:

```text
drwxr-x--- atlas atlas /data/FLOW/trash
```

Contenido inmediato de trash:

```text
/data/FLOW/trash
```

No hay lotes creados debajo de trash por estos intentos fallidos.

## 7. Permisos encontrados

Comando:

```bash
stat -c '%A %a %U %G %n' /data/FLOW /data/FLOW/trash /data/FLOW/sftpgo/storage/events \
  /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG \
  /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG \
  /data/FLOW/sftpgo/storage/events/2026/08/12/sabado/ricardo/canon-r6/JPG \
  /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG \
  /data/FLOW/sftpgo/storage/events/2026/08/15/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
```

Resultado:

```text
drwxrwxr-x 775 root root /data/FLOW
drwxr-x--- 750 atlas atlas /data/FLOW/trash
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/12/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/15/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
```

Comando:

```bash
stat -c '%A %a %U %G %n' \
  /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG/_21A5478.JPG \
  /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG/_21A0627.JPG
```

Resultado:

```text
-rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG/_21A5478.JPG
-rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG/_21A0627.JPG
```

## 8. Usuario del servicio

Comando:

```bash
systemctl show atlas-lens.service -p User -p Group -p MainPID -p WorkingDirectory
id atlas
```

Resultado:

```text
MainPID=3723395
WorkingDirectory=/opt/atlas-lens
User=atlas
Group=
```

```text
uid=1000(atlas) gid=1000(atlas) groups=1000(atlas),24(cdrom),25(floppy),29(audio),30(dip),44(video),46(plugdev),100(users),101(netdev)
```

`Group=` no esta declarado; systemd usa el grupo primario `atlas`.

## 9. Permisos efectivos del usuario atlas

Checks de acceso, sin modificar archivos:

```bash
test -r /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG/_21A5478.JPG
test -w /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
test -w /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG
test -w /data/FLOW/trash
```

Resultados:

```text
READ_SAMPLE_22=0
WRITE_SOURCE_DIR_22=1
WRITE_SOURCE_DIR_171=1
WRITE_TRASH=0
```

En `test`, `0` significa true/exito y `1` significa false/fallo.

Conclusion:

- `atlas` puede leer los JPG fuente.
- `atlas` puede escribir en `/data/FLOW/trash`.
- `atlas` no puede escribir en los directorios `JPG` fuente.
- Por tanto `atlas` no puede renombrar/mover los JPG fuera de esos directorios.

## 10. Filesystem/mount

Comandos:

```bash
findmnt -T /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
findmnt -T /data/FLOW/trash
stat -c '%d %m %n' /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG /data/FLOW/trash
```

Resultados:

```text
TARGET SOURCE     FSTYPE   OPTIONS
/data  atlas-data virtiofs rw,relatime
```

```text
40 /data /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
40 /data /data/FLOW/trash
```

Conclusion:

- Source y trash estan en el mismo filesystem/mount.
- Ambos atraviesan `virtiofs`.
- El mount real esta `rw`.
- No es un fallo `EXDEV`.

## 11. Exception/error exacto del intento real

Journal muestra HTTP 409 para los intentos reales:

```text
POST /flow/sessions/session-d97e544b32914e958a4f49f50139a359/delete HTTP/1.1" 409
POST /flow/sessions/session-1ed2e3298085416d976a8cb2c3d0ecc8/delete HTTP/1.1" 409
```

No hay traceback ni `PermissionError` en journal porque la implementacion convierte el problema a una respuesta controlada `FlowSessionFilesystemError`.

El error interno exacto inferido por el codigo y los permisos es:

```text
filesystem_error / source_unmovable
```

No llega a ejecutarse `Path.replace()`; el fallo ocurre antes, en el preflight `os.access(source_parent, os.W_OK)`.

## 12. Estado de dependencias LENS

`instance/lens_coverages.json`:

```json
{
  "coverages": {}
}
```

`instance/ingest.json`:

```text
session-d97e544b32914e958a4f49f50139a359 coverage_id=
session-1ed2e3298085416d976a8cb2c3d0ecc8 coverage_id=
```

Conclusion:

- No hay coberturas LENS persistidas.
- Las sesiones no tienen `coverage_id`.
- El fallo no es `BLOCKED_BY_LENS`.
- El estado correcto es `FILE_MOVE_FAILED`.

## 13. Por que aparece "Coberturas relacionadas"

El backend separa los errores:

- `photos_in_use` para dependencias LENS.
- `filesystem_error` para problemas de filesystem.

Pero el frontend reutiliza el mismo panel visual `blockedPanel` para cualquier error no exitoso.

En `app/static/js/flow_session_delete.js`:

```javascript
if (payload.reason && payload.reason !== "photos_in_use") {
    title.textContent = payload.reason === "session_active" ? "Esta sesión no puede eliminarse" : "No se pudo eliminar la sesión";
    setMode("blocked");
    blockedSummary.textContent = payload.message || "La sesión no puede eliminarse en este momento.";
    renderCoverages([]);
    return;
}
```

`renderCoverages([])` deja la lista vacia, pero `app/templates/flow/index.html` contiene el titulo y texto de coberturas dentro del panel bloqueado de forma fija:

```html
<h3>Coberturas relacionadas</h3>
<div class="flow-session-delete-coverages" data-flow-delete-coverages></div>
<p>Para eliminar esta sesión primero debe retirar esas fotografías de las coberturas relacionadas.</p>
```

Por eso aparece "Coberturas relacionadas" aunque no haya coberturas.

## 14. Correccion minima recomendada

Hay dos correcciones separadas:

### A. Desbloquear el move real

Dar a `atlas` permiso de escritura/ejecucion sobre los directorios fuente que contienen los JPG existentes y asegurar que los futuros directorios creados por FLOW/SFTPGo/organizador sean escribibles por `atlas`.

La opcion preferida es ACL especifica sobre el arbol FLOW events, si ACL esta disponible:

```bash
# No ejecutar sin aprobacion explicita.
setfacl -R -m u:atlas:rwx /data/FLOW/sftpgo/storage/events
setfacl -R -d -m u:atlas:rwx /data/FLOW/sftpgo/storage/events
```

Si ACL no esta disponible, usar una estrategia de grupo compartido limitada al arbol FLOW events, no `chmod 777` y no cambios amplios sobre todo `/data`.

La correccion de codigo no puede evitar este permiso: copiar a trash y luego borrar tambien requeriria permiso de escritura en el directorio fuente para retirar el original.

### B. Corregir UX del modal

Separar visualmente `photos_in_use` de `filesystem_error`:

- Mostrar "Coberturas relacionadas" solo cuando `payload.reason === "photos_in_use"` y existan coverages.
- Para `filesystem_error`, mostrar un mensaje operativo sin seccion de coberturas.
- Opcionalmente mostrar `payload.error_code` de forma controlada para diagnostico interno.

## 15. Archivos que habria que modificar

Para corregir el modal:

- `app/static/js/flow_session_delete.js`
- `app/templates/flow/index.html`
- `tests/test_flow_session_delete.py`

Para mejorar diagnostico backend opcionalmente:

- `app/routes/web.py`

Para desbloquear el move fisico:

- No requiere archivo de repo.
- Requiere cambio controlado de permisos/ACL en `/data/FLOW/sftpgo/storage/events` y politica para futuros directorios.

## 16. Riesgos de la correccion

- Un cambio amplio de permisos sobre `/data` podria exponer datos innecesariamente.
- `chmod 777` o `chown -R` indiscriminado podria romper ownership esperado por SFTPGo/organizador o degradar seguridad.
- Si solo se corrigen directorios actuales y no permisos por defecto/futuros, el bug volvera con nuevas sesiones.
- Si se cambia solo el frontend, el error real de move seguira ocurriendo.
- Si se fuerza el delete logico sin retirar originales, volveria el bug original: el watcher reingestaria las fotos.

## 17. Comandos utilizados

Comandos principales, todos de lectura/diagnostico:

```bash
nl -ba app/routes/web.py | sed -n '760,1010p'
nl -ba app/static/js/flow_session_delete.js | sed -n '75,150p'
git status --short
.venv/bin/python - <<'PY' ... leer instance/ingest.json e instance/lens_coverages.json ...
stat -c '%A %a %U %G %n' ...
findmnt -T ...
test -r ...
test -w ...
journalctl -u atlas-lens.service --since '2026-08-17 20:50:00' --no-pager
systemctl show atlas-lens.service -p User -p Group -p MainPID -p WorkingDirectory
id atlas
find /data/FLOW/trash -maxdepth 3 -printf '%M %u %g %p\n'
```

## 18. Confirmacion de no cambios

Durante este diagnostico:

- No se modifico codigo.
- No se movieron ni borraron fotografias.
- No se cambiaron permisos.
- No se modifico Proxmox, VirtioFS, mounts ni discos.
- No se modifico manualmente `instance/ingest.json`.
- No se hizo commit, push, pull, reset, checkout, deploy ni restart.
