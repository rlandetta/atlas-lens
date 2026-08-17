# ATLAS Routing Architecture - Phase 2A Apache Cutover Plan

Fecha: 2026-08-17

Alcance: plan operativo de corte. No se aplicaron cambios.

Base confirmada:

- Dominio: `atlas.lavoceria.com`
- Proxy publico: Apache en `109.199.100.104`
- Backend Flask: `atlas-apps:5001`
- Produccion actual: `ATLAS_URL_PREFIX=/lens`
- Commit base routing: `d48c274`
- Flask soporta arquitectura dual y paso 304 tests.

## 1. Topologia actual

```text
Cliente publico
  -> https://atlas.lavoceria.com
  -> DNS A 109.199.100.104
  -> Apache/2.4.58 en host publico vmi2802983.contaboserver.net
  -> / sirve sitio Next.js actual
  -> /lens... se proxya sin recortar prefijo hacia atlas-apps:5001
  -> Flask atlas-lens.service con ATLAS_URL_PREFIX=/lens
```

Comportamiento publico actual:

| URL | Significado actual |
|---|---|
| `/` | Sitio Next.js actual |
| `/lens/` | Dashboard ATLAS servido por Flask |
| `/lens/flow` | FLOW |
| `/lens/lens` | LENS |
| `/lens/coverages/...` | Coberturas LENS |
| `/lens/dispatch/...` | DISPATCH |
| `/lens/settings/...` | SETTINGS |
| `/lens/d/...` | Entregas publicas |
| `/lens/static/...` | Assets Flask |

## 2. Topologia objetivo

```text
Cliente publico
  -> https://atlas.lavoceria.com
  -> DNS A 109.199.100.104
  -> Apache termina TLS y proxya rutas ATLAS hacia atlas-apps:5001
  -> Flask atlas-lens.service con ATLAS_URL_PREFIX=""
```

Arquitectura publica objetivo:

| URL | Significado objetivo |
|---|---|
| `/` | Dashboard ATLAS |
| `/flow/` | FLOW |
| `/lens/` | LENS |
| `/lens/coverages/...` | Coberturas LENS |
| `/dispatch/` | DISPATCH |
| `/settings/` | SETTINGS |
| `/d/...` | Entregas publicas |
| `/static/...` | Assets Flask |

## 3. VirtualHost Apache propuesto

Esta propuesta asume backend:

```text
http://atlas-apps:5001
```

Si el Apache actual usa otro nombre resoluble o IP interna para el mismo backend, conservar ese valor. No inventar otro backend.

> Nota: los paths de certificados deben ajustarse a la configuracion real de Let's Encrypt en el VPS. Normalmente serian `/etc/letsencrypt/live/atlas.lavoceria.com/fullchain.pem` y `privkey.pem`, pero deben verificarse antes del corte.

```apache
<VirtualHost *:80>
    ServerName atlas.lavoceria.com

    RewriteEngine On
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
</VirtualHost>

<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName atlas.lavoceria.com

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/atlas.lavoceria.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/atlas.lavoceria.com/privkey.pem

    ProxyPreserveHost On
    ProxyRequests Off

    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Host "atlas.lavoceria.com"

    RewriteEngine On

    # Legacy GET/POST-preserving redirects. Use 307 during the first cutover
    # window to preserve method and body for old POST URLs.
    RewriteRule ^/lens/lens/?$ /lens/ [R=307,L]
    RewriteRule ^/lens/flow/?$ /flow/ [R=307,L]
    RewriteRule ^/lens/flow/(.*)$ /flow/$1 [R=307,L]
    RewriteRule ^/lens/dispatch/?$ /dispatch/ [R=307,L]
    RewriteRule ^/lens/dispatch/(.*)$ /dispatch/$1 [R=307,L]
    RewriteRule ^/lens/settings/?$ /settings/ [R=307,L]
    RewriteRule ^/lens/settings/(.*)$ /settings/$1 [R=307,L]
    RewriteRule ^/lens/d/(.*)$ /d/$1 [R=307,L]
    RewriteRule ^/lens/static/(.*)$ /static/$1 [R=307,L]

    # Canonical ATLAS routes. Order matters: more specific routes first,
    # then the root catch-all.
    ProxyPass        /flow/     http://atlas-apps:5001/flow/
    ProxyPassReverse /flow/     http://atlas-apps:5001/flow/

    ProxyPass        /lens/     http://atlas-apps:5001/lens/
    ProxyPassReverse /lens/     http://atlas-apps:5001/lens/

    ProxyPass        /dispatch/ http://atlas-apps:5001/dispatch/
    ProxyPassReverse /dispatch/ http://atlas-apps:5001/dispatch/

    ProxyPass        /settings/ http://atlas-apps:5001/settings/
    ProxyPassReverse /settings/ http://atlas-apps:5001/settings/

    ProxyPass        /d/        http://atlas-apps:5001/d/
    ProxyPassReverse /d/        http://atlas-apps:5001/d/

    ProxyPass        /static/   http://atlas-apps:5001/static/
    ProxyPassReverse /static/   http://atlas-apps:5001/static/

    ProxyPass        /          http://atlas-apps:5001/
    ProxyPassReverse /          http://atlas-apps:5001/

    ErrorLog ${APACHE_LOG_DIR}/atlas_lavoceria_error.log
    CustomLog ${APACHE_LOG_DIR}/atlas_lavoceria_access.log combined
</VirtualHost>
</IfModule>
```

