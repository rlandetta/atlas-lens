# ATLAS FLOW trash runtime ready

Fecha: 2026-08-17

## Alcance

Preparacion runtime exclusiva de `FLOW_TRASH_ROOT` antes del deploy de eliminacion segura de sesiones FLOW.

No se tocaron fotografias reales, no se movieron archivos de sesiones reales, no se modifico `instance/ingest.json`, no se modificaron Proxmox/VirtioFS/mounts/discos, no se hizo deploy, no se reinicio `atlas-lens.service`, no se hizo commit ni push.

## Comandos solicitados

`sudo` no esta instalado en este sistema:

```text
/bin/bash: line 1: sudo: command not found
```

Se uso `su` para ejecutar los mismos cambios aprobados con privilegios, sin incluir la contraseña en la linea de comando:

```bash
su -c 'mkdir -p /data/FLOW/trash'
su -c 'chown atlas:atlas /data/FLOW/trash'
su -c 'chmod 750 /data/FLOW/trash'
```

## Estado final de FLOW_TRASH_ROOT

Comando:

```bash
stat -c '%A %a %U %G %n' /data/FLOW/trash
```

Resultado:

```text
drwxr-x--- 750 atlas atlas /data/FLOW/trash
```

Conclusion:

- `/data/FLOW/trash` existe.
- Owner: `atlas`.
- Group: `atlas`.
- Permisos: `750`.

## Verificacion de no cambios en directorios no autorizados

Comando:

```bash
stat -c '%A %a %U %G %n' /data/FLOW /data/FLOW/sftpgo/storage/events
```

Resultado:

```text
drwxrwxr-x 775 root root /data/FLOW
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events
```

Conclusion: no se cambiaron permisos ni ownership de `/data/FLOW` ni de `/data/FLOW/sftpgo/storage/events`.

## Prueba de escritura como usuario atlas

Como `sudo -u atlas` no esta disponible por ausencia de `sudo`, se ejecuto el comando como `atlas` via `su` desde root:

```bash
su -c "su atlas -c 'touch /data/FLOW/trash/.atlas_write_test'"
su -c "su atlas -c 'test -w /data/FLOW/trash/.atlas_write_test'"
su -c "su atlas -c 'rm /data/FLOW/trash/.atlas_write_test'"
```

La prueba de escritura devolvio codigo `0`, por tanto el usuario `atlas` pudo crear y escribir el archivo temporal vacio dentro de `/data/FLOW/trash`.

## Confirmacion de limpieza del temporal

Comando:

```bash
test ! -e /data/FLOW/trash/.atlas_write_test
find /data/FLOW/trash -maxdepth 1 -mindepth 1 -printf '%f\n'
```

Resultado:

```text
TEST_FILE_ABSENT=0
```

`find` no devolvio contenido inmediato en `/data/FLOW/trash`.

Conclusion: el archivo temporal `.atlas_write_test` fue eliminado.

## Confirmacion de alcance

Durante esta preparacion:

- Se creo/preparo unicamente `/data/FLOW/trash`.
- No se toco `/data/FLOW/sftpgo/storage/events`.
- No se movieron ni borraron fotografias.
- No se modifico `instance/ingest.json`.
- No se cambiaron permisos de `/data/FLOW`.
- No se cambiaron permisos de `events`.
- No se modifico Proxmox.
- No se modifico VirtioFS.
- No se modificaron mounts ni discos.
- No se hizo deploy.
- No se reinicio `atlas-lens.service`.
- No se hizo commit.
- No se hizo push.

## Resultado

`FLOW_TRASH_ROOT=/data/FLOW/trash` queda preparado para el deploy de la eliminacion segura de sesiones FLOW.
