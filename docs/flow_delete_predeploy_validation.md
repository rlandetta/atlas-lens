# ATLAS FLOW delete predeploy validation

Fecha: 2026-08-17

## Alcance

Validacion pre-deploy de la correccion existente para eliminacion segura de sesiones FLOW mediante papelera/cuarentena.

No se modifico codigo funcional. No se tocaron fotografias reales, `instance/ingest.json`, servicios, Proxmox, VirtioFS, discos, deploy, restart, commit ni push.

## Archivos que contienen la correccion

Cambios funcionales en el working tree:

- `app/config.py`
  - agrega `FLOW_TRASH_ROOT`, con default `/data/FLOW/trash`.
- `app/__init__.py`
  - importa y expone `FLOW_TRASH_ROOT` en `app.config`.
- `app/routes/web.py`
  - agrega validacion de eliminacion de sesiones FLOW.
  - bloquea sesiones activas.
  - bloquea fotos usadas por LENS.
  - valida que los originales esten bajo `FLOW_EVENTS_ROOT`.
  - valida que `FLOW_TRASH_ROOT` no este observado por el watcher.
  - mueve originales a trash antes de eliminar registros del store.
  - escribe `manifest.json`.
  - hace rollback si falla el move.
  - elimina registros de `sessions` y `photos` solo despues del move correcto.
- `app/templates/flow/index.html`
  - renderiza boton `Eliminar sesión`.
  - renderiza indicador de fotografias usadas en LENS.
  - expone URLs mediante data attributes.
  - carga `static/js/flow_session_delete.js`.
- `app/static/js/flow_session_delete.js`
  - consume `data-delete-check-url` y `data-delete-url`.
  - ejecuta check previo y POST de borrado.
  - no hardcodea rutas.
- `app/static/css/main.css`
  - estilos de boton/dialogo/indicadores de eliminacion.
- `tests/test_flow_session_delete.py`
  - pruebas dedicadas de eliminacion segura, dependencia LENS, filesystem, watcher y UI.

Documentacion relacionada presente:

- `docs/flow_session_persistence_audit.md`
- `docs/atlas_flow_session_delete_report.md`
- `docs/atlas_flow_session_trash_report.md`
- `docs/atlas_flow_permissions_predeploy.md`
- `docs/atlas_flow_mount_verification.md`

## Estado del working tree

`git status --short` al inicio de la validacion:

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
?? docs/atlas_flow_mount_verification.md
?? docs/atlas_flow_permissions_predeploy.md
?? docs/atlas_flow_session_delete_report.md
?? docs/atlas_flow_session_reappears_analysis.md
?? docs/atlas_flow_session_trash_report.md
?? docs/atlas_routing_closeout.md
?? docs/flow_session_persistence_audit.md
?? tests/test_flow_session_delete.py
```

Los artefactos `atlas-convert-prototype.zip`, `atlas_convert_hif_fix_report.md` y `atlas_convert_install_report.md` no pertenecen a esta correccion.

## Configuracion esperada

Comando ejecutado:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from app import create_app
from app.config import FLOW_EVENTS_ROOT, FLOW_TRASH_ROOT, FLOW_WATCH_DIRECTORIES, INGEST_STORE_PATH

app = create_app()
with app.app_context():
    events = str(app.config.get('FLOW_EVENTS_ROOT') or FLOW_EVENTS_ROOT)
    trash = str(app.config.get('FLOW_TRASH_ROOT') or FLOW_TRASH_ROOT)
    watches = app.config.get('FLOW_WATCH_DIRECTORIES') or FLOW_WATCH_DIRECTORIES
    trash_path = Path(trash).resolve(strict=False)
    inside = []
    for watch in watches:
        watch_path = Path(str(watch)).resolve(strict=False)
        try:
            trash_path.relative_to(watch_path)
            inside.append(str(watch))
        except ValueError:
            pass
    print(f"INGEST_STORE_PATH={INGEST_STORE_PATH}")
    print(f"FLOW_EVENTS_ROOT={events}")
    print(f"FLOW_TRASH_ROOT={trash}")
    print("FLOW_WATCH_DIRECTORIES=" + ",".join(str(item) for item in watches))
    print(f"FLOW_TRASH_INSIDE_WATCH={bool(inside)}")
    if inside:
        print("WATCH_CONFLICTS=" + ",".join(inside))
PY
```

Resultado:

```text
INGEST_STORE_PATH=instance/ingest.json
FLOW_EVENTS_ROOT=/data/FLOW/sftpgo/storage/events
FLOW_TRASH_ROOT=/data/FLOW/trash
FLOW_WATCH_DIRECTORIES=/data/FLOW/sftpgo/storage/events
FLOW_TRASH_INSIDE_WATCH=False
```

Conclusion: `FLOW_TRASH_ROOT` no esta dentro de ningun `FLOW_WATCH_DIRECTORIES` con la configuracion esperada actual.

## Pruebas ejecutadas

### Suite dedicada de eliminacion FLOW

Comando:

```bash
.venv/bin/python -m unittest tests.test_flow_session_delete
```

Resultado:

```text
Ran 26 tests in 1.021s

OK
```

Cobertura funcional validada:

