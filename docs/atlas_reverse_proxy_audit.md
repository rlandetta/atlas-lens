# ATLAS Reverse Proxy Audit - Fase 0B

Fecha: 2026-08-16

Repositorio auditado: `/opt/atlas-lens`

Dominio auditado: `https://atlas.lavoceria.com`

## 1. Topologia encontrada

Resultado: Caso B, identificacion parcial con evidencia suficiente del flujo publico, pero sin acceso directo al archivo de configuracion del proxy publico.

Topologia observada:

```text
Cliente publico
  -> DNS atlas.lavoceria.com
  -> 109.199.100.104
  -> host publico vmi2802983.contaboserver.net
  -> Apache/2.4.58 (Ubuntu) termina HTTPS y sirve el sitio raiz
  -> location/ruta publica /lens... proxya hacia ATLAS LENS
  -> atlas-apps:5001
  -> Flask/Werkzeug atlas-lens.service
```

La maquina local donde se ejecuto esta auditoria es `atlas-apps`. Tiene IP LAN `192.168.1.45/26` en `ens18`, gateway `192.168.1.1`, IP Tailscale `100.79.10.122/32` y varias redes Docker bridge. `systemd-detect-virt` reporta `container-other`; `qemu-guest-agent.service` esta activo, por lo que la maquina parece estar virtualizada/contenerizada en infraestructura tipo VM/LXC. Desde este entorno no hay acceso a `/etc/pve`, `pct` o `qm`, asi que no se pudo mapear Proxmox desde dentro.

## 2. DNS de `atlas.lavoceria.com`

Consulta A:

```text
atlas.lavoceria.com -> 109.199.100.104
```

Consulta AAAA:

```text
sin respuesta
```

Reverse DNS:

```text
109.199.100.104 -> vmi2802983.contaboserver.net.
```

La IP no pertenece a una interfaz local observada en `atlas-apps`. La IP publica de salida observada desde `atlas-apps` fue `181.112.9.124`, distinta de `109.199.100.104`.

## 3. IP publica

IP publica del dominio:

```text
109.199.100.104
```

Indicios:

- No parece estar detras de Cloudflare: no se observaron headers `CF-*` ni IPs Cloudflare.
- El reverse DNS apunta a Contabo: `vmi2802983.contaboserver.net`.
- La ruta desde `atlas-apps` hacia `109.199.100.104` sale via `192.168.1.1`, no por interfaz local directa.

## 4. Host que termina HTTPS

La terminacion TLS parece ocurrir en el host publico `109.199.100.104`, reverse DNS `vmi2802983.contaboserver.net`.

Certificado observado:

```text
subject=CN=atlas.lavoceria.com
issuer=C=US, O=Let's Encrypt, CN=YE2
notBefore=Jul 22 01:26:56 2026 GMT
notAfter=Oct 20 01:26:55 2026 GMT
SAN: DNS:atlas.lavoceria.com
```

## 5. Reverse proxy encontrado

Se encontro evidencia publica de Apache:

```text
GET https://atlas.lavoceria.com/
HTTP/1.1 200 OK
Server: Apache/2.4.58 (Ubuntu)
X-Powered-By: Next.js
```

Para rutas bajo `/lens`, la respuesta publica expone el backend Flask/Werkzeug:

```text
GET https://atlas.lavoceria.com/lens/
HTTP/1.1 200 OK
Server: Werkzeug/3.1.8 Python/3.13.5
```

Conclusion: el reverse proxy publico mas probable es Apache en el host `109.199.100.104`, con una regla tipo `ProxyPass` o equivalente para `/lens` hacia el backend `atlas-apps:5001`. El archivo exacto de Apache no esta en `atlas-apps` y no se pudo leer desde este entorno.

## 6. Software utilizado

Software publico observado:

- Apache/2.4.58 (Ubuntu) en `/`.
- Next.js detras de Apache para el sitio raiz.
- Flask/Werkzeug 3.1.8 Python 3.13.5 para `/lens`.
- Let's Encrypt para TLS.

Software local observado en `atlas-apps`:

- `atlas-lens.service` ejecutando Flask en puerto 5001.
- Docker activo.
- Portainer activo en 9443/8000.
- Tailscale activo, sin configuracion de `tailscale serve`.
- No hay servicios locales Nginx, Caddy, Traefik, HAProxy, Apache, cloudflared o FRP detectados como responsables del puerto 80/443.

## 7. Configuracion relevante

Servicio local:

