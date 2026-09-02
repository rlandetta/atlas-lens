# FLOW delete POSIX permissions plan

Fecha: 2026-08-17

## Alcance

Diagnostico solamente para disenar una solucion POSIX minima y segura despues de descartar ACL sobre VirtioFS por `Operation not supported`.

No se ejecuto `chmod`, `chown`, `chgrp`, no se crearon grupos, no se modificaron usuarios ni membresias, no se modifico SFTPGo ni servicios, no se modifico Proxmox/VirtioFS/mounts/discos, no se movieron ni borraron fotografias, no se hizo deploy/restart/commit/push.

## 1. Usuarios y grupos de servicios

Comando:

```bash
systemctl show atlas-lens.service atlas-flow.service atlas-flow-organizer.service sftpgo.service -p User -p Group -p SupplementaryGroups -p ExecStart -p WorkingDirectory -p MainPID -p FragmentPath
```

Resultado relevante:

```text
atlas-lens.service:
MainPID=3723395
WorkingDirectory=/opt/atlas-lens
User=atlas
Group=
SupplementaryGroups=
ExecStart=/opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001

atlas-flow.service:
MainPID=3100118
WorkingDirectory=/opt/atlas-lens
User=atlas
Group=
SupplementaryGroups=
ExecStart=/opt/atlas-lens/.venv/bin/python -c from app.ingest.watcher import run_ingest_watcher; run_ingest_watcher()

atlas-flow-organizer.service:
MainPID=3105492
User=atlas
Group=
SupplementaryGroups=
ExecStart=/bin/bash -c while true; do /data/FLOW/scripts/atlas-flow-organize.sh; sleep 2; done

sftpgo.service:
No hay unidad systemd visible.
```

Comando:

```bash
ps -eo user,group,pid,ppid,cmd | grep -E 'sftpgo serve|run_ingest_watcher|atlas-flow-organize|flask --app app'
```

Resultado:

```text
atlas atlas 377707 377683 sftpgo serve
atlas atlas 3100118 1 /opt/atlas-lens/.venv/bin/python -c from app.ingest.watcher import run_ingest_watcher; run_ingest_watcher()
atlas atlas 3105492 1 /bin/bash -c while true; do /data/FLOW/scripts/atlas-flow-organize.sh; sleep 2; done
atlas atlas 3723395 1 /opt/atlas-lens/.venv/bin/python3 /opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
```

Proceso padre de SFTPGo:

```text
root  377683  1      /usr/bin/containerd-shim-runc-v2 ...
atlas 377707  377683 sftpgo serve
```

Conclusion:

- `atlas-lens.service`: usuario `atlas`, grupo primario efectivo `atlas`.
- FLOW watcher: usuario `atlas`, grupo primario efectivo `atlas`.
- FLOW organizer: usuario `atlas`, grupo primario efectivo `atlas`.
- SFTPGo: proceso real `atlas:atlas`, aunque lanzado bajo un `containerd-shim` root.

## 2. Identidad de atlas

Comandos solicitados:

```bash
id atlas
getent passwd atlas
getent group atlas
```

Resultados:

```text
uid=1000(atlas) gid=1000(atlas) groups=1000(atlas),24(cdrom),25(floppy),29(audio),30(dip),44(video),46(plugdev),100(users),101(netdev)
atlas:x:1000:1000:atlas,,,:/home/atlas:/bin/bash
atlas:x:1000:
```

## 3. Usuario real de SFTPGo y grupos

El proceso real `sftpgo serve` corre como:

```text
atlas atlas 377707 377683 sftpgo serve
```

No se encontro unidad `sftpgo.service` en systemd. La evidencia local apunta a SFTPGo ejecutandose como proceso/contenedor administrado por containerd, pero el proceso efectivo que ve el host es `atlas:atlas`.

Grupo compartido actual relevante:

- `atlas` es el grupo primario de `atlas`.
- SFTPGo, FLOW watcher, FLOW organizer y Flask corren como `atlas:atlas`.
- No hay necesidad tecnica de crear un grupo nuevo si se limita el acceso al modulo FLOW; el grupo `atlas` ya es compartido por todos los procesos que necesitan operar en FLOW.

