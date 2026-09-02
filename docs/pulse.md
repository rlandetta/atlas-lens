# ATLAS PULSE

PULSE es el módulo de Real-Time Event Intelligence de ATLAS. En esta primera etapa vive como módulo independiente de Flask en `/pulse/` y usa almacenamiento JSON con bloqueo de archivo, igual que los stores existentes de LENS y Settings.

## Configuración

- `PULSE_STORE_PATH`: ruta del store JSON de PULSE. Valor por defecto: `instance/pulse.json`.

## Alcance Inicial

- Normalización de señales para conectores RSS, web, medios, fuentes oficiales, Telegram, X, YouTube y futuras plataformas.
- Memoria `Signal -> Event` con deduplicación por hash o URL.
- Confidence Score basado en reglas, sin uso de IA costosa.
- X Budget Controller con presupuesto mensual de USD 10.00 y límite interno de USD 9.00.
- Dashboard operativo en `/pulse/` con datos demo separados cuando todavía no hay conectores configurados.
- Botón `Crear cobertura en NEXUS` implementado como puente hacia la creación de cobertura existente, porque NEXUS aún no está activo como módulo propio en este repositorio.

Las credenciales de conectores no deben guardarse en código ni exponerse al frontend o logs.
