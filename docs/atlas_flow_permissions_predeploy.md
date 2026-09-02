# ATLAS FLOW - Predeploy de permisos para papelera segura

Fecha: 2026-08-17

## Estado actual

Esta auditoria se realizo antes de activar la papelera segura de FLOW. No se ejecutaron cambios de permisos, no se creo `/data/FLOW/trash`, no se modificaron fotografias reales y no se reiniciaron servicios.

## Usuarios y grupos

`atlas-lens.service`:

```text
User=atlas
ExecStart=/opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
```

`atlas-flow.service`:

```text
User=atlas
ExecStart=/opt/atlas-lens/.venv/bin/python -c "from app.ingest.watcher import run_ingest_watcher; run_ingest_watcher()"
```

Usuario `atlas`:

```text
uid=1000(atlas) gid=1000(atlas) groups=1000(atlas),24(cdrom),25(floppy),29(audio),30(dip),44(video),46(plugdev),100(users),101(netdev)
```

Procesos relevantes:

```text
atlas atlas sftpgo serve
atlas atlas /opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
atlas atlas /opt/atlas-lens/.venv/bin/python -c from app.ingest.watcher import run_ingest_watcher; run_ingest_watcher()
atlas atlas /bin/bash -c while true; do /data/FLOW/scripts/atlas-flow-organize.sh; sleep 2; done
```

## Permisos actuales

Roots principales:

```text
drwxrwxr-x 775 nobody nogroup /data/FLOW
drwxrwxr-x 775 atlas  atlas   /data/FLOW/sftpgo
drwxrwxr-x 775 atlas  atlas   /data/FLOW/sftpgo/storage
drwxrwxr-x 775 nobody nogroup /data/FLOW/sftpgo/storage/events
/data/FLOW/trash no existe
```

Directorio inmediato dentro de `events` que contiene fotografias actuales:

```text
drwxrwxr-x 775 nobody nogroup /data/FLOW/sftpgo/storage/events/2026
```

Directorios `JPG` que contienen fotografias actuales:

```text
drwxrwxr-x 775 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/07/23/prueba-asamblea/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/07/24/asamblea/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/07/24/prueba-transferencia/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/07/25/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/08/09/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/08/12/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 nobody nogroup /data/FLOW/sftpgo/storage/events/2026/08/15/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
```

Fotografias actuales:

```text
atlas atlas 644 /data/FLOW/sftpgo/storage/events/.../*.JPG
```

Las fotografias pertenecen a `atlas:atlas`, pero mover o borrar un archivo requiere escritura en el directorio contenedor. La mayoria de directorios contenedores `JPG` son `755 nobody:nogroup`, por lo que `atlas` no puede retirar esos archivos.

## ACL

Herramientas:

```text
setfacl: no instalado
getfacl: no instalado
```

ACL actuales:

No se pudieron consultar porque `getfacl` no esta instalado.

Soporte ACL:

No se pudo validar con herramientas ACL. El mount donde vive `/data/FLOW` aparece como:

```text
/data atlas-data virtiofs ro,nosuid,nodev,relatime
```

`stat -f` reporta tipo `fuse`, y `lsattr` no esta soportado en ese filesystem.

Conclusion: ACL es la estrategia preferida, pero no esta disponible operativamente en este host tal como esta ahora.

## Filesystem y mount

`/data/FLOW` reside en:

```text
TARGET=/data
SOURCE=atlas-data
FSTYPE=virtiofs
OPTIONS=ro,nosuid,nodev,relatime
```

La opcion `ro` observada implica que cualquier cambio de permisos o creacion de `/data/FLOW/trash` podria requerir ejecutar el cambio desde el host/lado que monta `atlas-data` con escritura, o corregir el modo de montaje antes de aplicar permisos. En esta auditoria no se modifico Proxmox ni mounts.

## Proceso que crea fotografias y directorios

SFTPGo corre como `atlas:atlas` y recibe/custodia el area de storage.

El proceso que organiza las fotos hacia `events` es:

```text
/bin/bash -c while true; do /data/FLOW/scripts/atlas-flow-organize.sh; sleep 2; done
```

Script inspeccionado:

```text
/data/FLOW/scripts/atlas-flow-organize.sh
```

Logica relevante:

- lee `ATLAS_FLOW_ROOT` o usa `/data/FLOW`;
- toma archivos desde `/data/FLOW/sftpgo/storage/incoming/<camera>` o `/data/FLOW/sftpgo/storage/<camera>`;
- crea `DEST="$FLOW/events/$DATE/$EVENT/$PHOTOGRAPHER/$CAMERA/$TYPE"`;
- ejecuta `mkdir -p "$DEST" "$ARCHIVE"`;
- ejecuta `cp -p "$FILE" "$DEST/$NAME"`;
- si compara OK, mueve el incoming a archive.

El proceso corre como `atlas`, pero los directorios bajo `events` aparecen como `nobody:nogroup`, probablemente por el mapeo/propiedades del filesystem `virtiofs` o por directorios creados previamente con ese ownership.

## Causa exacta del Permission denied

El endpoint de eliminacion intenta retirar originales desde directorios como:

```text
/data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG
```

Esos directorios son mayoritariamente:

```text
drwxr-xr-x nobody:nogroup
```

El servicio Flask corre como:

```text
atlas:atlas
```

Aunque los JPG sean `atlas:atlas 0644`, para moverlos a trash hace falta permiso `w+x` sobre el directorio `JPG`. Como `atlas` no es owner ni pertenece a `nogroup`, solo recibe permisos de "otros": `r-x`. Por eso el `unlink` previo fallo con `Permission denied`, y el nuevo move a trash fallaria igual si no se corrigen permisos.

