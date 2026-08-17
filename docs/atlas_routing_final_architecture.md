# ATLAS Routing Final Architecture

Fecha de cutover: 2026-08-17
Commit base: `d48c274`
Estado: arquitectura publica canonica activa y validada manualmente en navegador.

## Arquitectura publica definitiva

El dominio publico `atlas.lavoceria.com` queda servido por Apache en `109.199.100.104`, proxyando hacia Flask en `100.79.10.122:5001`.

| Ruta publica | Destino |
| --- | --- |
| `/` | Dashboard ATLAS |
| `/flow/` | FLOW |
| `/lens/` | LENS |
| `/lens/coverages/...` | Coberturas LENS |
| `/dispatch/` | DISPATCH |
| `/settings/` | SETTINGS |
| `/d/...` | Entregas publicas |
| `/static/...` | Assets Flask |

## Backend y proxy

- Backend Flask: `100.79.10.122:5001`
- Proxy publico Apache: `109.199.100.104`
- Dominio: `atlas.lavoceria.com`
- `ATLAS_URL_PREFIX`: actualmente vacio (`Environment=ATLAS_URL_PREFIX=`)

## Compatibilidad legacy

Apache conserva compatibilidad temporal mediante redirects `307`, preservando metodo y body para rutas antiguas.

| Ruta legacy | Ruta canonica |
| --- | --- |
| `/flow` | `/flow/` |
| `/lens/lens` | `/lens/` |
| `/lens/flow...` | `/flow/...` |
| `/lens/dispatch...` | `/dispatch/...` |
| `/lens/settings...` | `/settings/...` |
| `/lens/d/...` | `/d/...` |
| `/lens/static/...` | `/static/...` |

La URL `/lens/` cambio de significado durante el corte: antes era el Dashboard por el prefijo global productivo; ahora es la entrada canonica de LENS.

## Servicios conservados fuera del routing publico

- Next.js `:3000` se conserva activo para rollback, pero queda fuera del routing publico de `atlas.lavoceria.com`.
- FLOW anterior `:3100` se conserva activo para rollback, pero queda fuera del routing publico de `atlas.lavoceria.com`.

No se eliminaron ni detuvieron esos servicios durante el corte.

## Backups de corte

Backend ATLAS:

- `/etc/systemd/system/atlas-lens.service.pre-atlas-routing-20260816235644`
- `/root/atlas-lens-service.pre-atlas-routing-20260816235644.txt`

VPS Apache:

- `/etc/apache2/sites-available/atlas.lavoceria.com.conf.pre-atlas-routing-20260816235644`
- `/etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf.pre-atlas-routing-20260816235644`
- `/root/apachectl-S.pre-atlas-routing-20260816235644.txt`
- `/root/apache2ctl-M.pre-atlas-routing-20260816235644.txt`
- `/root/apache-configtest.pre-atlas-routing-20260816235644.txt`

## Rollback resumido

Restaurar backend:

```bash
cp /etc/systemd/system/atlas-lens.service.pre-atlas-routing-20260816235644 /etc/systemd/system/atlas-lens.service
systemctl daemon-reload
systemctl restart atlas-lens.service
systemctl is-active atlas-lens.service
```

Restaurar Apache:

```bash
cp /etc/apache2/sites-available/atlas.lavoceria.com.conf.pre-atlas-routing-20260816235644 /etc/apache2/sites-available/atlas.lavoceria.com.conf
cp /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf.pre-atlas-routing-20260816235644 /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf
apachectl configtest
systemctl reload apache2
systemctl is-active apache2
```

Verificar tras rollback:

- `https://atlas.lavoceria.com/`
- `https://atlas.lavoceria.com/flow/`
- `https://atlas.lavoceria.com/lens`
- `https://atlas.lavoceria.com/lens/lens`
- `https://atlas.lavoceria.com/lens/coverages/new`

## Validacion

Validacion manual en navegador: correcta para los modulos principales.

Validacion automatizada final:

- `git diff --check`: OK
- `.venv/bin/python -m unittest tests.test_atlas_routing_phase1`: `Ran 8 tests`, OK
- `.venv/bin/python -m unittest discover -s tests`: `Ran 304 tests`, OK

La suite completa emitio warnings conocidos de fixtures de imagen invalida y `ResourceWarning`, pero finalizo correctamente.
