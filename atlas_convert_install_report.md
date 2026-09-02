# ATLAS CONVERT installation report

Fecha: 2026-08-16T20:44:58-05:00

## Resultado general

ATLAS CONVERT fue instalado y probado como servicio independiente de LENS.

No se modifico codigo de LENS. No se modificaron reverse proxies, firewall, router, Nginx, Caddy, Traefik ni rutas publicas actuales de ATLAS.

## Ubicacion exacta de instalacion

- `/opt/atlas-convert`

El prototipo fue localizado en:

- `/opt/atlas-lens/atlas-convert-prototype.zip`

El contenido del ZIP venia dentro de una carpeta superior `atlas-convert/`; se extrajo quitando ese prefijo para dejar la aplicacion directamente dentro de `/opt/atlas-convert/`.

## Archivos instalados

- `/opt/atlas-convert/Dockerfile`
- `/opt/atlas-convert/README.md`
- `/opt/atlas-convert/app.py`
- `/opt/atlas-convert/app/__init__.py`
- `/opt/atlas-convert/app/templates/index.html`
- `/opt/atlas-convert/atlas_convert_report.md`
- `/opt/atlas-convert/docker-compose.yml`
- `/opt/atlas-convert/requirements.txt`
- `/opt/atlas-convert/tests/test_convert.py`

## Dockerfile revisado

El Dockerfile usa:

- Base: `python:3.12-slim`
- Workdir: `/app`
- Dependencias desde `requirements.txt`
- Puerto expuesto: `8091`
- Comando: `python app.py`

## Docker Compose revisado

`/opt/atlas-convert/docker-compose.yml` define:

- Servicio: `atlas-convert`
- `container_name`: `atlas-convert`
- `restart`: `unless-stopped`
- Puerto publicado: `8091:8091`
- Variables:
  - `CONVERT_MAX_FILES=20`
  - `CONVERT_MAX_UPLOAD_MB=200`
  - `CONVERT_JPEG_QUALITY=95`
  - `LOG_LEVEL=INFO`

Validacion `docker compose config`: OK.

## Nombre y estado del contenedor

- Contenedor: `atlas-convert`
- Imagen: `atlas-convert-atlas-convert`
- Estado: running
- Publicacion Docker: `0.0.0.0:8091->8091/tcp`, `[::]:8091->8091/tcp`

## Puerto

- Puerto configurado: `8091`
- Antes de instalar: libre.
- Despues de instalar: escuchando en IPv4 e IPv6 mediante `docker-proxy`.

Resultado `ss`:

```text
LISTEN 0 4096 0.0.0.0:8091 0.0.0.0:* users:(("docker-proxy",...))
LISTEN 0 4096 [::]:8091 [::]:* users:(("docker-proxy",...))
```

## Health check

Comando:

```bash
curl -fsS http://127.0.0.1:8091/health
```

Resultado:

```json
{"formats":["heic","heif"],"ok":true,"outputs":["jpg","png"],"service":"atlas-convert"}
```

HTTP:

- `200 application/json`

Cumple el requisito:

- `ok: true`
- `service: atlas-convert`

## Pruebas realizadas

### Pagina principal local

Comando:

```bash
curl -fsS -D /tmp/atlas_convert_root_headers.txt -o /tmp/atlas_convert_root.html -w '%{http_code} %{content_type}\n' http://127.0.0.1:8091/
```

Resultado:

- `200 text/html; charset=utf-8`

### Health local

Comando:

```bash
curl -fsS -w '\n%{http_code} %{content_type}\n' http://127.0.0.1:8091/health
```

Resultado:

- `200 application/json`
- `ok: true`
- `service: atlas-convert`

### Health por IP LAN

Comando:

```bash
curl --connect-timeout 5 -fsS -w '\n%{http_code} %{content_type}\n' http://192.168.1.45:8091/health
```

Resultado:

- `200 application/json`
- `ok: true`
- `service: atlas-convert`

### Health por IP Tailscale

Comando:

```bash
curl --connect-timeout 5 -fsS -w '\n%{http_code} %{content_type}\n' http://100.79.10.122:8091/health
```

Resultado:

- `200 application/json`
- `ok: true`
- `service: atlas-convert`

### Prueba de IP publica solicitada

Comando:

```bash
curl --connect-timeout 5 -fsS -w '\n%{http_code} %{content_type}\n' http://109.199.100.104:8091/health
```

Resultado:

```text
curl: (7) Failed to connect to 109.199.100.104 port 8091 after 179 ms: Could not connect to server
000
```

Conclusion:

- `109.199.100.104:8091` no fue accesible desde este servidor durante la prueba.
- No se hicieron cambios de red.
- Como `192.168.1.45:8091` y `100.79.10.122:8091` si responden, el servicio esta escuchando correctamente en el host.
- El bloqueo de `109.199.100.104:8091` probablemente esta fuera del contenedor: NAT/router/firewall externo, hairpin NAT no disponible, o politica de exposicion publica pendiente.

## IP local del servidor

Resultado de `hostname -I` con root:

```text
192.168.1.45
172.20.0.1
172.17.0.1
172.19.0.1
172.18.0.1
172.21.0.1
100.79.10.122
172.22.0.1
2800:370:ca:c6c0:be24:11ff:feff:ed1a
fdfc:4da6:f1db:2200:be24:11ff:feff:ed1a
2800:370:ca:c6c0:7f5:ad53:89f5:7ec8
fdfc:4da6:f1db:2200:daf4:bd47:5f9f:847e
fd7a:115c:a1e0::a533:a7b
```