## 4. Quien crea los directorios events/.../JPG

El script organizador actual es:

```bash
/data/FLOW/scripts/atlas-flow-organize.sh
```

Fragmento relevante:

```bash
FLOW="$BASE_ROOT/sftpgo/storage"
SOURCE="$FLOW/incoming/$CAMERA"
DEST="$FLOW/events/$DATE/$EVENT/$PHOTOGRAPHER/$CAMERA/$TYPE"
ARCHIVE="$FLOW/archive/$DATE/$CAMERA"
mkdir -p "$DEST" "$ARCHIVE"
cp -p "$FILE" "$DEST/$NAME"
mv "$FILE" "$ARCHIVE/$NAME"
```

La unidad `atlas-flow-organizer.service` lo ejecuta como `atlas`.

Sin embargo, los directorios existentes bajo `events` aparecen como `root:root`, lo que indica que fueron creados historicamente por un proceso root, por una ejecucion anterior del organizador bajo root, por una preparacion manual previa, o desde el lado que exporta el storage. No hay un proceso actual root de organizer en `ps`; el unico proceso relacionado actual que corre como root es el `containerd-shim` padre de SFTPGo, no `sftpgo serve` ni el organizador.

Conclusion operacional:

- El creador actual previsto por codigo/servicio es `atlas-flow-organizer.service` mediante `mkdir -p "$DEST"`.
- El owner real historico de los directorios existentes es `root:root`.
- La solucion debe corregir el arbol existente y asegurar herencia/mode para futuros directorios creados por `atlas`.

## 5. Permisos de directorios reales bajo events

Muestra de directorios:

```text
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events/2026
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events/2026/07
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events/2026/07/22
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/15/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/12/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG
```

Todos los directorios `JPG` reales listados:

```text
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/07/22/prueba3/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/07/23/prueba-asamblea/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/07/24/asamblea/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/07/24/prueba-transferencia/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/07/25/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/08/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/09/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/12/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/15/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW/ricardo/canon-r6/JPG
```

Resumen de directorios:

```text
54 root:root 755
8  root:root 775
```

Resumen de archivos JPG:

```text
79 -rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/13/sabado/ricardo/canon-r6/JPG
47 -rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/12/sabado/ricardo/canon-r6/JPG
44 -rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/15/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
22 -rw-r--r-- 644 atlas atlas /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
...
```

Conclusion:

- Los directorios se estan observando como `root:root`, mayoritariamente `755`.
- Los JPG son `atlas:atlas 644`.
- La falta de write en el directorio padre explica `source_unmovable`.

## 6. Variacion de propietarios/grupos

No se encontraron directorios bajo `events` con owner/grupo distinto a `root:root` en el resumen actual. Si hubo directorios mas antiguos `775`, siguen siendo `root:root`; el grupo no es compartido con `atlas`, por lo que `775 root:root` no ayuda al servicio.

Los archivos JPG si son `atlas:atlas`, coherente con SFTPGo/organizador preservando ownership de archivo mediante `cp -p`.

## 7. Grupo compartido apropiado

Grupo existente recomendado:

```text
atlas
```

Justificacion:

- `atlas-lens.service` corre como `atlas`.
- `atlas-flow.service` corre como `atlas`.
- `atlas-flow-organizer.service` corre como `atlas`.
- `sftpgo serve` corre como `atlas`.
- Los archivos JPG ya son `atlas:atlas`.

No se recomienda crear un grupo nuevo en primera opcion, porque ya existe un grupo comun exacto para los procesos implicados. Crear `atlas-flow` exigiria modificar membresias de usuario y reiniciar procesos para aplicar grupos suplementarios.

## 8. Analisis de solucion POSIX segura

La solucion POSIX segura debe resolver dos cosas:

1. Arbol existente: `atlas` debe poder desvincular/renombrar entradas desde los directorios `JPG`.
2. Directorios futuros: los nuevos directorios bajo `events` deben heredar grupo compartido y modo group-writable.

