# FLOW delete ACL and UX fix report

Fecha: 2026-08-17

## Resultado final

Se instalo correctamente el paquete `acl` en `atlas-apps`, pero la prueba segura sobre `/data` fallo porque el mount VirtioFS `atlas-data` no soporta aplicar ACL desde este sistema:

```text
setfacl: /data/.atlas_acl_test: Operation not supported
```

Por instruccion operativa, al fallar ACL sobre VirtioFS se detuvo el proceso antes de tocar `/data/FLOW/sftpgo/storage/events`. No se aplico alternativa de permisos. No se corrigio UX en esta pasada porque la fase de permisos debia completarse antes.

## 1. Instalacion de acl

Sistema operativo:

```text
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
ID=debian
VERSION_ID=13
```

Gestor de paquetes:

```text
/usr/bin/apt
apt 3.0.3 (amd64)
```

Comandos ejecutados:

```bash
su -c 'apt update'
su -c 'apt install -y acl'
```

Resultado:

```text
Installing:
  acl

Upgrading: 0, Installing: 1, Removing: 0, Not Upgrading: 26
Setting up acl (2.3.2-2+b1) ...
```

Verificacion:

```bash
command -v setfacl
command -v getfacl
setfacl --version
getfacl --version
```

Resultado:

```text
/usr/bin/setfacl
/usr/bin/getfacl
setfacl 2.3.2
getfacl 2.3.2
```

## 2. ACL antes

Antes de aplicar cualquier ACL sobre FLOW, se registraron permisos POSIX:

```bash
stat -c '%A %a %U %G %n' /data/FLOW/sftpgo/storage/events /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG /data/FLOW/trash
```

Resultado:

```text
drwxrwxr-x 775 root root /data/FLOW/sftpgo/storage/events
drwxr-xr-x 755 root root /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
drwxr-x--- 750 atlas atlas /data/FLOW/trash
```

Tras instalar `acl`, `getfacl` pudo leer el estado actual:

```bash
getfacl -p /data/FLOW/sftpgo/storage/events /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG /data/FLOW/trash
```

Resultado:

```text
# file: /data/FLOW/sftpgo/storage/events
# owner: root
# group: root
user::rwx
group::rwx
other::r-x

# file: /data/FLOW/sftpgo/storage/events/2026/08/17/pruebas-de-cobertura/ricardo-landeta/canon-r6/JPG
# owner: root
# group: root
user::rwx
group::r-x
other::r-x

# file: /data/FLOW/trash
# owner: atlas
# group: atlas
user::rwx
group::r-x
other::---
```

No habia ACL extendida efectiva para `atlas` sobre `events`.

## 3. Prueba ACL sobre VirtioFS

Para no tocar fotografias reales ni el arbol `events`, se creo un directorio temporal propio:

```bash
su -c 'mkdir -p /data/.atlas_acl_test && touch /data/.atlas_acl_test/probe'
```

Se intento aplicar ACL solo sobre ese temporal:

```bash
su -c 'setfacl -m u:atlas:rwx /data/.atlas_acl_test && setfacl -m u:atlas:rw /data/.atlas_acl_test/probe'
```

Resultado:

```text
setfacl: /data/.atlas_acl_test: Operation not supported
```

Conclusion:

- `setfacl` existe.
- `getfacl` existe.
- El filesystem/mount `/data` no acepta aplicar ACL desde este sistema.
- ACL no funciona correctamente sobre el VirtioFS `atlas-data` en esta configuracion.

El temporal fue eliminado:

```bash
su -c 'rm -rf /data/.atlas_acl_test'
test ! -e /data/.atlas_acl_test
```

Resultado:

```text
ACL_TEST_TEMP_ABSENT=0
```

En `test`, `0` significa exito: el temporal ya no existe.

## 4. ACL aplicada

No se aplico ACL sobre `/data/FLOW/sftpgo/storage/events`.

Motivo: ACL fallo sobre el temporal seguro en el mismo mount `/data` con `Operation not supported`.

## 5. Default ACL

