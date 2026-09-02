# FLOW delete POSIX apply report

Fecha: 2026-08-18

## Resumen

Se aplico la solucion POSIX aprobada, limitada a `/data/FLOW/sftpgo/storage/events`, para permitir que `atlas-lens.service` pueda retirar/mover fotografias desde `events` hacia `/data/FLOW/trash`.

Tambien se configuro `UMask=0002` para `atlas-flow-organizer.service` mediante drop-in systemd y se corrigio la UX del modal FLOW para separar `photos_in_use` de `filesystem_error`.

No se hizo deploy de `atlas-lens`, no se reinicio `atlas-lens.service`, no se reinicio SFTPGo, no se borraron sesiones reales y no se movieron fotografias reales.

## Estado antes

Backup de permisos creado antes de modificar:

```text
docs/flow_events_permissions_before_posix_change.txt
```

Contenido: 293 entradas con tipo, mode, owner, group y path.

Ejemplo:

```text
d	775	root	root	/data/FLOW/sftpgo/storage/events
d	775	root	root	/data/FLOW/sftpgo/storage/events/2026
d	775	root	root	/data/FLOW/sftpgo/storage/events/2026/07
d	755	root	root	/data/FLOW/sftpgo/storage/events/2026/07/23
f	644	atlas	atlas	/data/FLOW/sftpgo/storage/events/2026/07/23/prueba-asamblea/ricardo/canon-r6/JPG/_21A8749.JPG
```

Backup de unidad organizer creado antes de modificar:

```text
docs/atlas_flow_organizer_service_before_posix_change.txt
```

Contenido relevante antes:

```ini
[Service]
Type=simple
User=atlas
ExecStart=/bin/bash -c 'while true; do /data/FLOW/scripts/atlas-flow-organize.sh; sleep 2; done'
Restart=always
RestartSec=5
```

## Comandos ejecutados

### Backup

```bash
find /data/FLOW/sftpgo/storage/events -printf '%y\t%m\t%u\t%g\t%p\n' > docs/flow_events_permissions_before_posix_change.txt
systemctl cat atlas-flow-organizer.service > docs/atlas_flow_organizer_service_before_posix_change.txt
```

### Arbol events existente

```bash
su -c 'chgrp -R atlas /data/FLOW/sftpgo/storage/events'
su -c 'find /data/FLOW/sftpgo/storage/events -type d -exec chmod 2775 {} +'
```

No se ejecuto `chown -R`.

No se uso `chmod 777`.

No se aplico chmod recursivo generico sobre archivos.

### UMask organizer

```bash
su -c 'mkdir -p /etc/systemd/system/atlas-flow-organizer.service.d'
su -c "printf '[Service]\nUMask=0002\n' > /etc/systemd/system/atlas-flow-organizer.service.d/override.conf"
su -c 'systemctl daemon-reload'
su -c 'systemctl restart atlas-flow-organizer.service'
```

Solo se reinicio `atlas-flow-organizer.service`.

## Permisos despues

Verificacion por niveles:

```text
drwxrwsr-x 2775 root atlas /data/FLOW/sftpgo/storage/events
drwxrwsr-x 2775 root atlas /data/FLOW/sftpgo/storage/events/2026
drwxrwsr-x 2775 root atlas /data/FLOW/sftpgo/storage/events/2026/08
drwxrwsr-x 2775 root atlas /data/FLOW/sftpgo/storage/events/2026/08/17
drwxrwsr-x 2775 root atlas /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura
drwxrwsr-x 2775 root atlas /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta
drwxrwsr-x 2775 root atlas /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6
drwxrwsr-x 2775 root atlas /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
```

Verificacion de JPG reales:

```text
-rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG/_21A5478.JPG
-rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG/_21A0627.JPG
-rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG/_21A2092.JPG
-rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG/_21A2083.JPG
-rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG/_21A2240.JPG
```

Verificaciones globales:

```bash
find /data/FLOW/sftpgo/storage/events -type d ! -group atlas -printf '%M %m %u %g %p\n'
find /data/FLOW/sftpgo/storage/events -type d ! -perm 2775 -printf '%M %m %u %g %p\n'
```

Resultado: sin salida; todos los directorios bajo `events` quedaron grupo `atlas` y modo `2775`.

## Configuracion UMask

Drop-in creado:

```text
/etc/systemd/system/atlas-flow-organizer.service.d/override.conf
```

Contenido:

```ini
[Service]
UMask=0002
```

Verificacion:

```text
MainPID=416065
UMask=0002
User=atlas
Group=
```

`systemctl cat atlas-flow-organizer.service` muestra la unidad original mas el drop-in.

## Estado del organizer

Comando:

```bash
systemctl is-active atlas-flow-organizer.service
```

Resultado:

```text
active
```

## Prueba temporal segura

No se usaron fotografias reales.

Se verifico previamente que no existieran los temporales:

```bash
test ! -e /data/FLOW/sftpgo/storage/events/.atlas_posix_test
test ! -e /data/FLOW/trash/.atlas_posix_test_file
```

Se creo un directorio temporal como `atlas`, simulando umask futura:

```bash
su -c "su atlas -c 'umask 0002; mkdir /data/FLOW/sftpgo/storage/events/.atlas_posix_test'"
```

Resultado:

```text
drwxrwsr-x 2775 atlas atlas /data/FLOW/sftpgo/storage/events/.atlas_posix_test
```

Se creo un archivo temporal:

```bash
su -c "su atlas -c 'touch /data/FLOW/sftpgo/storage/events/.atlas_posix_test/probe.tmp'"
```

Resultado:

```text
-rw-rw-r-- 664 atlas atlas /data/FLOW/sftpgo/storage/events/.atlas_posix_test/probe.tmp
drwxr-x--- 750 atlas atlas /data/FLOW/trash
```

Move temporal hacia trash:

```bash
su -c "su atlas -c 'mv /data/FLOW/sftpgo/storage/events/.atlas_posix_test/probe.tmp /data/FLOW/trash/.atlas_posix_test_file'"
```

Resultado: OK.

Limpieza de temporales:

```bash
su -c "su atlas -c 'rm /data/FLOW/trash/.atlas_posix_test_file && rmdir /data/FLOW/sftpgo/storage/events/.atlas_posix_test'"
test ! -e /data/FLOW/sftpgo/storage/events/.atlas_posix_test
test ! -e /data/FLOW/trash/.atlas_posix_test_file
```

Resultado: OK; no quedaron temporales.

## Cambios UX

Archivos modificados:

- `app/templates/flow/index.html`
- `app/static/js/flow_session_delete.js`
- `tests/test_flow_session_delete.py`

Correccion:

- `photos_in_use` ahora muestra "No se puede eliminar la sesión", explica que hay fotografias utilizadas por coberturas y muestra "Coberturas relacionadas" con la lista real.
- `filesystem_error` y otros errores operativos muestran "No se pudo eliminar la sesión" y el mensaje operativo.
- `filesystem_error` no muestra "Coberturas relacionadas".
- `filesystem_error` no indica que haya que retirar fotografias de LENS.
- Backend sigue fail-closed: si no se puede mover fisicamente, no elimina el registro logico.

## Tests

Pruebas especificas:

```bash
.venv/bin/python -m unittest tests.test_flow_session_delete
```

Resultado:

```text
Ran 27 tests in 1.057s

OK
```

`git diff --check`:

```text
OK
```

Suite completa:

```bash
.venv/bin/python -m unittest discover -s tests
```

Resultado:

```text
Ran 331 tests in 11.808s

OK
```

Durante la suite se observaron warnings/logs conocidos de imagenes dummy y `ResourceWarning`, sin fallos.

