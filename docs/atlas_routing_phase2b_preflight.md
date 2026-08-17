# ATLAS Routing Architecture - Phase 2B VPS Preflight

Fecha: 2026-08-17

Estado: preflight real completado. No se aplico ningun cambio.

## 1. Hostname VPS

```text
hostname: vmi2802983
fqdn: vmi2802983.contaboserver.net
public IPv4: 109.199.100.104
public IPv6: 2a02:c207:2280:2983::1
OS: Ubuntu 24.04.3 LTS
```

Apache:

```text
Apache/2.4.58 (Ubuntu)
Server built: 2026-07-06T16:27:55
```

## 2. Archivo exacto VirtualHost

`apachectl -S` identifica:

```text
*:80  atlas.lavoceria.com  /etc/apache2/sites-enabled/atlas.lavoceria.com.conf:1
*:443 atlas.lavoceria.com  /etc/apache2/sites-enabled/atlas.lavoceria.com-le-ssl.conf:2
```

Symlinks reales:

```text
/etc/apache2/sites-enabled/atlas.lavoceria.com.conf
  -> /etc/apache2/sites-available/atlas.lavoceria.com.conf

/etc/apache2/sites-enabled/atlas.lavoceria.com-le-ssl.conf
  -> /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf
```

Archivo principal de corte HTTPS:

```text
/etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf
```

Archivo HTTP:

```text
/etc/apache2/sites-available/atlas.lavoceria.com.conf
```

## 3. Configuracion actual relevante

### HTTP `*:80`

Archivo: `/etc/apache2/sites-available/atlas.lavoceria.com.conf`

```apache
<VirtualHost *:80>
    ServerName atlas.lavoceria.com

    ProxyRequests Off
    ProxyPass / http://100.79.10.122:3000/
    ProxyPassReverse / http://100.79.10.122:3000/

    ErrorLog ${APACHE_LOG_DIR}/atlas-error.log
    CustomLog ${APACHE_LOG_DIR}/atlas-access.log combined
RewriteEngine on
RewriteCond %{SERVER_NAME} =atlas.lavoceria.com
RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI} [END,NE,R=permanent]
</VirtualHost>
```

Observacion: aunque contiene `ProxyPass /` a Next.js, tambien contiene regla de redireccion HTTPS permanente generada por Certbot.

### HTTPS `*:443`

Archivo: `/etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf`

```apache
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName atlas.lavoceria.com

    # FLOW
    RedirectMatch 302 ^/flow$ /flow/
    ProxyPass /flow/ http://100.79.10.122:3100/
    ProxyPassReverse /flow/ http://100.79.10.122:3100/
    ProxyRequests Off

    # LENS
    ProxyPass /lens http://100.79.10.122:5001/lens
    ProxyPassReverse /lens http://100.79.10.122:5001/lens

    # ATLAS Homepage actual
    ProxyPass / http://100.79.10.122:3000/
    ProxyPassReverse / http://100.79.10.122:3000/

    ErrorLog ${APACHE_LOG_DIR}/atlas-error.log
    CustomLog ${APACHE_LOG_DIR}/atlas-access.log combined

    SSLCertificateFile /etc/letsencrypt/live/atlas.lavoceria.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/atlas.lavoceria.com/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
</IfModule>
```

## 4. Backend exacto actual

Backends reales encontrados en Apache:

| Ruta publica actual | Backend actual |
|---|---|
| `/` | `http://100.79.10.122:3000/` |
| `/flow/` | `http://100.79.10.122:3100/` |
| `/lens` | `http://100.79.10.122:5001/lens` |

Probes desde el VPS:

```text
http://100.79.10.122:3000/ -> 200, X-Powered-By: Next.js
http://100.79.10.122:3100/ -> 200, Server: gunicorn
http://100.79.10.122:5001/lens/ -> 200, Server: Werkzeug/3.1.8 Python/3.13.5
http://100.79.10.122:5001/ -> 200, Server: Werkzeug/3.1.8 Python/3.13.5
```

Backend Flask real para ATLAS LENS:

```text
http://100.79.10.122:5001
```

## 5. Configuracion actual de `/lens`

```apache
ProxyPass /lens http://100.79.10.122:5001/lens
ProxyPassReverse /lens http://100.79.10.122:5001/lens
```

Esto confirma que Apache no usa `atlas-apps` como hostname. Usa la IP Tailscale:

```text
100.79.10.122
```

## 6. Configuracion actual de `/`

```apache
ProxyPass / http://100.79.10.122:3000/
ProxyPassReverse / http://100.79.10.122:3000/
```

`/` se sirve por proxy a Next.js en:

```text
http://100.79.10.122:3000/
```

No hay `DocumentRoot` en el VirtualHost de `atlas.lavoceria.com`; es proxy.

En el VPS no hay listener local `:3000`; el servicio Next.js vive en el host Tailscale/backend `100.79.10.122`.

Tambien existe un FLOW separado actual en:

