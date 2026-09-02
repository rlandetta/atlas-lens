# ATLAS FLOW session persistence audit

Fecha: 2026-08-17

## Alcance

Auditoria exclusiva del codigo de persistencia de FLOW para explicar por que una sesion eliminada puede reaparecer en Dashboard y FLOW.

No se modificaron datos reales, servicios, Proxmox, runtime ni configuracion externa. No se hizo commit ni push.

## Resumen ejecutivo

FLOW no guarda una `active_session_id`, `current_session`, `last_session`, cache especial ni SQLite. El estado persistido vive en `instance/ingest.json` mediante dos listas:

- `sessions`
- `photos`

El archivo de lock asociado es `instance/ingest.json.lock`.

La sesion activa se deriva de `sessions[*].status == "active"` y de `last_received_at`. Dashboard y `/flow/` usan la misma funcion: `build_flow_summary()`.

La causa funcional del bug es que el watcher reconstruye sesiones desde los JPG fisicos que quedan dentro de `FLOW_WATCH_DIRECTORIES`. Si el endpoint de eliminacion borra la sesion/fotos de `ingest.json` pero deja los originales en `/data/FLOW/sftpgo/storage/events`, el siguiente escaneo del watcher ve esos JPG como archivos nuevos no registrados y llama a `register_received_photo()`. Eso crea una sesion nueva y el Dashboard vuelve a mostrar `RECIBIENDO: 1`.

## Archivos de estado y configuracion

Codigo relevante:

- `app/config.py`
- `app/__init__.py`
- `app/ingest/store.py`
- `app/ingest/service.py`
- `app/ingest/watcher.py`
- `app/routes/web.py`
- `app/templates/index.html`
- `app/templates/flow/index.html`
- `app/static/js/flow_session_delete.js`

Estado FLOW:

- `INGEST_STORE_PATH`: por defecto `instance/ingest.json`.
- Lock: `instance/ingest.json.lock`, generado por `IngestStore`.
- Watch roots: `FLOW_WATCH_DIRECTORIES`, por defecto `["/data/FLOW/sftpgo/storage/events"]`.
- Events root: `FLOW_EVENTS_ROOT`, por defecto `/data/FLOW/sftpgo/storage/events`.
- Trash root en el working tree actual: `FLOW_TRASH_ROOT`, por defecto `/data/FLOW/trash`.

No se encontro SQLite ni base de datos local para FLOW. Tampoco se encontro un archivo paralelo `current`, `cache`, `active_session_id`, `current_session`, `last_session` o `session_open` para la sesion activa.

## Flujo completo de creacion de sesion

1. `atlas-flow.service` ejecuta `app.ingest.watcher.run_ingest_watcher()`.
2. `build_ingest_watcher()` crea:
   - `IngestStore(INGEST_STORE_PATH)`
   - `IngestService(store, session_timeout_minutes=INGEST_SESSION_TIMEOUT_MINUTES)`
   - `IngestWatcher(service, FLOW_WATCH_DIRECTORIES)`
3. En el primer `scan_once()`, el watcher ejecuta `initialize_baseline()` y no registra fotos. Los archivos ya presentes y no registrados se agregan a `baseline_paths`; los archivos ya registrados en `ingest.json` quedan cubiertos por `known_paths`, no por `baseline_paths`.
4. En escaneos posteriores, `scan_once()` recorre recursivamente los JPG/JPEG del directorio observado.
5. Para cada archivo estable:
   - si su path esta en `registered_paths()`, lo ignora;
   - si su path esta en `baseline_paths`, lo ignora;
   - si no esta en ninguno, llama a `IngestService.register_received_photo()`.
6. `register_received_photo()`:
   - cierra sesiones activas vencidas;
   - busca una sesion activa valida con `get_active_session_from_payload()`;
   - si no existe, crea una con `create_session()`;
   - agrega la foto a `payload["photos"]`;
   - refresca `photo_count`, `last_received_at` y `sources`;
   - guarda todo en `ingest.json`.

La sesion creada tiene esta estructura base:

```json
{
  "id": "session-<uuid>",
  "started_at": "...",
  "last_received_at": "...",
  "status": "active",
  "photo_count": 0,
  "sources": []
}
```

## Como se determina la sesion activa

`IngestService.get_active_session()` muta el store solo para cerrar sesiones inactivas. No crea sesiones.

La sesion activa se calcula asi:

1. filtra `payload["sessions"]` por `status == "active"`;
2. ordena por `last_received_at` descendente;
3. toma la mas reciente;
4. si expiro por timeout, la marca como `closed` y devuelve `None`.

No existe un puntero persistido tipo `active_session_id`.

## Fuente de estado del Dashboard

Dashboard `/` renderiza `app/templates/index.html` con:

```python
flow_summary=build_flow_summary()
```

`build_flow_summary()`:

