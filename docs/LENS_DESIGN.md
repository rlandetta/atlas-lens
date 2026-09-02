 # ATLAS LENS – Diseño oficial

## Estado

Este documento define la identidad visual oficial del módulo LENS.

## Paleta

Fondo:
#0F1720

Paneles:
#16202B

Principal:
#A36B2C

Hover:
#8B5A22

Texto:
#E6E6E6

Texto secundario:
#8A94A6

## Layout

- Sidebar izquierdo fijo.
- Cabecera compacta.
- Tarjetas editoriales.
- Formularios en dos columnas.
- Pestañas:
    - Fotografías
    - Captions
    - Exportaciones
    - Entregas
- Panel lateral para editar información.
- Las coberturas se listan por hora real de creación descendente; si falta `created_at`, se usa el timestamp del identificador `cov-...` como fallback estable.
- El editor individual de captions muestra el contador de fotografía y el nombre de archivo activo, usando tipografía secundaria y truncado visual cuando corresponde.
- Las captions admiten `admin_area` y `admin_area_type` para localidades no capitales, de modo que el motor pueda generar frases como provincia, estado, departamento, región o distrito sin duplicar localidad ni país.
- Diseño totalmente responsivo.

## Filosofía

LENS debe sentirse como un software profesional para edición fotográfica, no como una aplicación de formularios.
Las fotografías serán el elemento principal de la interfaz.
