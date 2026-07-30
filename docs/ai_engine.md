# Motor de IA de ATLAS LENS

## Arquitectura

El motor vive en `app/ai` y está separado de rutas, templates, JavaScript y plantillas editoriales. La IA solo genera `Narración`; el caption final sigue siendo construido por la plantilla editorial existente.

Componentes:

- `base.py`: contrato común `AIProvider`.
- `models.py`: modelos `AIRequest`, `AIResult`, `AIError`, `CoverageContext` e `ImageReference`.
- `prompt_builder.py`: instrucciones editoriales compatibles con Xinhua.
- `providers/mock_provider.py`: proveedor simulado sin APIs externas.
- `service.py`: selección de proveedor, validación básica, ejecución, normalización de errores y logs técnicos.

## Flujo

1. La interfaz llama `POST /coverages/<coverage_id>/photos/<photo_id>/generate-narration`.
2. La ruta valida que existan cobertura y fotografía.
3. `AIService` construye `AIRequest` con contexto mínimo.
4. `PromptBuilder` genera reglas editoriales.
5. El proveedor activo devuelve `AIResult`.
6. La interfaz coloca la narración en el textarea, actualiza contadores/vista previa y autoguarda como `En edición`.

## Proveedor mock

`MockProvider` no analiza píxeles ni llama servicios externos. Simula latencia de 500 a 1000 ms y devuelve una narración editable basada en el título/contexto y nombre de archivo.

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