1. obtiene `ingest_service` y `store` desde `current_app.extensions["ingest"]`;
2. ejecuta `service.get_active_session()` para cerrar activas vencidas;
3. ejecuta `sync_flow_linked_coverages()`;
4. lee `store.list_sessions()`;
5. lee `store.list_photos()`;
6. calcula `active_sessions`, `active_photo_count`, `active_sources`, `recent_sessions` y `active_photos`.

El Dashboard no reconstruye sesiones desde filesystem. Solo muestra lo que ya esta en `ingest.json`.

## Fuente de estado de FLOW

`/flow/` usa la misma fuente:

```python
@web_bp.get("/flow")
def flow_home() -> str:
    return render_template("flow/index.html", flow_summary=build_flow_summary())
```

Por tanto Dashboard y FLOW leen el mismo `IngestStore` y la misma funcion `build_flow_summary()`.

Si ambos vuelven a mostrar una sesion, esa sesion ya fue reinsertada en `ingest.json` por otro componente. El componente que crea sesiones es el watcher.

## Flujo completo de eliminacion

### UI

En el working tree actual, `app/templates/flow/index.html` renderiza por sesion:

- `data-delete-check-url`
- `data-delete-url`
- boton `Eliminar sesión`
- indicador de fotos usadas en LENS

`app/static/js/flow_session_delete.js`:

1. abre el dialogo;
2. hace `GET` a `data-delete-check-url`;
3. si el check permite borrar, hace `POST` a `data-delete-url`;
4. si recibe `{ "ok": true }`, recarga la pagina.

El JS no construye manualmente URLs de FLOW; usa data attributes renderizados desde Flask.

### Endpoint

En el working tree actual:

```python
@web_bp.post("/flow/sessions/<session_id>/delete")
def flow_delete_session(session_id: str):
    return jsonify(delete_flow_session(session_id))
```

`delete_flow_session()`:

1. valida `session_id`;
2. entra a `store.mutate()`, con lock exclusivo sobre `ingest.json.lock`;
3. revalida que la sesion exista, no este activa y no tenga fotos usadas por LENS;
4. obtiene las fotos de la sesion desde `payload["photos"]`;
5. construye un plan de trash con `build_flow_trash_plan()`;
6. mueve originales con `move_flow_photos_to_trash()`;
7. elimina la sesion de `payload["sessions"]`;
8. elimina sus fotos de `payload["photos"]`;
9. guarda `ingest.json`;
10. intenta eliminar thumbnails asociados.

En el codigo actual sin commitear, el orden correcto es: mover originales fuera del arbol observado antes de confirmar la eliminacion del store.

## Que archivos elimina realmente

En el working tree actual, una eliminacion exitosa debe producir:

- `instance/ingest.json`: elimina la entrada de `sessions` para la sesion.
- `instance/ingest.json`: elimina las entradas de `photos` con ese `session_id`.
- `/data/FLOW/sftpgo/storage/events/...`: los JPG originales de esa sesion dejan de estar en `events`.
- `/data/FLOW/trash/<session-id>-<timestamp>/...`: recibe los JPG movidos.
- `/data/FLOW/trash/<session-id>-<timestamp>/manifest.json`: queda como manifiesto de papelera.

El lock `instance/ingest.json.lock` permanece. Eso es esperado.

Riesgo menor detectado: `delete_flow_thumbnails_for_plan()` calcula thumbnails usando `move["destination"]`, no el path original. Si el thumbnail cache key se basa en el path original, podrian quedar thumbnails huerfanos. Esto no explica la reaparicion de sesiones, porque el watcher no observa thumbnails.

## Que archivos permanecen despues del borrado

### Comportamiento problematico

Si la eliminacion solo borra registros de `ingest.json` y deja JPGs originales en:

```text
/data/FLOW/sftpgo/storage/events/...
```

entonces permanecen:

- originales JPG dentro del directorio observado;
- thumbnails/cache si existian;
- `ingest.json.lock`;
- posibles referencias LENS si no fueron bloqueadas antes.

Con esos originales todavia en `events`, el watcher puede reconstruir la sesion.

### Comportamiento esperado con papelera segura

Si los originales se mueven correctamente a `/data/FLOW/trash`, permanecen:

- originales en trash, fuera de `FLOW_WATCH_DIRECTORIES`;
- `manifest.json` de trash;
- `ingest.json.lock`;
- thumbnails si no se eliminaron.

En ese caso el watcher no deberia reconstruir la sesion, siempre que `FLOW_TRASH_ROOT` no este dentro de ningun watch root.

## Causa exacta del bug

La causa exacta es una inconsistencia entre el estado logico y el estado fisico:

