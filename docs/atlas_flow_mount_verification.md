# ATLAS FLOW mount verification

Fecha: 2026-08-17

## Alcance

Verificacion final, solo lectura, del mount `/data` antes de aplicar cualquier cambio de permisos para la papelera segura de FLOW.

No se ejecutaron remounts, cambios de Proxmox, `chmod`, `chown`, `chgrp`, creacion de `/data/FLOW/trash`, deploy, restart, commit ni push.

## Comandos ejecutados

```bash
findmnt /data
findmnt -T /data/FLOW
mount | grep -E ' /data |atlas-data|virtiofs'
cat /proc/mounts | grep -E ' /data |atlas-data|virtiofs'
stat -f -c '%T' /data
stat -c '%A %a %U %G %n' /data /data/FLOW /data/FLOW/sftpgo/storage/events
readlink -f /data/FLOW /data/FLOW/sftpgo /data/FLOW/sftpgo/storage /data/FLOW/sftpgo/storage/incoming /data/FLOW/sftpgo/storage/archive /data/FLOW/sftpgo/storage/events /data/FLOW/scripts/atlas-flow-organize.sh
findmnt -T /data/FLOW
findmnt -T /data/FLOW/sftpgo
findmnt -T /data/FLOW/sftpgo/storage
findmnt -T /data/FLOW/sftpgo/storage/incoming
findmnt -T /data/FLOW/sftpgo/storage/archive
findmnt -T /data/FLOW/sftpgo/storage/events
findmnt -R /data
sed -n '1,220p' /etc/fstab
sed -n '1,220p' /run/systemd/generator/data.mount
grep -RInE 'atlas-data|/data|virtiofs|FLOW' /etc/systemd /etc/fstab /etc 2>/dev/null
sed -n '1,180p' /etc/systemd/system/atlas-flow.service
sed -n '1,180p' /etc/systemd/system/atlas-flow-organizer.service
systemctl show -p User -p Group -p FragmentPath -p ExecStart atlas-flow.service atlas-flow-organizer.service atlas-lens.service
ps -eo user,group,pid,ppid,cmd | grep -E 'sftpgo serve|run_ingest_watcher|atlas-flow-organize|flask --app app'
find /data/FLOW/sftpgo/storage -maxdepth 2 -type l -o -type d -printf '%M %m %u %g %p\n'
find /data/FLOW/sftpgo/storage -type f -printf '%TY-%Tm-%Td %TH:%TM %u %g %m %p\n' | sort | tail -40
```

No se hizo prueba de escritura porque no existe un directorio de pruebas ya preparado en `/data/FLOW` y la instruccion fue no crear `/data/FLOW/trash` ni tocar datos reales.

## Resultados principales

`findmnt /data`:

```text
TARGET SOURCE     FSTYPE   OPTIONS
/data  atlas-data virtiofs ro,nosuid,nodev,relatime
```

`findmnt -T /data/FLOW`:

```text
TARGET SOURCE     FSTYPE   OPTIONS
/data  atlas-data virtiofs ro,nosuid,nodev,relatime
```

`mount` y `/proc/mounts` confirman:

```text
atlas-data on /data type virtiofs (ro,nosuid,nodev,relatime)
atlas-data /data virtiofs ro,nosuid,nodev,relatime 0 0
```

Tipo de filesystem reportado por `stat -f`:

```text
fuse
```

Permisos base:

```text
drwxr-xr-x 755 nobody nogroup /data
drwxrwxr-x 775 nobody nogroup /data/FLOW
drwxrwxr-x 775 nobody nogroup /data/FLOW/sftpgo/storage/events
```

## Topologia real de mounts

Todos los paths relevantes resuelven dentro de `/data`:

```text
/data/FLOW
/data/FLOW/sftpgo
/data/FLOW/sftpgo/storage
/data/FLOW/sftpgo/storage/incoming
/data/FLOW/sftpgo/storage/archive
/data/FLOW/sftpgo/storage/events
/data/FLOW/scripts/atlas-flow-organize.sh
```

`findmnt -T` sobre cada uno de esos paths devuelve el mismo mount:

```text
/data atlas-data virtiofs ro,nosuid,nodev,relatime
```