```ini
# /etc/systemd/system/atlas-lens.service
[Service]
User=atlas
WorkingDirectory=/opt/atlas-lens
Environment=PYTHONUNBUFFERED=1
Environment=ATLAS_URL_PREFIX=/lens
ExecStart=/opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
Restart=always
RestartSec=3
```

Listeners locales relevantes:

```text
0.0.0.0:5001 -> flask pid 1793774
```

No se detectaron listeners locales en `:80` o `:443` dentro de `atlas-apps`.

Directorios de configuracion proxy no presentes en `atlas-apps`:

```text
/etc/nginx: no existe
/etc/caddy: no existe
/etc/traefik: no existe
/etc/haproxy: no existe
/etc/apache2: no existe
```

Docker en `atlas-apps`:

```text
atlas-flow-control   atlas-flow-control-flow-control       0.0.0.0:3100->3100/tcp
orbit-homepage       ghcr.io/gethomepage/homepage:latest   0.0.0.0:3000->3000/tcp
flow-sftpgo          drakkan/sftpgo:v2.7.4                 2022, 2121, 8082, 50000-50020 publicados
orbit-filebrowser    filebrowser/filebrowser:latest        0.0.0.0:8081->80/tcp
portainer            portainer/portainer-ce:lts            0.0.0.0:8000, 9443
```

No hay contenedor Docker local publicado en 80/443 ni nombres que indiquen Nginx Proxy Manager, Traefik, Caddy o proxy publico.

## 8. Maquina/VM/LXC donde vive

Backend ATLAS LENS:

```text
hostname: atlas-apps
IPv4 LAN: 192.168.1.45/26
gateway: 192.168.1.1
Tailscale: 100.79.10.122/32
virtualizacion detectada: container-other
```

Proxy publico:

```text
IP: 109.199.100.104
reverse DNS: vmi2802983.contaboserver.net
software observado: Apache/2.4.58 (Ubuntu)
```

No se pudo confirmar desde `atlas-apps` si `vmi2802983` es una VM externa en Contabo, una VM gestionada por el administrador, o una capa de hosting independiente. Debe revisarse directamente en esa maquina/proveedor.

## 9. Backend utilizado

Backend observado para ATLAS LENS:

```text
atlas-lens.service
/opt/atlas-lens/.venv/bin/flask --app app run --host 0.0.0.0 --port 5001
```

La evidencia indica que el proxy publico reenvia `/lens...` al backend Flask escuchando en `atlas-apps:5001`.

## 10. Puerto backend

Puerto backend:

```text
5001/tcp
```

Interfaz:

```text
0.0.0.0:5001
```

Esto permite acceso desde otras maquinas de la LAN/VPN si firewall/routing lo permiten. No se modifico firewall.

## 11. Tratamiento actual de `/lens`

La evidencia muestra que el proxy publico conserva `/lens` al reenviar hacia Flask.

Prueba:

```text
GET https://atlas.lavoceria.com/lens/
```

produce HTML identico a:

```text
GET http://127.0.0.1:5001/lens/
```

Y difiere de:

```text
GET http://127.0.0.1:5001/
```

Los links generados por Flask en la respuesta publica de `/lens/` incluyen el prefijo:

```text
href="/lens/static/css/main.css"
href="/lens/"
href="/lens/flow"
href="/lens/lens"
href="/lens/dispatch/"
href="/lens/settings/"
```

Conclusion tecnica: el proxy parece usar el caso A:

```text
recibe /lens/... y envia a Flask como /lens/...
```

No hay evidencia de que el proxy recorte `/lens` antes del backend. Tampoco hay evidencia de que el proxy use `SCRIPT_NAME`; el `SCRIPT_NAME=/lens` actual lo establece `UrlPrefixMiddleware` dentro de la app cuando recibe `PATH_INFO` con `/lens`.

## 12. Headers observados

Root publico:

```text
HTTP/1.1 200 OK
Server: Apache/2.4.58 (Ubuntu)
x-nextjs-cache: HIT
X-Powered-By: Next.js
Content-Type: text/html; charset=utf-8
```

LENS publico:

```text
HTTP/1.1 200 OK
Server: Werkzeug/3.1.8 Python/3.13.5
Content-Type: text/html; charset=utf-8
```

Static publico bajo LENS:

```text
GET https://atlas.lavoceria.com/lens/static/css/main.css
HTTP/1.1 200 OK
Server: Werkzeug/3.1.8 Python/3.13.5
Content-Type: text/css; charset=utf-8
```

