# Export UI Navigation Defaults

## Cambio

- La accion `Volver a cobertura` queda siempre visible en la seccion Exportaciones, entre `Descargar` y `Enviar a DISPATCH`.
- El enlace apunta a la ruta canonica `/lens/coverages/<coverage_id>`.
- El panel de resultado ya no genera un segundo boton `Volver a cobertura`.
- `Incluir fotografias` queda desmarcado por defecto.

## Alcance

- No se modifico DISPATCH.
- No se modifico la logica de envio a DISPATCH.
- No se modifico la logica del Export Engine.
- La seleccion manual de fotografias originales mantiene el comportamiento existente: cualquier exportacion con originales genera ZIP.

## Validacion

- La vista de detalle de cobertura renderiza el enlace persistente antes de generar exportaciones.
- El checkbox `include_photos` se renderiza sin `checked`.
- Los tests cubren que el enlace use el `coverage_id` correcto, no este duplicado en el resultado, y que `include_photos=True` siga generando ZIP.