`findmnt -R /data` no muestra submounts adicionales debajo de `/data`.

Conclusion: no se encontro ningun bind mount, symlink o mount alternativo writable usado por `incoming`, `archive`, `events` o el organizador dentro de este sistema.

## Donde se define `atlas-data`

`/etc/fstab` contiene:

```text
atlas-data   /data   virtiofs defaults 0 0
atlas-backup /backup virtiofs defaults 0 0
```

La unidad generada por systemd es `/run/systemd/generator/data.mount`:

```ini
[Mount]
What=atlas-data
Where=/data
Type=virtiofs
```

Aunque `fstab` usa `defaults`, el estado efectivo montado en este entorno es `ro,nosuid,nodev,relatime`.

## Paths de SFTPGo y FLOW

Procesos reales observados:

```text
atlas atlas sftpgo serve
atlas atlas /opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
atlas atlas /opt/atlas-lens/.venv/bin/python -c from app.ingest.watcher import run_ingest_watcher; run_ingest_watcher()
atlas atlas /bin/bash -c while true; do /data/FLOW/scripts/atlas-flow-organize.sh; sleep 2; done
```

Servicios:

```text
atlas-flow.service: User=atlas
atlas-flow-organizer.service: User=atlas
atlas-lens.service: User=atlas
```

`atlas-flow-organizer.service` ejecuta:

```bash
while true; do /data/FLOW/scripts/atlas-flow-organize.sh; sleep 2; done
```

El script `atlas-flow-organize.sh` usa por defecto:

```text
BASE_ROOT=/data/FLOW
FLOW=/data/FLOW/sftpgo/storage
SOURCE=/data/FLOW/sftpgo/storage/incoming/<camera>
fallback SOURCE=/data/FLOW/sftpgo/storage/<camera>
DEST=/data/FLOW/sftpgo/storage/events/<date>/<event>/<photographer>/<camera>/<type>
ARCHIVE=/data/FLOW/sftpgo/storage/archive/<date>/<camera>
```

## Estado writable/read-only efectivo

Desde este sistema, `/data` esta montado read-only. Eso impide crear directorios nuevos, mover archivos entre directorios o eliminar entradas dentro de `/data`, independientemente de que algunos directorios tengan bits de grupo escribibles.

Ademas, incluso si el mount estuviera read-write, los permisos actuales seguirian bloqueando operaciones de borrado/move para `atlas` en varios directorios de `events`, porque hay directorios `755 nobody:nogroup`. Para mover o eliminar un archivo hace falta permiso de escritura en el directorio contenedor, no solo ownership del archivo.

Ejemplos de permisos encontrados:

```text
drwxrwxr-x 775 atlas atlas /data/FLOW/sftpgo/storage
drwxrwxr-x 775 nobody nogroup /data/FLOW/sftpgo/storage/archive
drwxr-xr-x 755 atlas atlas /data/FLOW/sftpgo/storage/incoming
drwxrwxr-x 775 nobody nogroup /data/FLOW/sftpgo/storage/events
drwxrwxr-x 775 nobody nogroup /data/FLOW/sftpgo/storage/events/2026
```

## Evidencia de fotografias recientes

Los archivos mas recientes listados bajo `/data/FLOW/sftpgo/storage` tienen timestamp del 2026-08-15, por ejemplo:

```text
2026-08-15 11:32 atlas atlas 644 /data/FLOW/sftpgo/storage/archive/2026/08/15/canon-r6/_21A5413.JPG
2026-08-15 11:32 atlas atlas 644 /data/FLOW/sftpgo/storage/events/2026/08/15/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG/_21A5413.JPG
```

Esto demuestra que FLOW escribio en algun momento, pero no demuestra que pueda escribir actualmente con el mount en `ro`.

## Explicacion de la aparente contradiccion

La contradiccion se resuelve asi:

1. El estado efectivo actual de `/data` dentro de este sistema es `virtiofs ro`.
2. No hay evidencia de que SFTPGo u organizer usen otro path writable para `incoming`, `archive` o `events`.
3. Los procesos reales que escriben FLOW corren como `atlas`, pero si el mount permanece `ro`, esos procesos no deberian poder crear ni mover archivos nuevos bajo `/data`.
4. Las fotografias existentes pueden haber sido creadas antes de que `/data` quedara montado `ro`, o desde el lado/exportador de Proxmox cuando el storage estaba writable.
5. Otra posibilidad operativa es que Proxmox/export exponga el mismo storage como writable en otro contexto, pero en este sistema invitado el mount visible es read-only.