Ruta `/d` publica probada con token inexistente:

```text
GET https://atlas.lavoceria.com/d/nonexistent-audit-token
HTTP/1.1 404 Not Found
Server: Apache/2.4.58 (Ubuntu)
X-Powered-By: Next.js
```

No se observaron headers:

- `CF-*`
- `Via`
- `X-Forwarded-Host`
- `X-Forwarded-Proto`
- `X-Forwarded-Prefix`

Esto no prueba que Apache no los envie al backend; solo indica que no aparecen en la respuesta publica.

## 13. Estado de `PUBLIC_BASE_URL`

En `app/config.py`:

```python
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
```

En `atlas-lens.service` no aparece configurado `PUBLIC_BASE_URL`.

La clase `DeliveryLinkService` construye enlaces asi:

```python
path = f"/d/{token}"
url = f"{PUBLIC_BASE_URL}{path}" if PUBLIC_BASE_URL else path
```

Estado observado:

- `PUBLIC_BASE_URL` no esta definido en `atlas-lens.service`.
- Si no se define en otro mecanismo no observado, los enlaces publicos se generan como `/d/<token>`.
- Actualmente `https://atlas.lavoceria.com/d/nonexistent-audit-token` no llega a Flask; responde Apache/Next.js 404.

Riesgo: los enlaces `/d/<token>` pueden no estar publicados correctamente por el proxy actual si Apache no proxya `/d` hacia ATLAS LENS.

## 14. Riesgos

1. Proxy publico fuera de `atlas-apps`.
   - La configuracion real de Apache vive en `109.199.100.104` / `vmi2802983.contaboserver.net`, no en este repositorio ni en esta maquina.
   - La migracion de rutas no puede completarse solo cambiando Flask/systemd.

2. `/lens` se pasa intacto al backend.
   - Hoy esto funciona por `ATLAS_URL_PREFIX=/lens` y `UrlPrefixMiddleware`.
   - Si se elimina `ATLAS_URL_PREFIX` antes de cambiar Apache, `/lens/...` dejara de mapear igual.

3. `/` ya esta ocupado por Next.js.
   - La arquitectura objetivo quiere publicar ATLAS en `/`.
   - Esto implica decidir si el sitio actual Next.js se retira, se mueve, o se integra como dashboard.

4. `/d/<token>` no parece proxyear a Flask.
   - Riesgo para descargas publicas de DISPATCH si los links se generan como `/d/<token>`.
   - Debe verificarse con un token real o configurar Apache para `/d/`.

5. `Server: Werkzeug` queda expuesto publicamente.
   - Indica que Apache probablemente esta pasando cabeceras del backend sin normalizarlas.
   - No es el principal problema funcional, pero revela detalles de runtime.

6. No se pudo auditar Proxmox desde `atlas-apps`.
   - Falta confirmar en la consola Proxmox si `atlas-apps` y `vmi2802983` estan relacionados o si el proxy vive fuera del cluster local.

## 15. Cambios necesarios para la futura arquitectura

En Apache del host publico `109.199.100.104`, preparar rutas canonicas hacia el backend ATLAS:

```text
/            -> ATLAS dashboard o frontend objetivo
/flow/       -> atlas-apps:5001/flow...
/lens/       -> atlas-apps:5001/lens...
/dispatch/   -> atlas-apps:5001/dispatch...
/settings/   -> atlas-apps:5001/settings...
/static/     -> atlas-apps:5001/static...
/d/          -> atlas-apps:5001/d...
```

Cuando se retire `ATLAS_URL_PREFIX=/lens`, Apache no debe seguir dependiendo de que Flask reciba todo bajo `/lens`. Para evitar doble prefijo o rutas rotas, coordinar tres capas en el mismo corte:

- configuracion Apache;
- variable `ATLAS_URL_PREFIX`;
- rutas Flask/compatibilidad legacy.

Compatibilidad legacy recomendada:

```text
/lens/lens       -> /lens/
/lens/flow/...   -> /flow/...
/lens/dispatch...-> /dispatch...
/lens/settings...-> /settings...
/lens/static/... -> /static/...
/lens/d/...      -> /d/...
```

La ruta `/lens/` es especial: hoy significa dashboard general; en la arquitectura objetivo debe significar listado LENS. El dashboard objetivo deberia vivir en `/`.

## 16. Pasos recomendados para la migracion

