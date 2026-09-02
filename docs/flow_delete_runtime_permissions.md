# ATLAS FLOW delete runtime permissions

Fecha: 2026-08-17

## Alcance

Verificacion runtime y permisos previa al deploy de eliminacion segura de sesiones FLOW.

No se borraron fotografias reales, no se movieron fotografias de sesiones reales, no se modifico `instance/ingest.json`, no se modifico Proxmox/VirtioFS/discos/mounts, no se reiniciaron servicios, no se hizo deploy, commit ni push.

## Servicio runtime

Comando:

```bash
systemctl cat atlas-lens.service
```

Resultado relevante:

```ini
[Service]
Type=simple
User=atlas
WorkingDirectory=/opt/atlas-lens
Environment=PYTHONUNBUFFERED=1
Environment=ATLAS_URL_PREFIX=
ExecStart=/opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
Restart=always
RestartSec=3
```

Comando:

```bash
systemctl status atlas-lens.service --no-pager
```

Resultado relevante:

```text
Active: active (running) since Mon 2026-08-17 01:27:55 -05
Main PID: 2469408 (flask)
```

Comando:

```bash
systemctl show atlas-lens.service -p User -p Group -p MainPID -p Environment -p FragmentPath -p ExecStart
```

Resultado:

```text
MainPID=2469408
Environment=PYTHONUNBUFFERED=1 ATLAS_URL_PREFIX=
User=atlas
Group=
FragmentPath=/etc/systemd/system/atlas-lens.service
```

`Group=` no esta definido explicitamente. Systemd usa el grupo primario del usuario `atlas`.

Comando:

```bash
id atlas
```

Resultado:

```text
uid=1000(atlas) gid=1000(atlas) groups=1000(atlas),24(cdrom),25(floppy),29(audio),30(dip),44(video),46(plugdev),100(users),101(netdev)
```

Conclusion:

- Usuario efectivo del servicio: `atlas`.
- Grupo efectivo primario: `atlas`.

## Entorno runtime del proceso vivo

Comando:

```bash
tr '\0' '\n' < /proc/2469408/environ | grep -E '^(FLOW_EVENTS_ROOT|FLOW_TRASH_ROOT|FLOW_WATCH_DIRECTORIES|INGEST_STORE_PATH|ATLAS_URL_PREFIX|PYTHONUNBUFFERED)='
```

Resultado:

```text
PYTHONUNBUFFERED=1
ATLAS_URL_PREFIX=
```

El proceso vivo no tiene variables explicitas para:

- `FLOW_EVENTS_ROOT`
- `FLOW_TRASH_ROOT`
- `FLOW_WATCH_DIRECTORIES`
- `INGEST_STORE_PATH`

Por tanto, tras activar el codigo actual, usaria los defaults definidos en `app/config.py`.

## Configuracion efectiva esperada con el working tree actual

Comando:

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
    conflicts = []
    for watch in watches:
        watch_path = Path(str(watch)).resolve(strict=False)
        try:
            trash_path.relative_to(watch_path)
            conflicts.append(str(watch))
        except ValueError:
            pass
    print(f'INGEST_STORE_PATH={INGEST_STORE_PATH}')
    print(f'FLOW_EVENTS_ROOT={events}')
    print(f'FLOW_TRASH_ROOT={trash}')
    print('FLOW_WATCH_DIRECTORIES=' + ','.join(str(item) for item in watches))
    print(f'FLOW_TRASH_INSIDE_WATCH={bool(conflicts)}')
    if conflicts:
        print('WATCH_CONFLICTS=' + ','.join(conflicts))
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

Conclusion:

- `FLOW_TRASH_ROOT` no queda dentro de `FLOW_WATCH_DIRECTORIES`.
- La configuracion esperada es compatible con la correccion.

## Mount real de /data

Dentro del sandbox de Codex, `/data` se veia como `ro`. Se repitio la comprobacion fuera del sandbox para obtener la vista real del host.

Comandos:

```bash
findmnt /data
findmnt -T /data/FLOW
```

Resultado real:

```text
TARGET SOURCE     FSTYPE   OPTIONS
/data  atlas-data virtiofs rw,relatime
```

Conclusion: el mount real esta `rw`.

## Permisos actuales

Comandos:

```bash
stat -c '%A %a %U %G %n' /data /data/FLOW /data/FLOW/sftpgo/storage/events /data/FLOW/trash
ls -ld /data/FLOW /data/FLOW/sftpgo/storage/events /data/FLOW/trash
namei -l /data/FLOW/trash
```

Resultado:

```text
stat: cannot statx '/data/FLOW/trash': No such file or directory
drwxr-xr-x 755 root root /data
drwxrwxr-x 775 root root /data/FLOW
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events
```

