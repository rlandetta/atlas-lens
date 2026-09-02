# ATLAS CONVERT HIF fix report

Fecha: 2026-08-16T20:57:13-05:00

## Resultado

ATLAS CONVERT fue corregido para aceptar archivos HEIF con extension Canon `.HIF`, manteniendo soporte para `.HEIF` y `.HEIC`.

No se modifico LENS. No se modifico reverse proxy. No se cambio el puerto `8091`. No se reinstalaron servicios ATLAS.

## Ubicacion

- Instalacion modificada: `/opt/atlas-convert`
- Servicio reconstruido: `atlas-convert`
- Puerto: `8091`

## Archivos modificados

- `/opt/atlas-convert/app/__init__.py`
- `/opt/atlas-convert/app/templates/index.html`
- `/opt/atlas-convert/tests/test_convert.py`
- `/opt/atlas-convert/README.md`

## Cambios aplicados

Backend:

- `ALLOWED_EXTENSIONS` ahora admite:
  - `.hif`
  - `.heif`
  - `.heic`
- `/health` ahora reporta:
  - `hif`
  - `heif`
  - `heic`
- Los mensajes de validacion mencionan `HEIF/HEIC/HIF`.
- La validacion real de decodificacion sigue usando Pillow/pillow-heif:
  - primero se acepta la extension;
  - despues `Image.open(...).load()` debe poder abrir realmente el contenedor HEIF;
  - no se convierte basandose solo en la extension.

Interfaz:

- El selector de archivos ahora usa:

```html
accept=".HIF,.HEIF,.HEIC,.hif,.heif,.heic,image/heif,image/heic"
```

Pruebas:

- Se agrego cobertura para `521A0669.HIF`.
- Se agrego cobertura para confirmar `ALLOWED_EXTENSIONS == {".hif", ".heif", ".heic"}`.

Documentacion:

- `README.md` ahora documenta HIF/HEIF/HEIC.

## Reconstruccion

Comando ejecutado:

```bash
su -c "cd /opt/atlas-convert && docker compose up -d --build"
```

Resultado:

- Imagen `atlas-convert-atlas-convert` reconstruida.
- Contenedor `atlas-convert` recreado e iniciado.

## Estado del contenedor

Resultado de `docker ps`:

```text
NAMES           IMAGE                         STATUS         PORTS
atlas-convert   atlas-convert-atlas-convert   Up 2 minutes   0.0.0.0:8091->8091/tcp, [::]:8091->8091/tcp
```

Puerto `8091`:

```text
LISTEN 0 4096 0.0.0.0:8091 0.0.0.0:* users:(("docker-proxy",...))
LISTEN 0 4096 [::]:8091 [::]:* users:(("docker-proxy",...))
```

## Health check

Comando:

```bash
curl -fsS -w '\n%{http_code} %{content_type}\n' http://127.0.0.1:8091/health
```

Resultado:

```json
{"formats":["hif","heif","heic"],"ok":true,"outputs":["jpg","png"],"service":"atlas-convert"}
```

HTTP:

- `200 application/json`

## Prueba de decodificacion real

Se creo una muestra HEIF sintetica dentro del contenedor, se presento a la app con nombre `521A0669.HIF`, y se forzo:

1. Validacion de extension `.HIF`.
2. Apertura real con Pillow/pillow-heif.
3. Decodificacion con `image.load()`.
4. Re-encode a JPG.

Resultado del script temporal:

```text
{'ok': True, 'filename': '521A0669.HIF', 'decoded_mode': 'RGB', 'decoded_size': (16, 16), 'source_bytes': 466, 'jpeg_bytes': 288}
```

Tambien se probo el endpoint HTTP real:

```bash
curl -fsS -o /tmp/atlas_sample_converted.jpg -w '%{http_code} %{content_type} %{size_download}\n' \
  -F 'format=jpg' \
  -F 'quality=95' \
  -F 'files=@/tmp/atlas_sample.HIF;filename=521A0669.HIF;type=image/heif' \
  http://127.0.0.1:8091/convert
```

Resultado:

```text
200 image/jpeg 287
```

Cabecera del JPG generado:

```text
ff d8 ff e0 00 10 4a 46 49 46 00 01 01 00 00 01
```

## Canon HDR PQ

No habia una muestra Canon HDR PQ real disponible para validar `521A0669.HIF` especificamente contra el flujo de captura Canon HDR PQ.

Por tanto:

- Se confirmo que ATLAS CONVERT acepta `.HIF`.
- Se confirmo que no convierte solo por extension: decodifica realmente el contenedor HEIF.
- Se confirmo conversion correcta de una muestra HEIF sintetica con extension `.HIF`.
- No se afirma compatibilidad total con Canon HDR PQ real sin una muestra Canon HDR PQ para prueba.

Los logs del contenedor si muestran conversiones `.HIF` exitosas, incluyendo una peticion desde LAN, pero no se puede confirmar desde el log si ese archivo era Canon HDR PQ.