### Recommended hardening after functional cutover

The public audit showed `Server: Werkzeug/3.1.8 Python/3.13.5` for Flask responses. After the routing cutover is stable, replace the Flask development server with a production WSGI server such as Gunicorn or uWSGI behind Apache. This should be a separate operational change, not bundled into the routing cutover.

## 4. Reglas legacy

Temporary legacy behavior:

| Legacy | Objetivo | Metodo |
|---|---|---|
| `/lens/lens` | `/lens/` | `307` |
| `/lens/flow` | `/flow/` | `307` |
| `/lens/flow/...` | `/flow/...` | `307` |
| `/lens/dispatch` | `/dispatch/` | `307` |
| `/lens/dispatch/...` | `/dispatch/...` | `307` |
| `/lens/settings` | `/settings/` | `307` |
| `/lens/settings/...` | `/settings/...` | `307` |
| `/lens/d/...` | `/d/...` | `307` |
| `/lens/static/...` | `/static/...` | `307` |

No redirect is needed for `/lens/coverages/...` because it is already canonical in the target architecture.

Important semantic change:

```text
/lens/
```

currently means Dashboard because Flask is mounted under the global `/lens` prefix. After cutover, `/lens/` means LENS. The old Dashboard-at-`/lens/` behavior cannot be preserved at the same URL while also making `/lens/` the LENS module. After cutover, Dashboard is `/`.

## 5. Estrategia POST

Do not use `301` or `302` for legacy POST routes. Use `307` during the initial cutover because it preserves method and body and is less cache-sticky than `308`.

POST legacy routes covered by `307` rewrite rules:

| Flow | Legacy URL | Target |
|---|---|---|
| FLOW -> LENS | `/lens/flow/sessions/<id>/lens/open` | `/flow/sessions/<id>/lens/open` |
| DISPATCH create/edit/actions | `/lens/dispatch/...` | `/dispatch/...` |
| SETTINGS create/edit/delete | `/lens/settings/...` | `/settings/...` |

POST routes that remain directly canonical:

| Flow | Canonical URL |
|---|---|
| delete coverage | `/lens/coverages/<coverage_id>/delete` |
| caption autosave | `/lens/coverages/<coverage_id>/photos/<photo_id>/caption` |
| upload photo | `/lens/coverages/<coverage_id>/photos` |
| delete photo | `/lens/coverages/<coverage_id>/photos/<photo_id>/delete` |
| IA narration | `/lens/coverages/<coverage_id>/photos/<photo_id>/generate-narration` |
| IA context update | `/lens/coverages/<coverage_id>/ai-context` |
| export DOCX | `/lens/coverages/<coverage_id>/exports` |

Because `/lens/coverages/...` stays canonical, it should be proxied directly, not redirected.

Recommendation: keep `307` for one or more validation windows. Consider `308` only after old clients and caches are known safe.

## 6. Orden exacto de corte

The safest order is to stage reversible files first, then flip the Flask prefix and Apache proxy in one short window.

1. Confirm preconditions:
   - Backend repo on `atlas-apps` is at or includes commit `d48c274`.
   - `.venv/bin/python -m unittest discover -s tests` passes on backend.
   - Apache admin access to `109.199.100.104` is available.
   - Current Apache vhost path is known.
   - Current `atlas-lens.service` content is backed up.
2. On VPS, backup Apache:
   - copy enabled vhost file;
   - save `apachectl -S`;
   - save `apache2ctl -M`;
   - save current config test output.
3. On backend, backup service file:
   - copy `/etc/systemd/system/atlas-lens.service`;
   - capture `systemctl cat atlas-lens.service`;
   - capture `systemctl status atlas-lens.service --no-pager`.
4. Prepare Apache new vhost in a temporary file, not enabled yet.
5. Validate Apache syntax:
   - `apachectl configtest`