## Verificaciones de capacidad

No se creo `/data/FLOW/trash` porque la tarea prohibe cambios de permisos y aun no se debe modificar host.

La comprobacion efectiva con `runuser` no fue posible porque `runuser` no esta instalado. La alternativa con `setpriv` fallo por permisos de la sesion:

```text
setpriv: setgroups failed: Operation not permitted
```

Por tanto, la capacidad se determino por permisos POSIX observados:

- `atlas` no puede crear `/data/FLOW/trash` si `/data/FLOW` sigue `nobody:nogroup 775` y `atlas` no pertenece a `nogroup`.
- `atlas` no puede mover fotos desde directorios `JPG` con `nobody:nogroup 755`.
- `atlas` puede leer/atravesar esos directorios, por eso la ingesta y UI leen las fotos.

## Cambio minimo recomendado

Prioridad pedida: ACL especifica > grupo compartido > ownership.

ACL no esta disponible actualmente porque faltan `setfacl/getfacl`; por tanto el cambio minimo practicable ahora es de grupo/permisos, limitado al arbol FLOW observado y solo sobre directorios.

Objetivo:

- crear `/data/FLOW/trash` como `atlas:atlas 750`;
- dar al grupo `atlas` escritura/ejecucion sobre directorios bajo `/data/FLOW/sftpgo/storage/events`;
- activar setgid en directorios para que futuros subdirectorios hereden grupo `atlas`;
- no cambiar permisos de archivos JPG;
- no tocar nada fuera de `/data/FLOW`.

## Comandos propuestos PERO NO ejecutados

Backup de permisos de directorios antes del cambio:

```bash
find /data/FLOW/sftpgo/storage/events -type d -printf '%m\t%u\t%g\t%p\n' > /root/atlas-flow-events-dir-perms.pre-trash.tsv
```

Que modifica: nada; guarda permisos actuales para rollback.

Crear papelera:

```bash
install -d -o atlas -g atlas -m 750 /data/FLOW/trash
```

Que modifica: crea `/data/FLOW/trash` con owner/grupo controlado y acceso solo para `atlas`.

Ajustar grupo de directorios `events`:

```bash
find /data/FLOW/sftpgo/storage/events -type d -exec chgrp atlas {} +
```

Que modifica: cambia solo el grupo de directorios dentro de `events` a `atlas`.

Dar escritura/ejecucion al grupo solo en directorios:

```bash
find /data/FLOW/sftpgo/storage/events -type d -exec chmod g+rwx {} +
```

Que modifica: permite a procesos del grupo `atlas` crear/mover/eliminar entradas dentro de esos directorios.

Hacer que futuros directorios hereden grupo:

```bash
find /data/FLOW/sftpgo/storage/events -type d -exec chmod g+s {} +
```

Que modifica: activa setgid solo en directorios de `events`, para mantener grupo compartido.

Verificacion posterior propuesta:

```bash
stat -c '%A %a %U %G %n' /data/FLOW/trash /data/FLOW/sftpgo/storage/events
find /data/FLOW/sftpgo/storage/events -type d -path '*/JPG' -exec stat -c '%A %a %U %G %n' {} + | head
```

## Alternativa ACL preferida si se habilita ACL

Si se instala soporte de ACL y el filesystem lo soporta, la opcion mas fina seria:

```bash
install -d -o atlas -g atlas -m 750 /data/FLOW/trash
setfacl -R -m u:atlas:rwx /data/FLOW/sftpgo/storage/events
find /data/FLOW/sftpgo/storage/events -type d -exec setfacl -m d:u:atlas:rwx {} +
```

No se propone ejecutarla ahora porque `setfacl/getfacl` no existen en el host auditado.

## Rollback propuesto

Restaurar permisos de directorios desde backup:

```bash
while IFS=$'\t' read -r mode user group path; do
  chown "$user:$group" "$path"
  chmod "$mode" "$path"
done < /root/atlas-flow-events-dir-perms.pre-trash.tsv
```

Que revierte: owner/grupo/modo de cada directorio `events` al estado capturado antes del cambio.

Eliminar papelera solo si esta vacia y no se uso:

```bash
rmdir /data/FLOW/trash
```

Que revierte: elimina el directorio trash solo si no contiene archivos.

Si la papelera ya contiene lotes reales, no ejecutar `rm -rf`; mover/restaurar debe hacerse con una funcion especifica posterior.

## Riesgos

- El mount `/data` aparece como `ro` desde esta auditoria; si es el estado real del host, los comandos de permisos fallaran hasta resolver el montaje desde el lado operativo correspondiente.
- Cambiar grupo/permisos sobre directorios `events` permite a procesos del grupo `atlas` mover archivos dentro del arbol FLOW observado. Es necesario para la papelera, pero debe limitarse a usuarios confiables del grupo `atlas`.
- Si el script organizador o virtiofs vuelven a crear directorios como `nobody:nogroup 755`, puede hacer falta ajustar la creacion futura mediante ACL/default ACL o setgid efectivo.
- No se debe usar `chmod 777`, `chmod -R` amplio ni `chown -R` indiscriminado.

## Confirmacion de no cambios

No se ejecutaron:

- cambios de permisos;
- creacion de `/data/FLOW/trash`;
- movimientos, borrados o modificaciones sobre fotografias reales;
- deploy;
- restart;
- commit;
- push;
- cambios Apache;
- cambios DNS;
- cambios routing;
- cambios Docker;
- cambios Proxmox.

El unico archivo creado por esta tarea es este informe:

```text
/opt/atlas-lens/docs/atlas_flow_permissions_predeploy.md
```
