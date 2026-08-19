# DISPATCH History Cleanup

DISPATCH permite eliminar registros del historial sin tocar datos compartidos de ATLAS.

## Eliminacion individual

La accion **Eliminar** borra unicamente el registro logico de DISPATCH.

No elimina:

- coberturas de LENS;
- fotografias;
- captions;
- originales de FLOW;
- artefactos propios de DISPATCH.

Estados protegidos contra eliminacion directa:

- Preparando;
- Programado;
- Enviando.

Estados historicos eliminables:

- Borrador;
- Listo;
- Enviado;
- Entregado;
- Error;
- Cancelado.

## Limpieza de historial

La accion **Limpiar historial** elimina solo registros historicos elegibles y conserva los despachos activos o programados.

Si no hay registros elegibles, DISPATCH muestra el mensaje:

`No hay despachos historicos que puedan eliminarse.`

## Orden del historial

El historial se muestra siempre del mas reciente al mas antiguo usando:

1. `scheduled_at` descendente.
2. `created_at` descendente como desempate o fallback cuando `scheduled_at` no existe.