6. Prepare service change but do not restart yet:
   - remove `Environment=ATLAS_URL_PREFIX=/lens`, or change it to `Environment=ATLAS_URL_PREFIX=`
   - run `systemctl daemon-reload`
7. Start cutover window.
8. Restart backend service:
   - `systemctl restart atlas-lens.service`
   - verify backend responds without prefix:
     - `curl -I http://atlas-apps:5001/`
     - `curl -I http://atlas-apps:5001/lens/`
     - `curl -I http://atlas-apps:5001/lens/coverages/new`
9. Enable/apply Apache vhost changes.
10. Reload Apache gracefully:
    - `systemctl reload apache2`
11. Run immediate public checks over HTTPS.
12. If critical checks fail, execute rollback immediately.

Rationale:

- Restart Flask after prefix removal before Apache reload so backend is ready for canonical paths.
- Apache reload is graceful and should be faster than a full restart.
- Do not leave Apache pointing canonical root to a backend still using `ATLAS_URL_PREFIX=/lens`.

## 7. Rollback

Rollback target: restore the previous public behavior under `/lens/...`.

1. Restore previous Apache vhost from backup.
2. Validate:
   - `apachectl configtest`
3. Reload Apache:
   - `systemctl reload apache2`
4. Restore service file:
   - `Environment=ATLAS_URL_PREFIX=/lens`
5. Reload systemd:
   - `systemctl daemon-reload`
6. Restart Flask:
   - `systemctl restart atlas-lens.service`
7. Verify rollback URLs:
   - `/lens/`
   - `/lens/flow`
   - `/lens/lens`
   - `/lens/coverages/new`
   - `/lens/dispatch/`
   - `/lens/settings/`
   - `/lens/d/<known_token>`
   - `/lens/static/css/main.css`
8. Review logs:
   - Apache error log
   - Apache access log
   - `journalctl -u atlas-lens.service -n 100 --no-pager`

Expected rollback time: 2 to 5 minutes if backups and shell access are ready.

## 8. Checklist de verificacion posterior al corte

Run over public HTTPS:

| Check | Expected |
|---|---|
| `GET /` | Dashboard ATLAS |
| `GET /flow/` | FLOW |
| `GET /lens/` | LENS |
| `GET /lens/coverages/new` | New coverage form |
| Create coverage | POST succeeds and redirects to `/lens/coverages/<id>` or compatible detail |
| `GET /lens/coverages/<id>` | Detail page |
| Edit coverage | POST preserves body and persists |
| Delete coverage | POST preserves body and deletes |
| Caption autosave | JSON POST succeeds |
| Upload photo | JSON/FormData upload succeeds |
| Delete photo | JSON POST succeeds |
| IA narration | POST succeeds or returns expected configured AI response |
| DOCX export | POST succeeds |
| `GET /dispatch/` | DISPATCH |
| Create DISPATCH | POST succeeds |
| `GET /settings/` | SETTINGS |
| SETTINGS channel form/action | GET/POST succeeds |
| `GET /d/<token>` | Public delivery landing |
| `GET /static/css/main.css` | CSS loads |

Legacy checks:

| Legacy | Expected |
|---|---|
| `/lens/lens` | 307 to `/lens/` |
| `/lens/flow` | 307 to `/flow/` |
| `/lens/dispatch` | 307 to `/dispatch/` |
| `/lens/settings` | 307 to `/settings/` |
| `/lens/d/<token>` | 307 to `/d/<token>` |
| `/lens/static/css/main.css` | 307 to `/static/css/main.css` |
| `/lens/coverages/<id>` | 200 direct canonical LENS coverage |

## 9. Riesgos especiales

| Risk | Detail | Mitigation |
|---|---|---|
| Next.js currently owns `/` | Root currently returns Next.js. Cutover gives `/` to Flask Dashboard. | Decide before cutover whether Next.js is retired, moved to another path/subdomain, or backed up only. |
| `/lens/` changes meaning | Today it is Dashboard; target is LENS. | Communicate change. Dashboard becomes `/`; both meanings cannot coexist at `/lens/`. |
| `/d/<token>` public exposure | Existing links may be `/lens/d/...`; target is `/d/...`. | Keep 307 from `/lens/d/...` to `/d/...`; verify `PUBLIC_BASE_URL`. |
| Werkzeug exposed | Current backend leaks `Server: Werkzeug`. | Plan separate WSGI hardening after routing cutover. |
| `PUBLIC_BASE_URL` | If set to include `/lens`, new delivery links may keep old prefix. | Audit environment and set base URL to `https://atlas.lavoceria.com` without `/lens` during cutover if configured. |
| Slash final | Canonical module roots use `/flow/`, `/lens/`, `/dispatch/`, `/settings/`. | Keep redirects/aliases and test both slash/no-slash variants. |
| 308 cache | Permanent redirects can be cached aggressively. | Use 307 initially; revisit 308 after validation period. |
| Let's Encrypt | Certificate already observed valid but paths must match actual Apache config. | Do not change certificate files; reuse existing SSL directives. |
| ProxyPass order | Root `/` catches everything if placed first. | Put specific `ProxyPass` rules before `/`; keep legacy rewrites before proxying. |
| Apache module availability | `proxy`, `proxy_http`, `rewrite`, `headers`, `ssl` are required. | Confirm via `apache2ctl -M` before cutover. |

