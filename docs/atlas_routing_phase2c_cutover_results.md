# ATLAS Routing Architecture - Fase 2C Cutover Results

Fecha de ejecucion: 2026-08-17 00:00-00:05 America/Guayaquil
Commit base verificado: `d48c274`
Resultado final: `CUTOVER EXITOSO`

## Backups creados

Backend ATLAS:

- `/etc/systemd/system/atlas-lens.service.pre-atlas-routing-20260816235644`
- `/root/atlas-lens-service.pre-atlas-routing-20260816235644.txt`

VPS Apache `109.199.100.104`:

- `/etc/apache2/sites-available/atlas.lavoceria.com.conf.pre-atlas-routing-20260816235644`
- `/etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf.pre-atlas-routing-20260816235644`
- `/root/apachectl-S.pre-atlas-routing-20260816235644.txt`
- `/root/apache2ctl-M.pre-atlas-routing-20260816235644.txt`
- `/root/apache-configtest.pre-atlas-routing-20260816235644.txt`

El backup de `apache configtest` previo contenia `Syntax OK`.

## Pruebas antes del cambio

- `.venv/bin/python -m unittest tests.test_atlas_routing_phase1`: `Ran 8 tests`, `OK`
- `.venv/bin/python -m unittest discover -s tests`: `Ran 304 tests`, `OK`

## Cambio systemd aplicado

Archivo modificado:

- `/etc/systemd/system/atlas-lens.service`

Cambio exacto:

```ini
Environment=ATLAS_URL_PREFIX=/lens
```

a:

```ini
Environment=ATLAS_URL_PREFIX=
```

Comandos operativos ejecutados:

- `systemctl daemon-reload`
- `systemctl restart atlas-lens.service`

Estado posterior:

- `systemctl is-active atlas-lens.service`: `active`
- La linea activa queda como `Environment=ATLAS_URL_PREFIX=`

## Verificacion backend directa

Desde el VPS hacia el backend real `http://100.79.10.122:5001`:

- `/`: `200 OK`
- `/flow/`: `200 OK`
- `/lens/`: `200 OK`
- `/lens/coverages/new`: `200 OK`
- `/dispatch/`: `200 OK`
- `/settings/`: `200 OK`

Desde el propio backend, `127.0.0.1:5001` tambien respondio `200 OK` para las mismas rutas.

Nota: `curl http://100.79.10.122:5001/...` desde el propio host backend no conecto, pero desde el VPS publico, que es el consumidor real de Apache, si conecto correctamente. El servicio Flask esta escuchando en `0.0.0.0:5001`.

## Cambios Apache aplicados

Archivos modificados en el VPS:

- `/etc/apache2/sites-available/atlas.lavoceria.com.conf`
- `/etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf`

Backend usado:

- `http://100.79.10.122:5001`

Directivas SSL preservadas:

- `SSLCertificateFile /etc/letsencrypt/live/atlas.lavoceria.com/fullchain.pem`
- `SSLCertificateKeyFile /etc/letsencrypt/live/atlas.lavoceria.com/privkey.pem`
- `Include /etc/letsencrypt/options-ssl-apache.conf`

Logs preservados:

- `ErrorLog ${APACHE_LOG_DIR}/atlas-error.log`
- `CustomLog ${APACHE_LOG_DIR}/atlas-access.log combined`

Validacion:

- `apachectl configtest`: `Syntax OK`
- `systemctl reload apache2`: ejecutado
- `systemctl is-active apache2`: `active`

## Verificacion publica canonica

Sobre `https://atlas.lavoceria.com`:

- `/`: `200 OK` - Dashboard ATLAS
- `/flow/`: `200 OK` - FLOW via Flask canonico
- `/lens/`: `200 OK` - LENS
- `/lens/coverages/new`: `200 OK` - nueva cobertura LENS
- `/dispatch/`: `200 OK` - DISPATCH
- `/settings/`: `200 OK` - SETTINGS
- `/static/css/main.css`: `200 OK` - assets Flask

## Verificacion legacy

Todas las rutas legacy probadas respondieron con `307 Temporary Redirect`:

- `/flow` -> `/flow/`
- `/lens/lens` -> `/lens/`
- `/lens/flow` -> `/flow/`
- `/lens/dispatch` -> `/dispatch/`
- `/lens/settings` -> `/settings/`
- `/lens/d/test-token` -> `/d/test-token`
- `/lens/static/css/main.css` -> `/static/css/main.css`

Se uso `307` para preservar metodo y body en flujos POST legacy.

## Puertos y servicios no modificados

No se detuvieron ni modificaron los servicios existentes en:

- `:3000` Next.js: seguia respondiendo `200 OK` directamente en `http://100.79.10.122:3000/`
- `:3100` FLOW anterior: seguia respondiendo `200 OK` directamente en `http://100.79.10.122:3100/`

El corte solo cambio la publicacion Apache hacia Flask canonico.

## Pruebas despues del cambio

- `git diff --check`: `OK`
- `.venv/bin/python -m unittest tests.test_atlas_routing_phase1`: `Ran 8 tests`, `OK`
- `.venv/bin/python -m unittest discover -s tests`: `Ran 304 tests`, `OK`

La suite emitio warnings conocidos de fixtures de imagen invalida y `ResourceWarning`, pero finalizo en `OK`.

## Estado Git

`git status --short` antes de crear este informe:

```text
?? atlas-convert-prototype.zip
?? atlas_convert_hif_fix_report.md
?? atlas_convert_install_report.md
?? docs/atlas_routing_phase1_commit.md
?? docs/atlas_routing_phase2a_cutover_plan.md
?? docs/atlas_routing_phase2b_preflight.md
```

Este informe agrega:

```text
?? docs/atlas_routing_phase2c_cutover_results.md
```

No se hizo commit ni push.

## Rollback disponible

Si hiciera falta revertir el corte:

Backend:

```bash
cp /etc/systemd/system/atlas-lens.service.pre-atlas-routing-20260816235644 /etc/systemd/system/atlas-lens.service
systemctl daemon-reload
systemctl restart atlas-lens.service
systemctl is-active atlas-lens.service
```

Apache:

```bash
cp /etc/apache2/sites-available/atlas.lavoceria.com.conf.pre-atlas-routing-20260816235644 /etc/apache2/sites-available/atlas.lavoceria.com.conf
cp /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf.pre-atlas-routing-20260816235644 /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf
apachectl configtest
systemctl reload apache2
systemctl is-active apache2
```

URLs a verificar tras rollback:

- `https://atlas.lavoceria.com/`
- `https://atlas.lavoceria.com/flow/`
- `https://atlas.lavoceria.com/lens`
- `https://atlas.lavoceria.com/lens/lens`
- `https://atlas.lavoceria.com/lens/coverages/new`

## Errores e incidencias

- No hubo rollback.
- No hubo fallo de `apachectl configtest`.
- No hubo fallo de reload Apache.
- No hubo fallo del servicio Flask tras el cambio de prefijo.
- La unica observacion fue que el backend no conecta a su propia IP Tailscale `100.79.10.122:5001`, pero Apache desde el VPS si conecta al backend real correctamente.

## Confirmaciones

- No se modifico DNS.
- No se modificaron certificados.
- No se modifico firewall.
- No se modifico Tailscale.
- No se modifico Docker.
- No se modifico Proxmox.
- No se detuvo ni modifico Next.js `:3000`.
- No se detuvo ni modifico FLOW anterior `:3100`.
- No se hizo deploy.
- No se hizo commit.
- No se hizo push.