- eliminacion de sesiones FLOW;
- movimiento de originales a `FLOW_TRASH_ROOT`;
- bloqueo de fotografias utilizadas por LENS;
- rollback si falla filesystem/move;
- path traversal y symlink safety;
- no afectar sesiones ajenas;
- watcher despues de eliminar una sesion;
- Dashboard y FLOW vacios despues de eliminar;
- UI con boton `Eliminar sesión`;
- indicador de uso en LENS.

### Pruebas pedidas explicitamente

Comando:

```bash
.venv/bin/python -m unittest \
  tests.test_flow_session_delete.FlowSessionDeleteTest.test_deleted_files_do_not_reappear_when_watcher_scans_events \
  tests.test_flow_session_delete.FlowSessionDeleteTest.test_dashboard_and_flow_show_empty_after_delete \
  tests.test_flow_session_delete.FlowSessionDeleteTest.test_bug_reproduction_many_files_do_not_reappear_after_delete_and_watcher_scans
```

Resultado:

```text
Ran 3 tests in 0.185s

OK
```

Resultado individual:

- `test_deleted_files_do_not_reappear_when_watcher_scans_events`: OK.
- `test_dashboard_and_flow_show_empty_after_delete`: OK.
- `test_bug_reproduction_many_files_do_not_reappear_after_delete_and_watcher_scans`: OK.

### Whitespace check

Comando:

```bash
git diff --check
```

Resultado: OK, sin salida.

## Evaluacion de completitud

La correccion esta completa a nivel de codigo y pruebas dedicadas.

Puntos que quedan cubiertos:

- El endpoint no confirma borrado si la sesion sigue activa.
- El endpoint no confirma borrado si hay fotos usadas por LENS.
- Los originales se mueven fuera de `FLOW_EVENTS_ROOT`.
- El store se limpia solo despues de mover los originales.
- Si falla el filesystem, la respuesta es 409 y el store queda intacto.
- Si el watcher escanea despues del borrado, no reingesta las fotos eliminadas.
- Dashboard y FLOW quedan vacios despues de eliminar la ultima sesion en pruebas temporales.
- `FLOW_TRASH_ROOT` queda fuera del watch root esperado.

No se detecta necesidad de cambiar codigo antes del deploy.

## Riesgos y observaciones

- La validacion uso tests con directorios temporales. No se tocaron fotos reales ni `instance/ingest.json`.
- Antes del deploy real debe confirmarse en el entorno runtime que `/data/FLOW/trash` existe o puede ser creado por `atlas`, y que `atlas` puede mover archivos desde `events`.
- Si en produccion se configura `FLOW_WATCH_DIRECTORIES` de forma distinta y llega a incluir `/data/FLOW`, el endpoint deberia bloquear con `trash_observed` si el trash queda dentro de un watch root.
- Los cambios estan en working tree, no commiteados ni desplegados.
- Hay archivos no relacionados con FLOW delete en el working tree; no deben incluirse en un commit/deploy selectivo de esta correccion.

## Procedimiento minimo para activar sin afectar fotografias ni sesiones existentes

No ejecutar todavia; procedimiento recomendado cuando se apruebe el deploy:

1. Revisar staging/deploy selectivo para incluir solo:
   - `app/__init__.py`
   - `app/config.py`
   - `app/routes/web.py`
   - `app/static/css/main.css`
   - `app/templates/flow/index.html`
   - `app/static/js/flow_session_delete.js`
   - `tests/test_flow_session_delete.py`
   - documentacion FLOW correspondiente si se desea.
2. Excluir artefactos no relacionados:
   - `atlas-convert-prototype.zip`
   - `atlas_convert_hif_fix_report.md`
   - `atlas_convert_install_report.md`
3. Confirmar runtime env:
   - `FLOW_EVENTS_ROOT=/data/FLOW/sftpgo/storage/events`
   - `FLOW_TRASH_ROOT=/data/FLOW/trash`
   - `FLOW_WATCH_DIRECTORIES=/data/FLOW/sftpgo/storage/events`
4. Confirmar que `/data/FLOW/trash` queda fuera de `FLOW_WATCH_DIRECTORIES`.
5. Confirmar permisos sin tocar fotos reales:
   - `atlas` puede crear/escribir en `/data/FLOW/trash`.
   - `atlas` puede mover archivos desde un directorio de prueba controlado bajo FLOW, no desde sesiones reales.
6. Ejecutar pruebas antes de activar:
   - `.venv/bin/python -m unittest tests.test_flow_session_delete`
   - opcional: `.venv/bin/python -m unittest discover -s tests`
7. Activar el codigo en el servicio Flask con el mecanismo habitual aprobado.
8. Reiniciar solo `atlas-lens.service` cuando se apruebe la activacion.
9. No borrar ni migrar sesiones existentes. La correccion actua solo cuando el usuario pulse `Eliminar sesión`.
10. Verificar manualmente:
    - `/flow/` muestra boton `Eliminar sesión`.
    - el check de LENS bloquea sesiones con fotos usadas.
    - una sesion libre se mueve a trash.
    - Dashboard y FLOW quedan vacios si se elimino la ultima sesion.
    - el watcher no reconstruye la sesion tras varios segundos.

## Confirmacion

Durante esta validacion:

- No se borraron fotografias reales.
- No se modifico `instance/ingest.json`.
- No se hizo deploy.
- No se reiniciaron servicios.
- No se hizo push.
- No se hizo commit.
- No se modifico Proxmox, VirtioFS ni discos.
