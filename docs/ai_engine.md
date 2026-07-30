# Motor de IA de ATLAS LENS

## IA estacionada

La IA queda desactivada por defecto para mantener LENS como flujo manual estable y sin costos de API o hardware local.

Configuración activa por defecto:

- `AI_ENABLED=false`
- `AI_PROVIDER=mock`

Mientras `AI_ENABLED=false`:

- no se muestra el botón `Generar con IA`;
- no se muestra `Contexto de IA`;
- no se expone generación al usuario;
- no se ejecuta `MockProvider`;
- no se requieren API keys;
- no hay llamadas externas ni costo operativo.

La arquitectura permanece conservada como código inactivo para una futura activación controlada. Para reactivarla en el futuro, configurar `AI_ENABLED=true`, mantener `AI_PROVIDER=mock` o registrar otro proveedor en `AIService`, y validar nuevamente el flujo editorial antes de exponerlo a usuarios.

## Arquitectura

El motor vive en `app/ai` y está separado de rutas, templates, JavaScript y plantillas editoriales. La IA solo genera `Narración`; el caption final sigue siendo construido por la plantilla editorial existente.

Componentes:

- `base.py`: contrato común `AIProvider`.
- `context_engine.py`: reúne contexto estructurado de cobertura y fotografía.
- `models.py`: modelos `AIRequest`, `AIResult`, `AIError`, `CoverageContext` e `ImageReference`.
- `prompt_builder.py`: instrucciones editoriales compatibles con Xinhua.
- `providers/mock_provider.py`: proveedor simulado sin APIs externas.
- `service.py`: selección de proveedor, validación básica, ejecución, normalización de errores y logs técnicos.

## Flujo

1. La interfaz llama `POST /coverages/<coverage_id>/photos/<photo_id>/generate-narration`.
2. La ruta valida que existan cobertura y fotografía.
3. `ContextEngine` construye `CoverageContext` con datos de cobertura, fotografía y panel Contexto de IA.
4. `AIService` construye `AIRequest` con ese contexto estructurado.
5. `PromptBuilder` genera reglas editoriales desde `CoverageContext`.
6. El proveedor activo devuelve `AIResult`.
7. La interfaz coloca la narración en el textarea, actualiza contadores/vista previa y autoguarda como `En edición`.

## Context Engine

`ContextEngine` no genera prompts ni llama proveedores. Solo normaliza información disponible y evita `null` cuando puede enviar cadenas o listas vacías.

Reúne:

- Datos de cobertura: `coverage_id`, `coverage_title`, `city`, `country`, `event_date`, `send_date`, `agency`, `photographer`, `editor`.
- Contexto editorial: `known_people`, `organizations`, `keywords`, `notes`, `event_type`.
- Datos de fotografía: `photo_filename`, `photo_sequence`.
- Preparación futura: contenedores vacíos para EXIF, GPS, reconocimiento facial, OCR, objetos detectados, clasificación y noticias relacionadas.

Para añadir campos nuevos:

1. Agregar el campo en `CoverageContext`.
2. Normalizarlo en `ContextEngine.build()`.
3. Exponerlo en `ContextEngine.to_json_payload()` si debe verse en `Ver contexto IA`.
4. Usarlo en `PromptBuilder` o proveedores solo si es editorialmente seguro.

## Proveedor mock

`MockProvider` no analiza píxeles ni llama servicios externos. Simula latencia de 500 a 1000 ms y devuelve una narración editable basada en el contexto estructurado: persona conocida, organización, ciudad, título de cobertura y nombre de archivo.

Para probar errores desde la interfaz, usar `Alt/Option + clic` en `Generar con IA`.

## Configuración

Actual:

- `AI_PROVIDER=mock`

Variables preparadas para futuras integraciones:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `OLLAMA_BASE_URL`

La aplicación no requiere ninguna API key en esta iteración.

## Añadir un proveedor nuevo

1. Crear `app/ai/providers/<provider>_provider.py`.
2. Implementar `AIProvider.generate_narration(request: AIRequest) -> AIResult`.
3. Registrar el proveedor en `AIService._build_provider()`.
4. Mantener la salida limitada a narración editorial, sin encabezado, fecha, crédito ni caption completo.
5. No registrar prompts completos, imágenes, API keys ni datos sensibles.