## 10. Tiempo estimado de indisponibilidad

Estimated user-visible disruption:

```text
1 to 3 minutes
```

Operational window recommendation:

```text
15 to 30 minutes
```

This includes validation, rollback readiness, and log review. If service restart or Apache reload fails, rollback should be possible in approximately 2 to 5 minutes.

## 11. Precondiciones antes de ejecutar

- Commit `d48c274` deployed on `/opt/atlas-lens`.
- Working tree clean or known non-routing files documented.
- Full test suite passing on backend.
- SSH/root or sudo access to `109.199.100.104`.
- SSH/root or sudo access to `atlas-apps`.
- Exact Apache vhost file identified.
- Existing SSL directives and certificate paths identified.
- Current Apache config backed up.
- Current `atlas-lens.service` backed up.
- Known delivery token available for `/d/<token>` validation.
- Decision made about current Next.js root site.
- Rollback operator present and reachable.

## 12. Comandos que habria que ejecutar

These commands are proposed only. They were not executed in this planning task.

On backend `atlas-apps`:

```bash
cd /opt/atlas-lens
git rev-parse --short HEAD
.venv/bin/python -m unittest discover -s tests
sudo cp /etc/systemd/system/atlas-lens.service /etc/systemd/system/atlas-lens.service.pre-routing-cutover
sudo systemctl cat atlas-lens.service
sudo sed -i 's/^Environment=ATLAS_URL_PREFIX=\\/lens$/Environment=ATLAS_URL_PREFIX=/' /etc/systemd/system/atlas-lens.service
sudo systemctl daemon-reload
sudo systemctl restart atlas-lens.service
curl -I http://atlas-apps:5001/
curl -I http://atlas-apps:5001/lens/
curl -I http://atlas-apps:5001/lens/coverages/new
```

On Apache VPS `109.199.100.104`:

```bash
sudo apachectl -S
sudo apache2ctl -M
sudo cp /path/to/current-vhost.conf /path/to/current-vhost.conf.pre-routing-cutover
sudoedit /path/to/current-vhost.conf
sudo apachectl configtest
sudo systemctl reload apache2
curl -I https://atlas.lavoceria.com/
curl -I https://atlas.lavoceria.com/flow/
curl -I https://atlas.lavoceria.com/lens/
curl -I https://atlas.lavoceria.com/dispatch/
curl -I https://atlas.lavoceria.com/settings/
curl -I https://atlas.lavoceria.com/static/css/main.css
```

Rollback commands:

```bash
# Apache VPS
sudo cp /path/to/current-vhost.conf.pre-routing-cutover /path/to/current-vhost.conf
sudo apachectl configtest
sudo systemctl reload apache2

# Backend
sudo cp /etc/systemd/system/atlas-lens.service.pre-routing-cutover /etc/systemd/system/atlas-lens.service
sudo systemctl daemon-reload
sudo systemctl restart atlas-lens.service
```

## 13. Que NO tocar

Do not touch during this cutover unless explicitly approved:

- DNS records.
- Let's Encrypt certificate issuance/renewal.
- Firewall rules.
- Docker or Proxmox.
- Database or persistent LENS media.
- Application code.
- Git history.
- Non-ATLAS Apache sites, except where the current root Next.js vhost must be intentionally displaced.

## 14. Decision sobre el sitio Next.js en `/`

The current root `/` is served by Next.js. The target architecture requires `/` to be Dashboard ATLAS from Flask.

Decision required before execution:

```text
Move root ownership from Next.js to ATLAS Flask Dashboard.
```

Options for the existing Next.js site:

1. Retire it from `atlas.lavoceria.com/`.
2. Move it to another hostname, such as `home.atlas.lavoceria.com`, if DNS/proxy support is desired.
3. Move it to a temporary path only if its routing and assets support a base path.
4. Keep a backup of the current Apache config and restore via rollback if ATLAS cutover fails.

Do not attempt to keep both Next.js root and Flask Dashboard root at `/`; they conflict by definition.
