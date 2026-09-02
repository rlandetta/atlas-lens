# DISPATCH detail compact analytics

## Scope

This update keeps the existing DISPATCH delivery-link workflow and extends the
download activity event payload. Existing tokens, package files, shipment
records, and legacy `country` / `city` fields remain compatible.

## Public delivery URL

The operator detail page displays and copies the client-facing delivery URL
using:

```text
https://ayampi.com/d/{token}
```

`PUBLIC_BASE_URL` remains available for existing internal delivery-link
generation behavior. `PUBLIC_DELIVERY_BASE_URL` controls the public URL shown to
operators and defaults to `https://ayampi.com`.

The detail view now rebuilds this URL from the token at render time. This avoids
showing a legacy `/d/{token}` value or an internal `PUBLIC_BASE_URL` value when a
link object was created or enriched before `PUBLIC_DELIVERY_BASE_URL` existed.

## IP resolution behind reverse proxy

Download routes resolve the client IP with this order:

1. Use `X-Forwarded-For` when `request.remote_addr` matches a trusted proxy.
2. Use `X-Real-IP` when `request.remote_addr` matches a trusted proxy and
   `X-Forwarded-For` is unavailable.
3. Fall back to `request.remote_addr`.

Headers are ignored when the direct peer is not trusted. Configure trusted
proxies with:

```text
DISPATCH_TRUSTED_PROXY_CIDRS=127.0.0.1/32,::1/128
```

Add the Apache reverse-proxy address or Docker bridge CIDR only when that
network is controlled by the deployment.

Expected Apache proxy headers:

```apache
ProxyPreserveHost On
ProxyAddHeaders On
RequestHeader set X-Forwarded-Proto "https"
RequestHeader set X-Forwarded-Host "ayampi.com"
RequestHeader set X-Real-IP expr=%{REMOTE_ADDR}
```

If Apache and Flask communicate through Docker or another private network, add
that proxy-side address or CIDR to `DISPATCH_TRUSTED_PROXY_CIDRS`. Without that,
DISPATCH intentionally ignores forwarded headers and sees only the proxy/private
address.

## Geolocation provider

Provider selected: `ipwho.is`.

Reasons:

- HTTPS endpoint.
- No API key required for the free endpoint.
- Server-side lookup is simple and does not require new infrastructure.
- Current documented free limit is 1,000 requests per day per client IP.

The provider is used through `app.dispatch.geolocation`, so routes and templates
do not depend on provider-specific response fields.

Environment variables:

```text
DISPATCH_IP_GEOLOCATION_PROVIDER=ipwhois
DISPATCH_IP_GEOLOCATION_CACHE_PATH=instance/dispatch_ip_geolocation_cache.json
DISPATCH_IP_GEOLOCATION_CACHE_TTL_DAYS=30
```

Set `DISPATCH_IP_GEOLOCATION_PROVIDER=none` to disable external lookups.

## Cache and failure behavior

Geolocation results are cached by IP for 30 days by default. Only globally
routable IP addresses are sent to the provider. Private, loopback, shared,
reserved, multicast, and invalid IP addresses are not sent.

External lookup failures never block downloads. Failed or unavailable lookups
store empty location fields and the download continues normally.

## Investigation result: "Ubicación no disponible"

Direct server-side provider check:

```text
curl https://ipwho.is/8.8.8.8
success=true, country=United States, region=California, city=San Jose
```

Internal resolver check outside the command sandbox:

```text
IpWhoIsGeolocationService.resolve("8.8.8.8")
country_code=US, country=United States, region=California, city=San Jose
```

Internal resolver check inside the command sandbox failed with DNS:

```text
URLError: Temporary failure in name resolution
```

That sandbox DNS failure does not reproduce outside the sandbox. The remaining
runtime cause for new downloads showing `Ubicación no disponible` is therefore
the effective client IP path:

- current configured `DISPATCH_TRUSTED_PROXY_CIDRS` is `127.0.0.1/32,::1/128`;
- `172.18.0.1` and `100.64.0.2` are not trusted by default;
- when Flask receives Apache/Docker/Tailscale/private IPs as `request.remote_addr`,
  DISPATCH ignores `X-Forwarded-For` and stores an empty location;
- when Apache sends `X-Forwarded-For` and its direct peer IP is trusted,
  DISPATCH resolves and stores city/country normally.

No full IP is written to permanent logs by this change.

## Privacy

DISPATCH does not store the full client IP in each download event. It stores a
SHA-256 hash for unique-client analytics and stores approximate geolocation
fields:

- country code
- country
- region
- city
- latitude / longitude when provided by the resolver

The UI uses these values only for distribution analytics and labels map markers
as approximate.

## User agent

Download events store parsed browser, operating system, and device category for
the main activity UI. The full User-Agent is kept in the event payload for
technical inspection, but it is not shown in the primary activity list.

## Final detail structure

The dispatch detail view uses this compact structure:

```text
HEADER DEL DESPACHO
RESUMEN OPERATIVO
ACCIONES DEL DESPACHO
Información del envío | Actividad de descargas
Entrega               | Cobertura
Nota de entrega
Fotografías
Información técnica
```

Information cards render as icon + label + value rows, not individual metric
boxes. The main detail grid uses `align-items: start`, so `Información del
envío` no longer stretches to match `Actividad de descargas`.

## Files modified

- `app/config.py`
- `app/__init__.py`
- `app/dispatch/geolocation.py`
- `app/dispatch/delivery_links.py`
- `app/routes/downloads.py`
- `app/routes/dispatch.py`
- `app/templates/dispatch/detail.html`
- `app/templates/downloads/landing.html`
- `app/templates/downloads/link_unavailable.html`
- `app/static/css/main.css`
- `tests/test_delivery_package_links.py`
- `docs/dispatch_detail_compact_analytics.md`

## Tests run

```text
.venv/bin/python -m unittest tests.test_delivery_package_links.DeliveryLinksAndRoutesTest.test_dispatch_detail_shows_official_ayampi_public_url tests.test_delivery_package_links.DeliveryLinksAndRoutesTest.test_dispatch_detail_shows_copy_link_and_delivery_metrics tests.test_delivery_package_links.DeliveryLinksAndRoutesTest.test_package_download_uses_trusted_proxy_ip_geolocation_and_user_agent
.venv/bin/python -m unittest tests.test_delivery_package_links tests.test_dispatch_routes
.venv/bin/python -m py_compile app/config.py app/__init__.py app/dispatch/geolocation.py app/dispatch/delivery_links.py app/routes/downloads.py app/routes/dispatch.py
```
