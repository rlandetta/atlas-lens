# ATLAS FLOW - Eliminacion segura mediante papelera

Fecha: 2026-08-17

## 1. Causa previa resumida

El borrado anterior eliminaba `sessions` y `photos` del `IngestStore`, pero despues intentaba borrar originales con `unlink`. En produccion, esos `unlink` fallaban por `Permission denied`, los JPG quedaban dentro de `/data/FLOW/sftpgo/storage/events`, y `atlas-flow.service` / `IngestWatcher` los reingresaba como fotos nuevas. Por eso reaparecia una sesion nueva con nuevo ID.

## 2. Arquitectura elegida de trash

La eliminacion ahora usa una papelera de FLOW fuera del arbol observado por el watcher.

Secuencia implementada:

1. Validar dependencias LENS.
2. Cerrar sesiones activas expiradas usando la logica existente de timeout.
3. Bloquear sesiones que sigan `active`.
4. Resolver todos los originales de la sesion.
5. Preflight completo de paths, symlinks, root FLOW, colisiones y permisos.
6. Mover todos los originales a una carpeta batch unica de trash.
7. Escribir `manifest.json` en trash.
8. Solo si todos los movimientos terminan OK, borrar `sessions/photos` del store.
9. Limpiar thumbnails FLOW asociados.

No se implemento vaciado definitivo, restauracion ni retencion automatica de trash.

## 3. Ruta de trash propuesta/real

Nueva configuracion:

- `FLOW_TRASH_ROOT`
- default: `/data/FLOW/trash`

Cada eliminacion crea una carpeta unica:

```text
/data/FLOW/trash/<session_id>-<timestamp>Z/
```

Dentro se preserva la ruta relativa original bajo `FLOW_EVENTS_ROOT`, para evitar colisiones cuando varias fotos tienen el mismo basename en carpetas distintas.

Cada lote incluye:

- `manifest.json`
- `session_id`
- `deleted_at`
- `filename`
- `relative_path`

Las respuestas JSON no exponen rutas internas.

## 4. Relacion con FLOW_WATCH_DIRECTORIES

`FLOW_WATCH_DIRECTORIES` actual:

```text
/data/FLOW/sftpgo/storage/events
```

`FLOW_TRASH_ROOT`:

```text
/data/FLOW/trash
```

La papelera queda fuera del arbol observado. El codigo valida esto antes de mover; si trash cae dentro de algun watch root, aborta con error seguro y no modifica el store.

## 5. Permisos actuales detectados

Servicios:

- `atlas-lens.service`: `User=atlas`
- `atlas-flow.service`: `User=atlas`

Usuarios/grupos observados:

- UID `1000`: `atlas`
- GID `1000`: `atlas`
- UID `65534`: `nobody`
- GID `65534`: `nogroup`

Permisos actuales:

```text
0775 nobody:nogroup /data/FLOW
0775 nobody:nogroup /data/FLOW/sftpgo/storage/events
/data/FLOW/trash no existe
```

Los logs previos mostraron `Permission denied` al intentar retirar originales desde subdirectorios de `events`. Aunque varios JPG pertenecen a `atlas`, borrar/mover requiere permiso de escritura en el directorio contenedor.

## 6. Cambio operativo de permisos necesario

No se aplico ningun cambio de permisos en esta tarea.

Antes de activar en produccion, hace falta garantizar dos cosas:

1. `atlas` puede crear/escribir en `/data/FLOW/trash`.
2. `atlas` puede mover fuera de `FLOW_EVENTS_ROOT` los archivos que administra FLOW.

Opcion recomendada con ACL, sin `chmod 777` ni `chown` recursivo indiscriminado:

```bash
mkdir -p /data/FLOW/trash
chown atlas:atlas /data/FLOW/trash
chmod 750 /data/FLOW/trash
setfacl -R -m u:atlas:rwx /data/FLOW/sftpgo/storage/events
find /data/FLOW/sftpgo/storage/events -type d -exec setfacl -m d:u:atlas:rwx {} +
```

Si ACL no esta disponible, alternativa operativa a evaluar:

```bash
mkdir -p /data/FLOW/trash
chown atlas:atlas /data/FLOW/trash
chmod 750 /data/FLOW/trash
```

y ajustar grupo/permisos solo sobre los directorios FLOW necesarios para que `atlas` tenga escritura en directorios, no permisos globales amplios.

## 7. Archivos de codigo modificados

- `app/config.py`
- `app/__init__.py`
- `app/routes/web.py`
- `app/templates/flow/index.html`
- `app/static/css/main.css`
- `app/static/js/flow_session_delete.js`
- `tests/test_flow_session_delete.py`

Documentacion agregada:

- `docs/atlas_flow_session_trash_report.md`

## 8. Algoritmo transaccional

El borrado de sesion se ejecuta dentro de la mutacion bloqueada de `IngestStore`.

