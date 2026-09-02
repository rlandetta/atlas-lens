# ATLAS FLOW delete deploy validation

Fecha: 2026-08-17

## Alcance

Deploy controlado de la correccion de eliminacion segura de sesiones FLOW ya presente en `/opt/atlas-lens`.

Se reinicio exclusivamente `atlas-lens.service`.

No se hizo `git pull`, `git reset`, `checkout`, `push`, commit, deploy externo adicional, cambios de Proxmox, VirtioFS, mounts ni discos. No se borraron ni movieron fotografias reales. No se modifico manualmente `instance/ingest.json`. No se invoco ningun endpoint real de eliminacion.

## Fase 1 - Predeploy

### Estado Git

Comando:

```bash
git status --short
```

Resultado:

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
?? docs/flow_delete_predeploy_validation.md
?? docs/flow_delete_runtime_permissions.md
?? docs/flow_session_persistence_audit.md
?? docs/flow_trash_runtime_ready.md
?? tests/test_flow_session_delete.py
```

### Whitespace check

Comando:

```bash
git diff --check
```

Resultado: OK, sin salida.

### Archivos funcionales FLOW delete

Archivos funcionales activados:

- `app/__init__.py`
- `app/config.py`
- `app/routes/web.py`
- `app/static/css/main.css`
- `app/templates/flow/index.html`
- `app/static/js/flow_session_delete.js`
- `tests/test_flow_session_delete.py`

Los artefactos ATLAS Convert y otros informes no relacionados no forman parte de la activacion funcional:

- `atlas-convert-prototype.zip`
- `atlas_convert_hif_fix_report.md`
- `atlas_convert_install_report.md`

### Pruebas pre-restart

Comando:

```bash
.venv/bin/python -m unittest tests.test_flow_session_delete
```

Resultado:

```text
Ran 26 tests in 1.077s

OK
```

## Fase 2 - Activacion

### Confirmacion de servicio

Comando:

```bash
systemctl cat atlas-lens.service
```

Resultado relevante:

```ini
WorkingDirectory=/opt/atlas-lens
Environment=ATLAS_URL_PREFIX=
ExecStart=/opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
User=atlas
```

Comando:

```bash
systemctl show atlas-lens.service -p WorkingDirectory -p ExecStart -p User -p FragmentPath -p MainPID
```

Resultado relevante:

```text
WorkingDirectory=/opt/atlas-lens
User=atlas
FragmentPath=/etc/systemd/system/atlas-lens.service
```

Conclusion: `atlas-lens.service` ejecuta el working tree validado en `/opt/atlas-lens`.

### Restart

El primer intento directo:

```bash
systemctl restart atlas-lens.service
```

fue denegado por permisos de la sesion:

```text
Failed to restart atlas-lens.service: Access denied
```

Se ejecuto el restart autorizado mediante `su`:

```bash
su -c 'systemctl restart atlas-lens.service'
```

Resultado: OK.

### Estado posterior

Comando:

```bash
systemctl status atlas-lens.service --no-pager
```

Resultado relevante:

```text
Active: active (running) since Mon 2026-08-17 20:50:20 -05
Main PID: 3723395 (flask)
```

## Logs recientes

Comando:

```bash
journalctl -u atlas-lens.service -n 80 --no-pager
```

Resultado posterior al restart:

```text
Aug 17 20:50:21 atlas-apps flask[3723395]:  * Serving Flask app 'app'
Aug 17 20:50:21 atlas-apps flask[3723395]:  * Debug mode: off
Aug 17 20:50:21 atlas-apps flask[3723395]: WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
Aug 17 20:50:21 atlas-apps flask[3723395]:  * Running on all addresses (0.0.0.0)
Aug 17 20:50:21 atlas-apps flask[3723395]:  * Running on http://127.0.0.1:5001
Aug 17 20:50:21 atlas-apps flask[3723395]:  * Running on http://192.168.1.45:5001
Aug 17 20:50:21 atlas-apps flask[3723395]: Press CTRL+C to quit
Aug 17 20:50:29 atlas-apps flask[3723395]: 127.0.0.1 - - [17/Aug/2026 20:50:29] "GET /flow/ HTTP/1.1" 200 -
Aug 17 20:50:29 atlas-apps flask[3723395]: 127.0.0.1 - - [17/Aug/2026 20:50:29] "GET / HTTP/1.1" 200 -
```

No se observaron tracebacks ni errores de importacion. La advertencia sobre Flask development server ya existia como condicion operativa y no esta relacionada con FLOW delete.

## Fase 3 - Verificacion sin borrar

### FLOW

Comando:

```bash
curl -s -o /tmp/atlas_flow_deploy_check.html -w '%{http_code}' http://127.0.0.1:5001/flow/
```

Resultado:

```text
200
```

HTML verificado:

```text
Eliminar sesión
/static/js/flow_session_delete.js
22 fotografías usadas en LENS
```

### Dashboard

Comando:

```bash
curl -s -o /tmp/atlas_dashboard_deploy_check.html -w '%{http_code}' http://127.0.0.1:5001/
```

Resultado:

```text
200
```

HTML verificado:

```text
BIENVENIDO A ATLAS
Centro editorial
```

## Resultado

A. Resultado de pruebas antes del restart:

- `tests.test_flow_session_delete`: 26 tests OK.
- `git diff --check`: OK.

B. Archivos FLOW delete activados:

- `app/__init__.py`
- `app/config.py`
- `app/routes/web.py`
- `app/static/css/main.css`
- `app/templates/flow/index.html`
- `app/static/js/flow_session_delete.js`
- `tests/test_flow_session_delete.py`

C. Estado de `atlas-lens.service`:

- `Active: active (running)`.
- PID nuevo: `3723395`.

D. FLOW:

- `http://127.0.0.1:5001/flow/` responde `200`.

E. Dashboard:

- `http://127.0.0.1:5001/` responde `200`.

F. Boton:

- El HTML de FLOW contiene `Eliminar sesión`.
- Tambien carga `flow_session_delete.js`.
- El indicador de uso LENS aparece en la pagina.

G. Errores:

- No hubo tracebacks ni errores de importacion.
- El intento inicial de restart sin privilegios fue denegado, luego se ejecuto correctamente via `su`.

H. Siguiente paso:

- El sistema queda listo para una prueba real controlada desde la interfaz, sin haber invocado todavia ningun endpoint de eliminacion real durante esta validacion.

## Confirmacion final

- No se hizo commit.
- No se hizo push.
- No se toco Proxmox, VirtioFS, mounts ni discos.
- No se modifico Apache.
- No se movieron ni borraron fotografias reales.
- No se modifico manualmente `instance/ingest.json`.
- No se invoco ningun endpoint de eliminacion real.