1. La eliminacion reporta exito al usuario.
2. La sesion/fotos desaparecen de `ingest.json`.
3. Los JPG originales siguen dentro del directorio observado por `IngestWatcher`.
4. El watcher calcula `known_paths` desde `store.list_photos()`.
5. Como la eliminacion borro esas fotos del store, sus paths ya no estan en `known_paths`.
6. Esos paths tampoco necesariamente estan en `baseline_paths`, porque cuando el watcher arranco ya estaban registrados en `ingest.json`, asi que `initialize_baseline()` no los marco como baseline.
7. En el siguiente escaneo, el watcher interpreta esos JPG como llegada nueva.
8. `register_received_photo()` crea una nueva sesion activa si no hay una activa vigente.
9. Dashboard y FLOW leen `ingest.json` y muestran esa nueva sesion.

Dashboard no reconstruye la sesion directamente. La reconstruye el watcher y Dashboard la muestra.

## Por que aparece como "otra vez sesion activa"

La sesion que vuelve a verse puede no tener el mismo ID. El patron funcional esperado del bug es:

- desaparece la sesion eliminada;
- el watcher reingesta los mismos JPG fisicos;
- crea un nuevo `session-<uuid>`;
- el Dashboard muestra `RECIBIENDO: 1`, numero de fotos y camara derivada de esos JPG.

Desde la UI parece que "volvio la sesion", pero tecnicamente es una reingesta de los mismos archivos fisicos en una sesion nueva.

## Diferencia importante del working tree actual

El working tree actual ya contiene una implementacion de papelera segura que ataca la causa raiz:

- bloquea sesiones activas;
- bloquea fotos usadas en LENS;
- valida que los originales esten bajo `FLOW_EVENTS_ROOT`;
- mueve los originales a `FLOW_TRASH_ROOT`;
- solo despues elimina registros de `ingest.json`;
- falla con 409 si no puede mover archivos.

Si el bug sigue ocurriendo en produccion, las hipotesis mas probables son:

1. el servicio productivo no esta ejecutando este working tree;
2. el endpoint productivo que devuelve exito no esta moviendo los originales fuera de `events`;
3. `FLOW_TRASH_ROOT` o algun path de destino esta dentro de un directorio observado;
4. hay archivos nuevos llegando despues del borrado, lo que correctamente crea una nueva sesion;
5. quedan copias fisicas observables en `FLOW_WATCH_DIRECTORIES` que no fueron movidas por el delete.

## Propuesta minima de correccion

La correccion minima debe preservar una regla: no confirmar la eliminacion logica si los JPG fisicos siguen observables por FLOW.

Implementacion recomendada:

1. Mantener una sola fuente de verdad logica: `instance/ingest.json`.
2. En `POST /flow/sessions/<session_id>/delete`, dentro de una operacion bloqueada:
   - revalidar dependencias LENS;
   - revalidar que la sesion no este activa;
   - resolver todos los paths originales;
   - verificar que pertenecen a `FLOW_EVENTS_ROOT`;
   - verificar que el trash no esta dentro de `FLOW_WATCH_DIRECTORIES`;
   - mover originales a `/data/FLOW/trash/<session-id>-<timestamp>/`;
   - escribir `manifest.json`;
   - solo entonces eliminar `sessions[*]` y `photos[*]` del store.
3. Si algun move falla, hacer rollback de archivos movidos y dejar `ingest.json` intacto.
4. Confirmar en runtime que `FLOW_WATCH_DIRECTORIES` no incluye `/data/FLOW/trash`.
5. Agregar o mantener una prueba que reproduzca el bug: borrar sesion, ejecutar dos `scan_once()` del watcher, verificar que `ingest.json` sigue sin sesiones.

El working tree actual ya contiene pruebas alineadas con esta correccion, especialmente:

- `test_deleted_files_do_not_reappear_when_watcher_scans_events`
- `test_dashboard_and_flow_show_empty_after_delete`
- `test_bug_reproduction_many_files_do_not_reappear_after_delete_and_watcher_scans`

## Validacion recomendada sin tocar datos reales

Antes de activar en produccion, usar store temporal y directorios temporales:

1. crear una sesion con JPGs bajo un `events` temporal;
2. borrar via endpoint;
3. comprobar que `ingest.json` queda sin sesiones/fotos;
4. comprobar que los JPG ya no existen bajo `events`;
5. comprobar que existen bajo `trash`;
6. instanciar `IngestWatcher` sobre el `events` temporal;
7. ejecutar `scan_once()` dos veces;
8. comprobar que no se crea ninguna sesion.

## Conclusion

El bug no esta en Dashboard ni en FLOW como vistas. Ambas pantallas leen correctamente `ingest.json`.

El bug aparece cuando el borrado deja una discrepancia: estado logico eliminado, pero originales fisicos todavia dentro del directorio observado. El watcher es el componente que vuelve a crear la sesion.

La solucion minima es que el borrado sea transaccional respecto al estado logico y al filesystem: mover los originales fuera del arbol observado antes de eliminar las entradas de `ingest.json`, y devolver error si ese movimiento no puede garantizarse.