```text
http://100.79.10.122:3100/
```

El corte propuesto abajo desplaza tanto el Next.js root `:3000` como el FLOW separado `:3100` para que la app Flask `:5001` sirva la arquitectura canonica completa. Si se desea conservar el FLOW `:3100` como modulo oficial, debe decidirse antes del corte y ajustar la propuesta.

## 7. Modulos Apache

`apache2ctl -M` confirma los modulos requeridos:

| Modulo | Estado |
|---|---|
| `proxy_module` | cargado |
| `proxy_http_module` | cargado |
| `rewrite_module` | cargado |
| `headers_module` | cargado |
| `ssl_module` | cargado |

Otros modulos relevantes observados:

```text
mpm_prefork_module
php_module
socache_shmcb_module
status_module
```

## 8. Rutas SSL

Directivas reales:

```apache
SSLCertificateFile /etc/letsencrypt/live/atlas.lavoceria.com/fullchain.pem
SSLCertificateKeyFile /etc/letsencrypt/live/atlas.lavoceria.com/privkey.pem
Include /etc/letsencrypt/options-ssl-apache.conf
```

No se leyo ni se mostro contenido de claves privadas.

## 9. Estado `apachectl configtest`

```text
Syntax OK
```

## 10. Propuesta VirtualHost final sin placeholders

### `/etc/apache2/sites-available/atlas.lavoceria.com.conf`

Se recomienda simplificar HTTP a redireccion HTTPS, retirando el proxy root innecesario en `:80`.

```apache
<VirtualHost *:80>
    ServerName atlas.lavoceria.com

    ErrorLog ${APACHE_LOG_DIR}/atlas-error.log
    CustomLog ${APACHE_LOG_DIR}/atlas-access.log combined

    RewriteEngine on
    RewriteCond %{SERVER_NAME} =atlas.lavoceria.com
    RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI} [END,NE,R=permanent]
</VirtualHost>
```

### `/etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf`

Esta propuesta usa exclusivamente el backend Flask real:

```text
http://100.79.10.122:5001
```

```apache
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName atlas.lavoceria.com

    ProxyRequests Off
    ProxyPreserveHost On
    RewriteEngine On

    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Host "atlas.lavoceria.com"

    # Legacy routing. Use 307 to preserve method and body for old POST URLs.
    RewriteRule ^/flow$ /flow/ [R=307,L]
    RewriteRule ^/lens/lens/?$ /lens/ [R=307,L]
    RewriteRule ^/lens/flow/?$ /flow/ [R=307,L]
    RewriteRule ^/lens/flow/(.*)$ /flow/$1 [R=307,L]
    RewriteRule ^/lens/dispatch/?$ /dispatch/ [R=307,L]
    RewriteRule ^/lens/dispatch/(.*)$ /dispatch/$1 [R=307,L]
    RewriteRule ^/lens/settings/?$ /settings/ [R=307,L]
    RewriteRule ^/lens/settings/(.*)$ /settings/$1 [R=307,L]
    RewriteRule ^/lens/d/(.*)$ /d/$1 [R=307,L]
    RewriteRule ^/lens/static/(.*)$ /static/$1 [R=307,L]

    # Canonical ATLAS Flask routes. Keep specific paths before root.
    ProxyPass /flow/ http://100.79.10.122:5001/flow/
    ProxyPassReverse /flow/ http://100.79.10.122:5001/flow/

    ProxyPass /lens/ http://100.79.10.122:5001/lens/
    ProxyPassReverse /lens/ http://100.79.10.122:5001/lens/

    ProxyPass /dispatch/ http://100.79.10.122:5001/dispatch/
    ProxyPassReverse /dispatch/ http://100.79.10.122:5001/dispatch/

    ProxyPass /settings/ http://100.79.10.122:5001/settings/
    ProxyPassReverse /settings/ http://100.79.10.122:5001/settings/

    ProxyPass /d/ http://100.79.10.122:5001/d/
    ProxyPassReverse /d/ http://100.79.10.122:5001/d/

    ProxyPass /static/ http://100.79.10.122:5001/static/
    ProxyPassReverse /static/ http://100.79.10.122:5001/static/

    ProxyPass / http://100.79.10.122:5001/
    ProxyPassReverse / http://100.79.10.122:5001/

    ErrorLog ${APACHE_LOG_DIR}/atlas-error.log
    CustomLog ${APACHE_LOG_DIR}/atlas-access.log combined

    SSLCertificateFile /etc/letsencrypt/live/atlas.lavoceria.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/atlas.lavoceria.com/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
</IfModule>
```

## 11. Plan exacto para desplazar Next.js de `/`

Actualmente `/` es:

```apache
ProxyPass / http://100.79.10.122:3000/
ProxyPassReverse / http://100.79.10.122:3000/
```

Para que `/` pase a Dashboard ATLAS:

