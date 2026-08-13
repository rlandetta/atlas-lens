# ATLAS LENS

## Flujo FLOW a LENS

FLOW mantiene las fotografías originales en su ubicación de ingreso. Desde `/flow`, cada sesión reciente muestra la acción `Abrir en LENS`.

Cuando una sesión FLOW todavía no tiene cobertura vinculada, esa acción crea una cobertura LENS reutilizando el store existente y guarda referencias a las fotografías reales mediante `flow_path`, sin copiar ni modificar los originales. La cobertura queda disponible en `/coverages/<coverage_id>`, donde se pueden seleccionar fotos, visualizar miniaturas o media, escribir captions y usar las secciones existentes de Exportaciones y DISPATCH.

La ruta manual `/flow/sessions/<session_id>/coverage/new` sigue disponible para completar datos editoriales antes de abrir la sesión en LENS.