ACL esta descartado en este mount, por lo que el mecanismo POSIX disponible es:

- grupo compartido;
- bit setgid en directorios;
- permisos `2775` en directorios;
- umask `0002` o chmod controlado en el proceso que crea directorios.

Solo setgid no basta si el proceso creador usa umask `0022`: el grupo heredado seria correcto, pero el modo podria seguir siendo `755` y no dar escritura al grupo. Por eso la herencia futura necesita una de estas dos medidas:

- configurar `UMask=0002` en `atlas-flow-organizer.service`; o
- ajustar el script `atlas-flow-organize.sh` para crear/aplicar directorios group-writable (`install -d -m 2775` o `chmod g+rwx,g+s` sobre los directorios que crea).

Como el usuario pidio no modificar servicios en esta fase, esto queda como propuesta.

## 9. Solucion POSIX recomendada

### Grupo

Usar grupo existente:

```text
atlas
```

Usuarios/procesos que deben pertenecer:

- `atlas` ya pertenece al grupo `atlas`.
- SFTPGo, FLOW watcher, FLOW organizer y Flask corren como usuario `atlas`; no se requieren membresias nuevas.

### Directorios que cambiarian

Limitar cambios a:

```text
/data/FLOW/sftpgo/storage/events
```

y su contenido.

No tocar:

- `/data`
- `/data/FLOW`
- `/data/FLOW/sftpgo/storage/incoming`
- `/data/FLOW/sftpgo/storage/archive`
- `/data/FLOW/trash` salvo verificaciones; ya esta `atlas:atlas 750`.
- Proxmox/VirtioFS/mounts/discos.

### Permisos actuales

Ejemplos:

```text
events root:root 775
JPG dirs root:root 755
JPG files atlas:atlas 644
trash atlas:atlas 750
```

### Permisos propuestos

Para directorios bajo `events`:

```text
owner: conservar owner actual
group: atlas
mode: 2775
```

Para archivos bajo `events`:

```text
owner: conservar owner actual
group: atlas
mode: group read/write donde corresponda, sin ejecutar bits innecesarios
```

La parte critica para delete es directorio `rwx` para grupo, no el write del archivo.

Comandos propuestos, no ejecutados:

```bash
# 1. Cambiar solo el grupo del arbol events al grupo compartido existente.
chgrp -R atlas /data/FLOW/sftpgo/storage/events

# 2. Dar rwx al grupo solo en directorios, y activar setgid para herencia de grupo.
find /data/FLOW/sftpgo/storage/events -type d -exec chmod 2775 {} +

# 3. Opcional/recomendado para archivos existentes: permitir rw al grupo sin cambiar owner.
find /data/FLOW/sftpgo/storage/events -type f -exec chmod g+rw {} +
```

Para herencia futura, una de estas opciones:

Opcion A, service-level:

```ini
# atlas-flow-organizer.service
[Service]
UMask=0002
```

Opcion B, script-level:

```bash
mkdir -p "$DEST" "$ARCHIVE"
chmod g+rwx "$DEST" "$ARCHIVE"
chmod g+s "$DEST" "$ARCHIVE"
```

Mejor version script-level para padres intermedios creados por `mkdir -p`:

```bash
mkdir -p "$DEST" "$ARCHIVE"
find "$FLOW/events/$DATE" -type d -exec chmod 2775 {} +
find "$FLOW/archive/$DATE" -type d -exec chmod 2775 {} +
```

Debe evaluarse con cuidado para limitar el alcance por fecha y no tocar todo `/data`.

### Garantia para fotografias futuras

La combinacion necesaria es:

- `events` y subdirectorios con grupo `atlas`.
- setgid (`2xxx`) en directorios para que nuevos hijos hereden grupo `atlas`.
- `UMask=0002` en el organizador, o chmod controlado del script, para que los nuevos directorios tengan escritura de grupo.

Con eso:

- nuevos directorios quedan `atlas` como grupo;
- nuevos directorios quedan group-writable;
- `atlas-lens.service` puede retirar/mover JPG de sesiones eliminadas.