1. Sustituir el root proxy `:3000` por `:5001`.
2. No detener el servicio Next.js durante el corte; solo dejar de enrutar `atlas.lavoceria.com/` hacia el.
3. Si se necesita conservar Next.js, crear posteriormente otro dominio o ruta dedicada. No puede seguir ocupando `/`.
4. Documentar que el backend `100.79.10.122:3000` queda sin trafico desde `atlas.lavoceria.com` despues del corte.

Decision requerida antes del corte:

```text
Aceptar que atlas.lavoceria.com/ deja de servir Next.js y pasa a Dashboard ATLAS Flask.
```

## 12. Comandos exactos de backup

No ejecutados en esta fase. Para el corte:

```bash
ssh root@109.199.100.104

timestamp=$(date +%Y%m%d%H%M%S)
cp /etc/apache2/sites-available/atlas.lavoceria.com.conf \
   /etc/apache2/sites-available/atlas.lavoceria.com.conf.pre-atlas-routing-$timestamp
cp /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf \
   /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf.pre-atlas-routing-$timestamp
apachectl -S > /root/apachectl-S.pre-atlas-routing-$timestamp.txt
apache2ctl -M > /root/apache2ctl-M.pre-atlas-routing-$timestamp.txt
apachectl configtest > /root/apache-configtest.pre-atlas-routing-$timestamp.txt 2>&1
```

En backend `100.79.10.122` / `atlas-apps`, tambien respaldar systemd antes del corte:

```bash
cp /etc/systemd/system/atlas-lens.service \
   /etc/systemd/system/atlas-lens.service.pre-atlas-routing-$timestamp
systemctl cat atlas-lens.service > /root/atlas-lens-service.pre-atlas-routing-$timestamp.txt
```

## 13. Comandos exactos de corte

No ejecutados en esta fase.

Orden recomendado:

```bash
# 1. Backend atlas-apps / 100.79.10.122
cd /opt/atlas-lens
git rev-parse --short HEAD
.venv/bin/python -m unittest discover -s tests

# Editar atlas-lens.service para dejar:
# Environment=ATLAS_URL_PREFIX=
systemctl daemon-reload
systemctl restart atlas-lens.service
curl -I http://100.79.10.122:5001/
curl -I http://100.79.10.122:5001/flow/
curl -I http://100.79.10.122:5001/lens/
curl -I http://100.79.10.122:5001/lens/coverages/new

# 2. VPS Apache 109.199.100.104
# Reemplazar los dos vhost con la propuesta validada.
apachectl configtest
systemctl reload apache2

# 3. Verificacion publica inmediata
curl -I https://atlas.lavoceria.com/
curl -I https://atlas.lavoceria.com/flow/
curl -I https://atlas.lavoceria.com/lens/
curl -I https://atlas.lavoceria.com/dispatch/
curl -I https://atlas.lavoceria.com/settings/
curl -I https://atlas.lavoceria.com/static/css/main.css
```

## 14. Comandos exactos de rollback

No ejecutados en esta fase.

```bash
# VPS Apache 109.199.100.104
cp /etc/apache2/sites-available/atlas.lavoceria.com.conf.pre-atlas-routing-$timestamp \
   /etc/apache2/sites-available/atlas.lavoceria.com.conf
cp /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf.pre-atlas-routing-$timestamp \
   /etc/apache2/sites-available/atlas.lavoceria.com-le-ssl.conf
apachectl configtest
systemctl reload apache2

# Backend atlas-apps / 100.79.10.122
cp /etc/systemd/system/atlas-lens.service.pre-atlas-routing-$timestamp \
   /etc/systemd/system/atlas-lens.service
systemctl daemon-reload
systemctl restart atlas-lens.service

# Rollback verification
curl -I https://atlas.lavoceria.com/
curl -I https://atlas.lavoceria.com/lens/
curl -I https://atlas.lavoceria.com/lens/flow
curl -I https://atlas.lavoceria.com/lens/lens
curl -I https://atlas.lavoceria.com/lens/dispatch/
curl -I https://atlas.lavoceria.com/lens/settings/
curl -I https://atlas.lavoceria.com/lens/static/css/main.css
```

## 15. Confirmacion de que no se aplico ningun cambio

Confirmado:

- No se edito Apache.
- No se ejecuto `sudoedit`.
- No se copio sobre archivos productivos.
- No se hizo reload de Apache.
- No se reinicio Apache.
- No se cambio systemd.
- No se cambio Flask.
- No se cambio `ATLAS_URL_PREFIX`.
- No se reinicio `atlas-lens.service`.
- No se tocaron DNS, certificados, firewall, Docker ni Proxmox.

Comandos ejecutados fueron solo lectura/diagnostico:

```text
hostname
apache2ctl -v
apachectl -S
apachectl configtest
apache2ctl -M
ls -la /etc/apache2/sites-enabled
ls -la /etc/apache2/sites-available
grep sobre configuracion Apache
readlink -f de vhosts
sed -n para leer vhosts
ss -ltnp
systemctl list-units --type=service --all --no-pager
curl -I a backends internos
```