1. Acceder al host publico `109.199.100.104` / `vmi2802983.contaboserver.net`.
2. Localizar Apache:
   - `/etc/apache2/sites-enabled/`
   - `/etc/apache2/sites-available/`
   - certificados Let's Encrypt en `/etc/letsencrypt/`
   - reglas `ProxyPass`, `ProxyPassReverse`, `RewriteRule` y VirtualHost de `atlas.lavoceria.com`.
3. Copiar en una nota de migracion la configuracion actual sin secretos.
4. Verificar el backend usado por Apache:
   - IP privada/LAN;
   - Tailscale;
   - VPN;
   - NAT;
   - nombre DNS interno.
5. Agregar primero rutas proxy nuevas de compatibilidad sin retirar `/lens`.
6. Probar en staging o ventana controlada:
   - `/`
   - `/flow/`
   - `/lens/`
   - `/dispatch/`
   - `/settings/`
   - `/static/css/main.css`
   - `/d/<token>`
7. Ajustar Flask para arquitectura objetivo y compatibilidad legacy.
8. Cambiar `atlas-lens.service` solo cuando la app y Apache esten coordinados.
9. Reiniciar/reload controlado solo del servicio necesario en la ventana aprobada:
   - probablemente `apache2` en el host publico;
   - `atlas-lens.service` en `atlas-apps` si cambia `ATLAS_URL_PREFIX`.
10. Validar logs inmediatos de Apache y Flask.

## 17. Evidencias y comandos utilizados

Todos los comandos fueron de lectura/diagnostico. No se modificaron servicios, contenedores, configuracion ni codigo.

Git antes de la auditoria:

```text
git status --short
 M app/__init__.py
 M app/config.py
 M tests/test_lens_persistence_routes.py
?? docs/atlas_routing_audit.md
?? tests/test_url_prefix.py

git diff --cached --stat
sin salida
```

Identidad/red:

```text
hostname -> atlas-apps
hostname -f -> atlas-apps
systemd-detect-virt -> container-other
ip -o -4 addr show scope global
ip -o -6 addr show scope global
ip route show default
ip route get 109.199.100.104
```

Servicios y procesos:

```text
systemctl status atlas-lens.service --no-pager
systemctl list-units --type=service --all --no-pager
systemctl cat atlas-lens.service
ss -H -ltnp '( sport = :5001 or sport = :80 or sport = :443 )'
ps -eo pid,comm,args | grep -Ei 'nginx|caddy|traefik|haproxy|apache|cloudflared|frp|tailscale|funnel|proxy|npm|portainer|docker'
```

Docker:

```text
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
docker network ls
```

Tailscale:

```text
tailscale serve status
```

DNS/TLS/HTTP:

```text
dig +short atlas.lavoceria.com A
dig +short atlas.lavoceria.com AAAA
dig +short -x 109.199.100.104
openssl s_client -connect atlas.lavoceria.com:443 -servername atlas.lavoceria.com </dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
curl -sS -D - -o /tmp/atlas_public_root_probe.html https://atlas.lavoceria.com/
curl -sS -D - -o /tmp/atlas_public_lens_probe.html https://atlas.lavoceria.com/lens/
curl -sS -D - -o /tmp/atlas_public_lens_lens_probe.html https://atlas.lavoceria.com/lens/lens
curl -sS -D - -o /tmp/atlas_public_static_probe.css https://atlas.lavoceria.com/lens/static/css/main.css
curl -sS -D - -o /tmp/atlas_public_d_probe.html https://atlas.lavoceria.com/d/nonexistent-audit-token
curl -sS http://127.0.0.1:5001/lens/ -D - -o /tmp/atlas_local_lens_probe.html
curl -sS http://127.0.0.1:5001/ -D - -o /tmp/atlas_local_root_probe.html
diff -q /tmp/atlas_public_lens_probe.html /tmp/atlas_local_lens_probe.html
diff -q /tmp/atlas_public_lens_probe.html /tmp/atlas_local_root_probe.html
```

Inventario Flask:

```text
.venv/bin/flask --app app routes
```

Archivos leidos:

```text
app/config.py
app/__init__.py
app/dispatch/delivery_links.py
docs/atlas_routing_audit.md
```

## Observacion final

La pieza que falta no esta en `atlas-apps`: hay que entrar al host publico `109.199.100.104` / `vmi2802983.contaboserver.net` y revisar Apache. Hasta que esa configuracion se confirme, la migracion de rutas debe tratarse como un cambio coordinado entre el proxy publico y Flask, no como una modificacion local aislada.
