# DISPATCH Delivery Method UX

El formulario de nuevo despacho muestra dos metodos visibles:

- Generar enlace de descarga.
- Enviar enlace por correo.

## Generar enlace de descarga

Este metodo crea un enlace para compartir y no envia correo.

El bloque de destinatarios no se muestra para este metodo. DISPATCH no exige nombre ni correo para guardar el despacho o generar el enlace.

La nota de entrega y la expiracion del enlace siguen disponibles.

## Vista publica de descarga

La pagina publica del enlace de descarga es una vista externa y autocontenida. No debe enlazar al dashboard, LENS, DISPATCH, Settings ni a otras pantallas internas de ATLAS.

El footer publico usa el texto neutro `Powered by ATLAS · Digital Asset Delivery` y no muestra referencias a La Voceria ni dominios provisionales. Las acciones disponibles para el cliente se limitan a consultar la entrega y descargar los archivos autorizados.

## Enviar enlace por correo

Este metodo crea el enlace de descarga y usa la cuenta de correo configurada en Settings para enviarlo a los destinatarios.

El formulario no muestra el selector de canal. La seleccion de cuenta/canal pertenece a Settings.

DISPATCH exige al menos un destinatario con correo valido para guardar, enviar ahora o programar el envio por correo.

El correo envia el enlace de descarga.

## Programacion

Programar envio esta disponible para el metodo de correo. Para el metodo de enlace simple, el usuario puede guardar borrador o generar el enlace ahora.