No se configuro default ACL.

Motivo: ACL no funciona sobre el mount desde este sistema.

## 6. Permisos efectivos del usuario atlas

No hubo cambios sobre `events`, por lo que se mantiene el bloqueo diagnosticado:

- `atlas` puede leer JPG existentes.
- `atlas` puede escribir en `/data/FLOW/trash`.
- `atlas` no puede escribir en los directorios `JPG` source `root:root 755`.
- Por tanto `atlas` no puede retirar/mover fotografias desde `events` hacia `trash`.

## 7. Cambios UX

No se modifico UX en esta pasada.

Motivo: la instruccion indicaba continuar con UX "una vez comprobados los permisos"; como ACL no funciona sobre VirtioFS y no se aplicaron permisos, se detuvo el flujo antes de modificar codigo.

## 8. Tests

No se ejecutaron pruebas de codigo porque no hubo cambios de codigo en esta fase.

## 9. Git status

Estado observado:

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
?? docs/flow_delete_acl_ux_fix_report.md
?? docs/flow_delete_deploy_validation.md
?? docs/flow_delete_predeploy_validation.md
?? docs/flow_delete_real_failure_diagnosis.md
?? docs/flow_delete_runtime_permissions.md
?? docs/flow_session_persistence_audit.md
?? docs/flow_trash_runtime_ready.md
?? tests/test_flow_session_delete.py
```

## 10. Commit

No se creo commit.

## 11. Que falta exactamente para deploy

El deploy de la correccion de eliminacion segura sigue bloqueado por permisos source.

Opciones a decidir en una fase posterior:

1. Resolver soporte ACL desde el lado que exporta/controla `atlas-data`.
2. Si ACL no es viable en este VirtioFS, aprobar una alternativa limitada, por ejemplo grupo compartido o permisos POSIX puntuales solo sobre `/data/FLOW/sftpgo/storage/events`, sin `chmod 777`, sin `chown -R` y sin tocar todo `/data`.
3. Corregir UX del modal en codigo, separando `photos_in_use` de `filesystem_error`.
4. Ejecutar pruebas específicas y suite completa.
5. Hacer deploy/restart solo cuando se apruebe.

## 12. Rollback de ACL

No aplica rollback de ACL porque no se aplico ninguna ACL al arbol FLOW.

El paquete instalado podria retirarse si se decide volver al estado anterior de herramientas:

```bash
apt remove -y acl
```

No se recomienda hacerlo automaticamente porque `getfacl` ahora sirve para diagnostico y no modifica datos.

Rollback previsto si en una fase posterior se aplicara ACL desde un entorno que si la soporte:

```bash
setfacl -R -x u:atlas /data/FLOW/sftpgo/storage/events
setfacl -R -x d:u:atlas /data/FLOW/sftpgo/storage/events
```

Debe validarse antes/despues con `getfacl`.

## 13. Riesgos

- ACL no esta soportada por el mount VirtioFS actual desde este sistema.
- Aplicar una alternativa sin aprobacion podria ampliar permisos mas de lo necesario.
- Si solo se corrige UX, los borrados reales seguiran fallando con `filesystem_error/source_unmovable`.
- Si se fuerza la eliminacion logica sin mover originales, el watcher reingestaria los JPG.
- Cualquier solucion POSIX para directorios futuros debe cubrir la forma real en que SFTPGo/organizador crean directorios bajo `events`.

## 14. Confirmacion de alcance

Durante esta fase:

- Se instalo unicamente el paquete `acl`.
- Se creo y elimino unicamente `/data/.atlas_acl_test` para prueba segura.
- No se aplico ACL sobre `/data/FLOW/sftpgo/storage/events`.
- No se uso `chmod 777`.
- No se hizo `chown -R`.
- No se cambiaron permisos de todo `/data`.
- No se modifico Proxmox, VirtioFS, mounts ni discos.
- No se borraron ni movieron fotografias.
- No se modifico manualmente `instance/ingest.json`.
- No se hizo deploy.
- No se hizo restart.
- No se hizo push.