```text
ls: cannot access '/data/FLOW/trash': No such file or directory
drwxrwxr-x 11 root root 4096 Jul 24 12:21 /data/FLOW
drwxrwxr-x  3 root root 4096 Jul 22 14:46 /data/FLOW/sftpgo/storage/events
```

```text
f: /data/FLOW/trash
drwxr-xr-x root root /
drwxr-xr-x root root data
drwxrwxr-x root root FLOW
                      trash - No such file or directory
```

Conclusion:

- `/data/FLOW/trash` no existe.
- `/data/FLOW` existe como `root:root 775`.
- `/data/FLOW/sftpgo/storage/events` existe como `root:root 775`.
- El usuario `atlas` no pertenece al grupo `root`, por lo que no puede escribir en `/data/FLOW` solo por esos permisos.

## Prueba de escritura

No se creo archivo temporal porque `/data/FLOW/trash` no existe y la instruccion fue no crearlo todavia.

Se uso `test -w` sin modificar archivos.

Comandos:

```bash
test -w /data/FLOW
test -w /data/FLOW/sftpgo/storage/events
test -d /data/FLOW/trash
whoami
groups
```

Resultados:

```text
FLOW_PARENT_WRITABLE_BY_CURRENT_USER=1
EVENTS_WRITABLE_BY_CURRENT_USER=1
TRASH_EXISTS=1
```

En `test`, salida `1` significa falso/no.

Usuario efectivo de la comprobacion:

```text
atlas
```

Grupos efectivos:

```text
atlas cdrom floppy audio dip video plugdev users netdev
```

Conclusion:

- `atlas` no puede escribir actualmente en `/data/FLOW`.
- `atlas` no puede crear `/data/FLOW/trash`.
- No se pudo comprobar escritura dentro de `/data/FLOW/trash` porque el directorio no existe.

## Bloqueo para deploy

Si se despliega la correccion sin preparar `/data/FLOW/trash`, una eliminacion de sesion libre probablemente fallara con error controlado `filesystem_error/trash_unwritable`, porque el codigo intentara crear o usar `/data/FLOW/trash` como usuario `atlas`.

Este fallo seria seguro para los datos: el endpoint debe devolver 409 y no borrar registros del store si no puede mover originales. Pero funcionalmente bloquearia la eliminacion segura.

## Accion minima necesaria antes del deploy

Crear el directorio de trash y asignarlo al usuario/grupo del servicio:

```bash
sudo mkdir -p /data/FLOW/trash
sudo chown atlas:atlas /data/FLOW/trash
sudo chmod 750 /data/FLOW/trash
```

Que modifica cada comando:

- `mkdir -p /data/FLOW/trash`: crea solo el directorio de papelera FLOW si no existe.
- `chown atlas:atlas /data/FLOW/trash`: permite que el servicio `atlas-lens.service` administre el contenido de la papelera.
- `chmod 750 /data/FLOW/trash`: concede acceso completo a `atlas`, lectura/entrada al grupo `atlas`, y nada a otros.

Ademas, antes de activar borrado real, conviene confirmar en un directorio de prueba controlado, no en sesiones reales, que `atlas` puede mover un archivo hacia `/data/FLOW/trash`.

No ejecutar todavia estos comandos hasta aprobar la preparacion runtime.

## Respuestas directas

A. Usuario y grupo de `atlas-lens.service`:

- Usuario: `atlas`.
- Grupo primario: `atlas`.

B. Configuracion runtime efectiva esperada de FLOW:

- `INGEST_STORE_PATH=instance/ingest.json`
- `FLOW_EVENTS_ROOT=/data/FLOW/sftpgo/storage/events`
- `FLOW_TRASH_ROOT=/data/FLOW/trash`
- `FLOW_WATCH_DIRECTORIES=/data/FLOW/sftpgo/storage/events`

C. `/data/FLOW/trash`:

- No existe.

D. Propietario y permisos de trash:

- No aplica porque el directorio no existe.

E. Escritura:

- El servicio no puede escribir en `/data/FLOW/trash` porque no existe.
- El usuario `atlas` tampoco puede crearlo bajo `/data/FLOW` con los permisos actuales.

F. Bloqueo para deploy:

- Si, falta crear/preparar `/data/FLOW/trash` para `atlas`.

G. Accion minima:

- Crear `/data/FLOW/trash` con owner `atlas:atlas` y permisos `750`, y despues validar escritura con un archivo temporal vacio dentro de trash.

## Confirmacion de no cambios

Durante esta verificacion:

- No se crearon directorios.
- No se crearon archivos temporales.
- No se borraron fotografias reales.
- No se movieron fotografias reales.
- No se modifico `instance/ingest.json`.
- No se modifico Proxmox, VirtioFS, discos ni mounts.
- No se reiniciaron servicios.
- No se hizo deploy.
- No se hizo commit.
- No se hizo push.