El callback:

1. Carga el payload bajo lock exclusivo.
2. Revalida dependencias LENS.
3. Revalida estado activo.
4. Construye plan `source -> destination`.
5. Ejecuta preflight.
6. Mueve originales a trash.
7. Si el move completo termina OK, remueve sesion y fotos del payload.
8. `IngestStore` guarda el payload.

Si cualquier paso falla antes de guardar, `IngestStore.mutate()` no persiste cambios.

## 9. Rollback interno

Si un movimiento falla a mitad:

- se recorren en orden inverso los archivos ya movidos;
- se intentan devolver a su ubicacion original;
- se lanza error filesystem;
- no se guarda el borrado del store.

Si un rollback puntual fallara, se registra `LOGGER.error` con el filename, pero el store permanece intacto para no perder trazabilidad logica.

## 10. Tratamiento de sesion activa

Si la sesion esta `active`, primero se reutiliza la logica existente de timeout para cerrar sesiones expiradas.

Si despues de eso sigue `active`, se bloquea la eliminacion con `409`:

```text
Esta sesion esta recibiendo fotografias. Cierrela o espere a que deje de recibir antes de eliminarla.
```

No se permite borrar una sesion que sigue recibiendo.

## 11. Comportamiento UI

La UI mantiene el modal abierto si el backend devuelve error filesystem o sesion activa.

En error:

- no recarga la pagina;
- no quita visualmente la sesion;
- muestra el mensaje seguro del backend;
- no expone rutas internas.

En exito:

- el backend devuelve `ok: true`;
- la UI recarga para actualizar Dashboard/FLOW desde el store.

## 12. Pruebas ejecutadas

- `git diff --check`: OK
- `.venv/bin/python -m unittest tests.test_flow_session_delete`: `Ran 26 tests`, OK
- `.venv/bin/python -m unittest tests.test_ingest_watcher`: `Ran 11 tests`, OK
- `.venv/bin/python -m unittest tests.test_atlas_routing_phase1`: `Ran 8 tests`, OK
- `.venv/bin/python -m unittest discover -s tests`: `Ran 330 tests`, OK

La suite completa emitio warnings conocidos de fixtures de imagen invalida y `ResourceWarning`, pero finalizo correctamente.

## 13. Resultados cubiertos

- Sesion libre mueve todos los originales a trash y borra registros.
- Los archivos ya no quedan dentro de `events`.
- El watcher no los reingresa.
- Dashboard y FLOW quedan sin sesion activa despues del borrado.
- Dependencias LENS devuelven `409` y no mueven nada.
- Fallo de preflight filesystem deja store y archivos intactos.
- Fallo de move intermedio ejecuta rollback y deja store intacto.
- Path fuera de `FLOW_EVENTS_ROOT` aborta.
- Symlink aborta.
- Colision en trash aborta.
- Basenames iguales en carpetas distintas se conservan sin colision.
- Sesion inexistente devuelve `404`.
- Sesion activa recibiendo devuelve `409`.
- Sesion activa expirada se cierra y puede eliminarse.
- Nueva foto real despues del borrado crea una sesion nueva desde cero.
- Trash no es observado por watcher.
- Respuestas JSON no contienen paths internos.
- Otras sesiones, LENS y dispatch no se modifican.
- Reproduccion del bug original con multiples archivos ya no reaparece tras scans del watcher.

## 14. Riesgos restantes

- En produccion, si no se ajustan permisos para que `atlas` pueda mover originales fuera de `events`, el endpoint devolvera `409 filesystem_error` y no borrara registros. Eso es deliberado y evita la reaparicion.
- Si falla el rollback fisico despues de un move parcial, el store queda intacto pero puede requerir intervencion manual para reconciliar archivos movidos.
- La papelera crecera hasta que exista una funcion posterior de vaciado/restauracion/retencion.

## 15. git status --short

Estado observado antes de crear este informe:

```text
 M app/__init__.py
 M app/config.py
 M app/routes/web.py
 M app/static/css/main.css
 M app/templates/flow/index.html
?? app/static/js/flow_session_delete.js
?? atlas-convert-prototype.zip
?? atlas_convert_hif_fix_report.md
?? atlas_convert_install_report.md
?? docs/atlas_flow_session_delete_report.md
?? docs/atlas_flow_session_reappears_analysis.md
?? docs/atlas_routing_closeout.md
?? tests/test_flow_session_delete.py
```

Este informe agrega:

```text
?? docs/atlas_flow_session_trash_report.md
```

## 16. Confirmaciones

- No se modifico Apache.
- No se modifico systemd.
- No se modifico routing publico.
- No se modifico DNS.
- No se modifico Docker.
- No se modifico Proxmox.
- No se hizo deploy.
- No se hizo restart.
- No se hizo commit.
- No se hizo push.
