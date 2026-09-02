# ATLAS FLOW - Analisis de sesion que reaparece tras eliminar

Fecha: 2026-08-17

## Resumen

La sesion reaparece porque el borrado de FLOW elimina los registros del `IngestStore`, pero los JPG originales no se eliminan fisicamente por permisos. Como los archivos siguen en el directorio observado por `atlas-flow.service`, el `IngestWatcher` los vuelve a detectar como no registrados y crea una sesion nueva con nuevo ID.

No hay evidencia de un estado `active_session_id` huerfano ni de otro metadata interno apuntando a la sesion eliminada.

## Estado persistido de FLOW

Store real inspeccionado:

- `INGEST_STORE_PATH`: `instance/ingest.json`
- Archivo real bajo el servicio: `/opt/atlas-lens/instance/ingest.json`
- Keys presentes: `photos`, `sessions`

Campos buscados y no encontrados en el JSON:

- `active_session_id`
- `current_session`
- `ingest_session`
- `session_open`
- `receiving_state`
- `camera_state`
- `source_state`
- `last_session`

Estado observado despues de la reaparicion:

- `sessions`: 1
- `photos`: 171
- sesion: `session-d97e544b32914e958a4f49f50139a359`
- estado: `active`
- `photo_count`: 171
- source: `canon-r6`

Los registros apuntan a originales dentro de:

- `/data/FLOW/sftpgo/storage/events/...`

Y los archivos existen fisicamente.

## Fuentes del Dashboard y de FLOW

Dashboard `/`:

- Handler: `home()` en `app/routes/web.py`
- Usa: `build_flow_summary()`
- Template: `app/templates/index.html`

FLOW `/flow/`:

- Handler: `flow_home()` en `app/routes/web.py`
- Usa: `build_flow_summary()`
- Template: `app/templates/flow/index.html`

Ambos leen la misma fuente:

- `current_app.extensions["ingest"]["store"]`
- `IngestStore`
- `instance/ingest.json`

No usan stores distintos para `RECIBIENDO`, fotografias, sesion activa, camara ni ultima foto. No hay estado en memoria separado para esos valores. El estado se deriva de:

- sesiones con `status == "active"`;
- fotos cuyo `session_id` coincide con la sesion activa;
- `sources` de la sesion activa;
- `last_received_at`.

`build_flow_summary()` tambien llama a `service.get_active_session()`, que puede cerrar sesiones inactivas por timeout, pero no crea sesiones nuevas.

## Auto-creacion de sesiones

El componente que crea o reabre sesiones es:

- `atlas-flow.service`
- proceso: `/opt/atlas-lens/.venv/bin/python -c "from app.ingest.watcher import run_ingest_watcher; run_ingest_watcher()"`
- codigo: `app/ingest/watcher.py`

Tambien existe un proceso organizador:

- `/bin/bash -c while true; do /data/FLOW/scripts/atlas-flow-organize.sh; sleep 2; done`

El watcher observa:

- `FLOW_WATCH_DIRECTORIES`: `/data/FLOW/sftpgo/storage/events`

Logica relevante:

1. `IngestWatcher.scan_once()` calcula `known_paths` desde `store.list_photos()`.
2. Recorre los JPG/JPEG del directorio observado.
3. Si un path no esta en `known_paths` ni en `baseline_paths`, lo considera candidato.
4. Tras dos scans con tamano estable, llama a `IngestService.register_received_photo()`.
5. `register_received_photo()` crea una nueva sesion si no existe sesion activa.

Esto es correcto cuando llega una foto nueva. El problema aparece cuando se borran registros pero los archivos permanecen fisicamente.

## Evidencia de permisos

Los logs inmediatos de `atlas-lens.service` muestran errores de borrado fisico:

```text
No se pudo eliminar original FLOW ... Permission denied
```

Ejemplos:

- `_21A0877.JPG`
- `_21A0899.JPG`
- `_21A0913.JPG`
- `_21A0627.JPG`
- `_21A5413.JPG`

Los archivos muestreados existen y tienen permisos `0644`, UID/GID `1000/1000`, bajo `/data/FLOW/sftpgo/storage/events/...`.

El proceso Flask corre como usuario `atlas`. Aunque el archivo sea `0644`, borrar requiere permiso de escritura sobre el directorio contenedor. Los logs confirman que el usuario del servicio no pudo hacer `unlink`.