## 10. Impacto sobre SFTPGo

Impacto esperado bajo la evidencia actual:

- Bajo `events`, SFTPGo no parece ser el creador directo de la estructura final; el organizador mueve/copia desde `incoming` hacia `events`.
- SFTPGo corre como `atlas`, por lo que el grupo `atlas` no restringe su acceso.
- No se cambia `incoming`, donde SFTPGo recibe subidas.
- No se cambia configuracion de SFTPGo.

Riesgo:

- Si algun flujo externo espera `root:root` bajo `events`, cambiaria el grupo, no el owner. Es bajo impacto frente a cambiar owner recursivo.

## 11. Impacto sobre FLOW

Impacto esperado:

- `atlas-lens.service` podria mover fotografias desde `events` hacia `/data/FLOW/trash`.
- `atlas-flow-organizer.service` podria seguir creando estructura bajo `events`.
- `atlas-flow.service` watcher mantiene lectura.

Riesgo:

- Si no se ajusta umask o script, directorios futuros podrian volver a `755` aunque hereden grupo correcto.

## 12. Rollback exacto

Antes de aplicar la solucion, guardar snapshot de permisos:

```bash
find /data/FLOW/sftpgo/storage/events -printf '%M %m %u %g %p\n' > /opt/atlas-lens/docs/flow_events_permissions_before_posix_change.txt
```

Rollback minimo de grupo/modo si se adopta esta solucion:

```bash
# Revertir grupo a root en el arbol events.
chgrp -R root /data/FLOW/sftpgo/storage/events

# Revertir directorios al modo historico mas comun.
find /data/FLOW/sftpgo/storage/events -type d -exec chmod 755 {} +

# Restaurar manualmente directorios raiz que hoy estaban 775 si hace falta:
chmod 775 /data/FLOW/sftpgo/storage/events
chmod 775 /data/FLOW/sftpgo/storage/events/2026
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW/ricardo
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW/ricardo/canon-r6
chmod 775 /data/FLOW/sftpgo/storage/events/2026/07/22/prueba-FLOW/ricardo/canon-r6/JPG
```

Si se modifica `UMask` en systemd:

```bash
# eliminar la linea UMask=0002 o el drop-in correspondiente
systemctl daemon-reload
systemctl restart atlas-flow-organizer.service
```

No ejecutar rollback ni cambios sin aprobacion.

## 13. Riesgos

- `chmod 2775` en todos los directorios de `events` amplia escritura de grupo, aunque solo al grupo `atlas`.
- Si un proceso no deseado corre como `atlas`, tendria capacidad de modificar `events`; ese riesgo ya existe parcialmente porque los JPG son `atlas:atlas`.
- Sin corregir umask/script, la solucion puede no cubrir directorios futuros.
- Cambiar grupo recursivo bajo `events` es menos riesgoso que `chown -R`, pero sigue siendo un cambio operativo que debe hacerse con ventana controlada y snapshot previo.
- No debe usarse `chmod 777`, `chown -R` ni cambios sobre todo `/data`.

## 14. Comandos usados

Todos fueron de lectura:

```bash
systemctl show ...
systemctl cat ...
ps -eo ...
id atlas
getent passwd atlas
getent group atlas
find /data/FLOW/sftpgo/storage/events ...
stat -c ...
nl -ba /data/FLOW/scripts/atlas-flow-organize.sh
getent group root users netdev cdrom floppy audio dip video plugdev
```

## 15. Confirmacion de cero cambios

Durante este diagnostico:

- No se ejecuto `chmod`.
- No se ejecuto `chown`.
- No se ejecuto `chgrp`.
- No se crearon grupos.
- No se modificaron usuarios ni membresias.
- No se modifico SFTPGo.
- No se modificaron servicios.
- No se modifico Proxmox/VirtioFS/mounts/discos.
- No se movieron ni borraron fotografias.
- No se hizo deploy.
- No se hizo restart.
- No se hizo commit.
- No se hizo push.