## Git status

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
?? docs/atlas_flow_organizer_service_before_posix_change.txt
?? docs/atlas_flow_permissions_predeploy.md
?? docs/atlas_flow_session_delete_report.md
?? docs/atlas_flow_session_reappears_analysis.md
?? docs/atlas_flow_session_trash_report.md
?? docs/atlas_routing_closeout.md
?? docs/flow_delete_acl_ux_fix_report.md
?? docs/flow_delete_deploy_validation.md
?? docs/flow_delete_posix_permissions_plan.md
?? docs/flow_delete_predeploy_validation.md
?? docs/flow_delete_real_failure_diagnosis.md
?? docs/flow_delete_runtime_permissions.md
?? docs/flow_events_permissions_before_posix_change.txt
?? docs/flow_session_persistence_audit.md
?? docs/flow_trash_runtime_ready.md
?? tests/test_flow_session_delete.py
```

Nota: `docs/flow_delete_posix_apply_report.md` se creo despues de capturar ese estado.

## Archivos modificados

Codigo/UX:

- `app/templates/flow/index.html`
- `app/static/js/flow_session_delete.js`
- `tests/test_flow_session_delete.py`

Ya existian cambios previos FLOW delete en:

- `app/__init__.py`
- `app/config.py`
- `app/routes/web.py`
- `app/static/css/main.css`

Operativo fuera de Git:

- `/etc/systemd/system/atlas-flow-organizer.service.d/override.conf`
- permisos/grupo bajo `/data/FLOW/sftpgo/storage/events`

Backups/informes:

- `docs/flow_events_permissions_before_posix_change.txt`
- `docs/atlas_flow_organizer_service_before_posix_change.txt`
- `docs/flow_delete_posix_apply_report.md`

## Rollback exacto

El rollback debe usar el inventario:

```text
docs/flow_events_permissions_before_posix_change.txt
```

Rollback por entrada, conservando paths exactos del inventario:

```bash
while IFS=$'\t' read -r type mode user group path; do
  [ -e "$path" ] || continue
  chown "$user:$group" "$path"
  chmod "$mode" "$path"
done < /opt/atlas-lens/docs/flow_events_permissions_before_posix_change.txt
```

Este rollback no usa `chown -R`; restaura entrada por entrada segun el inventario previo.

Rollback manual simplificado si se acepta volver al patron observado:

```bash
chgrp -R root /data/FLOW/sftpgo/storage/events
find /data/FLOW/sftpgo/storage/events -type d -exec chmod 755 {} +
chmod 775 /data/FLOW/sftpgo/storage/events
chmod 775 /data/FLOW/sftpgo/storage/events/2026
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW/ricardo
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW/ricardo/canon-r6
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW/ricardo/canon-r6/JPG
```

Rollback UMask:

```bash
rm /etc/systemd/system/atlas-flow-organizer.service.d/override.conf
rmdir /etc/systemd/system/atlas-flow-organizer.service.d 2>/dev/null || true
systemctl daemon-reload
systemctl restart atlas-flow-organizer.service
```

No ejecutar rollback salvo aprobacion explicita.

## Riesgos

- El grupo `atlas` ahora tiene escritura sobre directorios bajo `events`; es intencional para permitir delete seguro.
- Si algun proceso no previsto corre como usuario/grupo `atlas`, podria escribir en `events`.
- `UMask=0002` solo aplica al organizer reiniciado; no cambia SFTPGo.
- No se eliminaron sesiones reales, por lo que falta una prueba real controlada desde UI.
- No se reinicio `atlas-lens.service`; la UX corregida en JS/template no estara activa publicamente hasta deploy/restart de `atlas-lens`.

## Confirmaciones

- No se tocaron fotografias reales.
- No se eliminaron las sesiones reales de 22 y 171 fotografias.
- No se modifico manualmente `instance/ingest.json`.
- No se modifico Proxmox.
- No se modifico VirtioFS.
- No se modificaron mounts ni discos.
- No se modifico SFTPGo.
- No se reinicio SFTPGo.
- No se reinicio `atlas-lens.service`.
- No se hizo deploy de `atlas-lens`.
- No se hizo push.
