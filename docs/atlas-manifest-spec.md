 # ATLAS LENS — atlas-manifest.json

## Objetivo

`atlas-manifest.json` es el archivo interno de cada cobertura.

Guarda:

- información de la cobertura
- fotografías
- captions
- orden editorial
- exportaciones
- entregas
- historial de cambios

No debe incluirse dentro del ZIP enviado a las agencias.

---

## Estructura general

```json
{
  "manifest_version": "1.0",
  "coverage": {},
  "photos": [],
  "exports": [],
  "delivery": [],
  "history": []
}

---

# 1. coverage

Información general de la cobertura.

Ejemplo:

```json
{
  "id": "cov_20260725_001",
  "title": "Convoy humanitario Imbabura",
  "slug": "Convoy-humanitario-Imbabura-EC",
  "date": "2026-07-25",
  "city": "Ibarra",
  "country": "Ecuador",
  "country_code": "EC",
  "agency": "Xinhua",
  "photographer": "Ricardo Landeta",
  "editor": "",
  "status": "draft",
  "created_at": "2026-07-25T22:30:00-05:00",
  "updated_at": "2026-07-25T22:30:00-05:00"
}
```
### Reglas

- `id` es el identificador único de la cobertura.
- `title` es el nombre visible para el usuario.
- `slug` es el nombre técnico utilizado para carpetas y archivos.
- `slug` se genera automáticamente.
- Los espacios del título se reemplazan por `-`.
- Al final del `slug` se agrega el código ISO 3166-1 alfa-2 del país.
- El código del país se obtiene automáticamente del campo `country`.
- Ejemplo:

```
Convoy humanitario Imbabura
↓
Convoy-humanitario-Imbabura-EC
```

- El nombre del archivo DOCX será exactamente el mismo que el `slug`.

Ejemplo:

```
Convoy-humanitario-Imbabura-EC.docx
```

- El archivo ZIP utilizará exactamente el mismo nombre.

Ejemplo:

```
Convoy-humanitario-Imbabura-EC.zip
```