Conclusion: la informacion anterior no fue interpretada al reves; el mount actual realmente se ve read-only desde este sistema. Lo que no queda probado es que las escrituras sigan funcionando en este instante bajo ese mismo estado `ro`.

## Puede escribir el usuario `atlas`

Conclusion tecnica sin prueba destructiva:

- En `/data`: no deberia poder escribir desde este sistema porque el mount esta `ro`.
- En `/data/FLOW`: no deberia poder crear nuevos directorios desde este sistema porque el mount esta `ro`.
- En directorios `events` historicos: no deberia poder mover/eliminar archivos donde el directorio sea `755 nobody:nogroup`; aun con mount `rw`, faltaria permiso de escritura en el directorio.

No se hizo prueba de escritura porque no habia un path temporal seguro ya existente y la auditoria prohibio crear nuevos directorios o tocar datos reales.

## Donde aplicar permisos

El cambio de permisos no debe ejecutarse todavia desde este sistema mientras `/data` este montado `ro`.

La siguiente accion debe hacerse desde el host Proxmox o desde el entorno que define/exporta `atlas-data` por virtiofs:

1. Verificar por que `atlas-data` llega como read-only al sistema ATLAS aunque `/etc/fstab` declare `defaults`.
2. Corregir la exposicion/mount para que `/data` sea read-write solo si ese es el estado operativo esperado para FLOW.
3. Una vez que `/data` sea realmente writable, aplicar el cambio minimo de permisos sobre el arbol FLOW necesario para mover fotografias desde `events` hacia `trash`.

Prioridad recomendada para permisos:

1. ACL especifica para `atlas` si ACL esta disponible en el lado que realmente controla el storage.
2. Grupo compartido limitado al arbol FLOW si ACL no esta disponible.
3. Cambio puntual de ownership solo si las dos opciones anteriores no son viables.

No usar `chmod 777`, `chmod -R` amplio, `chown -R` indiscriminado ni cambios sobre todo `/data`.

## Siguiente accion exacta recomendada

Desde el host Proxmox o el host que exporta `atlas-data`:

```bash
# Solo inspeccion, antes de tocar nada:
qm config <VMID> | grep -iE 'virtiofs|atlas-data|data'
mount | grep -E 'atlas-data|/data'
findmnt | grep -E 'atlas-data|/data'
```

Luego, si se confirma que la VM/entorno ATLAS debe escribir en `/data`, preparar un cambio controlado para exponer `atlas-data` como read-write al invitado ATLAS y validar de nuevo desde el sistema ATLAS:

```bash
findmnt /data
findmnt -T /data/FLOW
```

Solo despues de confirmar `rw`, aplicar permisos minimos sobre FLOW desde el lado writable. El comando exacto de permisos debe decidirse con la salida real del host/exportador y la disponibilidad real de ACL en ese lado.

## Riesgos

- Aplicar permisos dentro del invitado mientras `/data` esta `ro` fallara o dara una falsa sensacion de solucion.
- Cambiar ownership de forma amplia podria romper SFTPGo, historicos o integraciones de LENS.
- Hacer `chmod -R` amplio podria exponer fotografias y metadatos de forma innecesaria.
- Si Proxmox exporta `atlas-data` intencionalmente como read-only, el problema no es de permisos POSIX sino de topologia/mount.
- Si se cambia a `rw` sin revisar el modelo de usuarios, `atlas` podria seguir sin poder mover archivos dentro de directorios `755 nobody:nogroup`.

## Confirmacion de cero cambios

Durante esta verificacion:

- No se hizo remount.
- No se modifico Proxmox.
- No se ejecuto `chmod`, `chown` ni `chgrp`.
- No se creo `/data/FLOW/trash`.
- No se modificaron fotografias reales.
- No se hizo deploy.
- No se reiniciaron servicios.
- No se hizo commit.
- No se hizo push.