## Logs revisados

Comando:

```bash
su -c "docker logs --tail 160 atlas-convert"
```

Fragmentos relevantes:

```text
INFO:werkzeug:172.22.0.1 - - [17/Aug/2026 01:55:19] "GET /health HTTP/1.1" 200 -
INFO:atlas.convert:Converted file=521A0669.HIF output=jpg bytes=2733068
INFO:werkzeug:192.168.1.56 - - [17/Aug/2026 01:56:33] "POST /convert HTTP/1.1" 200 -
INFO:atlas.convert:Converted file=521A0669.HIF output=jpg bytes=287
INFO:werkzeug:172.22.0.1 - - [17/Aug/2026 01:56:33] "POST /convert HTTP/1.1" 200 -
```

No se observaron errores en los logs despues de la reconstruccion.

## Pruebas adicionales

Pruebas enfocadas dentro del contenedor:

```bash
su -c "docker exec -w /app atlas-convert python -c 'import runpy; ns=runpy.run_path(\"tests/test_convert.py\"); [ns[name]() for name in sorted(ns) if name.startswith(\"test_\")]; print(\"tests ok\")'"
```

Resultado:

```text
tests ok
```

Servicio principal:

- `curl http://127.0.0.1:8091/`: `200 text/html; charset=utf-8`
- `curl http://127.0.0.1:8091/health`: `200 application/json`

Servicios ATLAS verificados:

- LENS `http://127.0.0.1:5001/`: `200 text/html; charset=utf-8`
- FLOW `http://127.0.0.1:3100/`: `200 text/html; charset=utf-8`

## Estado de otros servicios ATLAS

Despues del fix:

- `atlas-convert`: running, `0.0.0.0:8091->8091/tcp`.
- `atlas-flow-control`: running, `0.0.0.0:3100->3100/tcp`.
- `orbit-homepage`: running healthy, `0.0.0.0:3000->3000/tcp`.
- `flow-sftpgo`: running, `2022`, `2121`, `8082`, `50000-50020`.
- `orbit-filebrowser`: running healthy, `0.0.0.0:8081->80/tcp`.
- `portainer`: running, `8000`, `9443`.

No se detecto afectacion a otros servicios ATLAS.

## Comandos utilizados

```bash
sed -n '1,260p' /opt/atlas-convert/app/__init__.py
sed -n '1,260p' /opt/atlas-convert/app/templates/index.html
sed -n '1,220p' /opt/atlas-convert/tests/test_convert.py
sed -n '1,220p' /opt/atlas-convert/README.md
su -c "cd /opt/atlas-convert && docker compose ps"
su -c "cd /opt/atlas-convert && docker compose up -d --build"
curl -fsS -w '\n%{http_code} %{content_type}\n' http://127.0.0.1:8091/health
curl -fsS -o /tmp/atlas_convert_hif_root.html -w '%{http_code} %{content_type}\n' http://127.0.0.1:8091/
su -c "docker ps --filter name=atlas-convert --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
su -c "docker logs --tail 80 atlas-convert"
su -c "docker cp /tmp/atlas_hif_decode_check.py atlas-convert:/tmp/atlas_hif_decode_check.py"
su -c "docker exec atlas-convert python /tmp/atlas_hif_decode_check.py"
su -c "docker exec -w /app atlas-convert python -c 'import app; from PIL import Image; Image.new(\"RGB\", (16, 16), (40, 120, 210)).save(\"/tmp/atlas_sample.HIF\", format=\"HEIF\")'"
su -c "docker cp atlas-convert:/tmp/atlas_sample.HIF /tmp/atlas_sample.HIF"
curl -fsS -o /tmp/atlas_sample_converted.jpg -w '%{http_code} %{content_type} %{size_download}\n' -F 'format=jpg' -F 'quality=95' -F 'files=@/tmp/atlas_sample.HIF;filename=521A0669.HIF;type=image/heif' http://127.0.0.1:8091/convert
od -An -tx1 -N16 /tmp/atlas_sample_converted.jpg
su -c "docker logs --tail 160 atlas-convert"
su -c "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
su -c "ss -ltnp | grep ':8091'"
curl -fsS -o /tmp/atlas_lens_after_hif.out -w '%{http_code} %{content_type}\n' http://127.0.0.1:5001/
curl -fsS -o /tmp/atlas_flow_after_hif.out -w '%{http_code} %{content_type}\n' http://127.0.0.1:3100/
date -Is
```

## Notas

- No se instalaron dependencias nuevas.
- No se cambio `requirements.txt`.
- No se creo commit Git.
- `pytest` no estaba instalado en el host; se ejecuto un runner simple dentro del contenedor para las pruebas enfocadas existentes.
- Se dejaron artefactos temporales de prueba en `/tmp`: `/tmp/atlas_hif_decode_check.py`, `/tmp/atlas_sample.HIF`, `/tmp/atlas_sample_converted.jpg`.