IPs recomendadas:

- LAN: `192.168.1.45`
- Tailscale: `100.79.10.122`

## URL de prueba recomendada

Desde el propio servidor:

- `http://127.0.0.1:8091/`

Desde la red LAN:

- `http://192.168.1.45:8091/`

Desde Tailscale:

- `http://100.79.10.122:8091/`

La URL publica `http://109.199.100.104:8091/` no fue accesible en la prueba realizada.

## Firewall / NAT detectado

No se modificaron reglas.

Lectura de regla Docker para `8091`:

```text
-A DOCKER -d 172.22.0.2/32 ! -i br-8307e5658308 -o br-8307e5658308 -p tcp -m tcp --dport 8091 -j ACCEPT
```

Observaciones:

- Docker agrego la regla interna esperada para publicar el puerto del contenedor.
- `INPUT` estaba en politica `ACCEPT` en la inspeccion previa.
- El servicio responde por IP LAN y Tailscale.
- La IP publica `109.199.100.104:8091` no responde desde esta prueba; no se continuo con cambios de red.

## Estado de los demas servicios ATLAS

`docker ps` despues de instalar:

- `atlas-convert`: running, `0.0.0.0:8091->8091/tcp`.
- `atlas-flow-control`: running, `0.0.0.0:3100->3100/tcp`.
- `orbit-homepage`: running healthy, `0.0.0.0:3000->3000/tcp`.
- `flow-sftpgo`: running, `2022`, `2121`, `8082`, `50000-50020`.
- `orbit-filebrowser`: running healthy, `0.0.0.0:8081->80/tcp`.
- `portainer`: running, `8000`, `9443`.

`docker compose ls` despues de instalar:

- `atlas-convert`: running, `/opt/atlas-convert/docker-compose.yml`.
- `atlas-flow-control`: running, `/opt/atlas-flow-control/docker-compose.yml`.
- `flow`: running, `/data/compose/6/docker-compose.yml`.
- `orbit`: running, `/data/compose/1/docker-compose.yml`.
- `orbit-dashboard`: running, `/data/compose/2/docker-compose.yml`.

Pruebas HTTP adicionales:

- LENS en `http://127.0.0.1:5001/`: `200 text/html; charset=utf-8`.
- FLOW en `http://127.0.0.1:3100/`: `200 text/html; charset=utf-8`.

No se detecto afectacion a otros servicios ATLAS.

## Comandos utilizados

```bash
find /opt/atlas-lens -maxdepth 4 -type f -name 'atlas-convert-prototype.zip' -print
ls -la /opt /opt/atlas-convert
ss -ltnp
git status --short
python3 -m zipfile -l atlas-convert-prototype.zip
su -c "mkdir -p /opt/atlas-convert && chown atlas:atlas /opt/atlas-convert"
python3 - <<'PY'
# extractor ZIP con validacion y eliminacion del prefijo atlas-convert/
PY
find /opt/atlas-convert -maxdepth 3 -type f -print | sort
sed -n '1,220p' /opt/atlas-convert/docker-compose.yml
sed -n '1,220p' /opt/atlas-convert/Dockerfile
sed -n '1,240p' /opt/atlas-convert/app.py
sed -n '1,260p' /opt/atlas-convert/app/__init__.py
sed -n '1,220p' /opt/atlas-convert/README.md
sed -n '1,160p' /opt/atlas-convert/requirements.txt
sed -n '1,220p' /opt/atlas-convert/tests/test_convert.py
su -c "ss -ltnp"
su -c "cd /opt/atlas-convert && docker compose config"
su -c "cd /opt/atlas-convert && docker compose up -d --build"
curl -fsS -D /tmp/atlas_convert_root_headers.txt -o /tmp/atlas_convert_root.html -w '%{http_code} %{content_type}\n' http://127.0.0.1:8091/
curl -fsS -w '\n%{http_code} %{content_type}\n' http://127.0.0.1:8091/health
curl --connect-timeout 5 -fsS -w '\n%{http_code} %{content_type}\n' http://109.199.100.104:8091/health
su -c "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
su -c "hostname -I"
su -c "ss -ltnp | grep ':8091'"
curl --connect-timeout 5 -fsS -w '\n%{http_code} %{content_type}\n' http://192.168.1.45:8091/health
curl --connect-timeout 5 -fsS -w '\n%{http_code} %{content_type}\n' http://100.79.10.122:8091/health
curl -fsS -o /tmp/atlas_lens_5001_after.out -w '%{http_code} %{content_type}\n' http://127.0.0.1:5001/
curl --connect-timeout 5 -fsS -o /tmp/atlas_flow_3100_after.out -w '%{http_code} %{content_type}\n' http://127.0.0.1:3100/
su -c "/usr/sbin/iptables -S | grep 8091"
su -c "docker compose ls"
date -Is
```

## Notas

- `unzip` no estaba instalado; se uso `python3`/`zipfile`, disponible en el sistema, para listar y extraer el prototipo.
- El primer intento de escritura directa en `/opt/atlas-convert` fue bloqueado por el sandbox; se repitio la extraccion con permiso elevado acotado.
- No se creo commit Git.
- No se tocaron rutas publicas ni reverse proxy.