## Reproduccion controlada

Se reprodujo con un store temporal, sin tocar datos reales:

1. Crear directorio temporal de eventos.
2. Crear un JPG.
3. Registrar una sesion y una foto en `IngestStore` temporal.
4. Inicializar `IngestWatcher` con esa foto ya conocida.
5. Borrar solo `sessions` y `photos`, dejando el archivo fisico.
6. Ejecutar scans del watcher.

Resultado:

```text
initial 1 1 session-915a86b8565546d0b6ca93f4540bf714
baseline_scan []
after_delete_records 0 0 file_exists True
scan_after_delete_1 []
after_scan_1 0 0
scan_after_delete_2_count 1
after_scan_2 1 1 session-5c1bbd386af3446c8e32560dc2937b88
```

La sesion reaparece con nuevo ID cuando el archivo fisico sigue en el directorio observado.

## Causa exacta

La causa exacta es doble:

1. El endpoint de eliminacion actual remueve los registros de `sessions` y `photos`.
2. El borrado fisico de originales falla por permisos (`Permission denied`), por lo que los JPG quedan en `/data/FLOW/sftpgo/storage/events`.
3. `atlas-flow.service` / `IngestWatcher` observa esos JPG restantes, ya no los encuentra en `known_paths`, espera estabilidad y los registra como fotos nuevas.
4. `IngestService.register_received_photo()` crea una nueva sesion activa y asigna ahi las 171 fotos.

No es el Dashboard reconstruyendo la sesion. El Dashboard solo muestra lo que el watcher ya volvio a persistir en el mismo `IngestStore`.

## Estado huerfano

No queda un puntero huerfano como `active_session_id`.

Lo que queda huerfano respecto al borrado logico son los archivos fisicos originales no eliminados. Al quedar vivos en el directorio observado y ya no estar registrados en `photos`, se convierten en candidatos nuevos para el watcher.

## Comportamiento esperado

Si se eliminan todas las sesiones y no entran fotos nuevas:

- Dashboard debe mostrar `RECIBIENDO: 0`.
- Fotografias FLOW debe ser `0`.
- Debe indicar `Sin sesion activa`.
- FLOW debe mostrar `Sesiones recientes: 0`.

Si la camara vuelve a mandar una foto despues del borrado:

- Es correcto crear una sesion nueva.
- Debe tener nuevo ID.
- Debe empezar con el conteo de fotos nuevas realmente recibidas despues del borrado.

El caso actual no cumple porque no son fotos nuevas: son archivos antiguos que quedaron fisicamente en el watch root.

## Solucion minima recomendada

La solucion minima de codigo recomendada para la siguiente fase:

1. Cambiar la eliminacion para que sea transaccional a nivel de comportamiento:
   - validar dependencias LENS;
   - resolver todos los paths fisicos;
   - verificar antes de modificar el store que todos los originales que deben borrarse son eliminables o movibles;
   - si algun original no puede eliminarse, devolver error seguro y no borrar `sessions/photos`.
2. Alternativa mas segura si no se quiere hacer `unlink` directo:
   - mover originales a una cuarentena/trash dentro de FLOW con permisos controlados;
   - solo despues remover registros del store;
   - excluir esa cuarentena del watcher.
3. Evitar que el watcher reingrese archivos de sesiones eliminadas:
   - registrar tombstones/ignore list para paths eliminados;
   - o pausar/coordinar watcher durante la operacion;
   - o actualizar `baseline_paths`/estado persistido equivalente.
4. Resolver permisos operativos:
   - asegurar que el usuario `atlas` pueda borrar/mover dentro de los directorios FLOW esperados;
   - o delegar el borrado/move a un componente con permisos adecuados y controlados.

La opcion mas pequena y segura es: preflight de permisos + abortar con error si no se pueden borrar/mover todos los originales, para impedir que el store quede limpio mientras los archivos siguen reingresables.

## Confirmacion de no cambios

Durante este analisis no se modifico codigo, Apache, systemd, DNS, Docker, Proxmox, routing publico ni servicios.

Solo se leyeron archivos, logs, procesos, configuracion y se ejecuto una reproduccion en directorio temporal.
