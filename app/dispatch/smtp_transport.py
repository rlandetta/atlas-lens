from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Any


class SMTPTransportError(ValueError):
    pass


class SMTPLinkTransport:
    def __init__(self, *, settings_service):
        self.settings_service = settings_service

    def build_message(self, *, channel: dict[str, Any], shipment: dict[str, Any], download_url: str) -> EmailMessage:
        recipients = self.recipients(shipment)
        if not recipients:
            raise SMTPTransportError("El despacho no tiene destinatarios válidos para notificar por correo.")
        sender = str(channel.get("sender_email", "")).strip()
        if not sender:
            raise SMTPTransportError("El canal SMTP no tiene remitente configurado.")
        display_name = str(channel.get("display_name") or channel.get("name") or sender).strip()
        subject = f"Cobertura fotográfica - {str(shipment.get('name', '')).strip() or shipment.get('id', '')}"
        note = str(shipment.get("delivery_note", "")).strip()
        if note:
            body = (
                "Estimados,\n\n"
                f"{note}\n\n"
                "Puede descargar los archivos desde el siguiente enlace:\n\n"
                f"{download_url}\n\n"
                "Saludos,\n"
                f"{display_name}"
            )
        else:
            body = (
                "Estimados,\n\n"
                f"Está disponible la cobertura fotográfica \"{str(shipment.get('name', '')).strip()}\".\n\n"
                "Puede descargar los archivos desde el siguiente enlace:\n\n"
                f"{download_url}\n\n"
                "Saludos,\n"
                f"{display_name}"
            )
        message = EmailMessage()
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        reply_to = str(channel.get("reply_to", "")).strip()
        if reply_to:
            message["Reply-To"] = reply_to
        message["Subject"] = subject
        message.set_content(body)
        return message

    def send_link(self, *, channel: dict[str, Any], shipment: dict[str, Any], download_url: str) -> dict[str, Any]:
        message = self.build_message(channel=channel, shipment=shipment, download_url=download_url)
        password = self.settings_service.resolve_channel_secret(channel)
        host = str(channel.get("smtp_host", "")).strip()
        username = str(channel.get("smtp_username", "")).strip()
        port = int(channel.get("smtp_port") or 465)
        security = str(channel.get("smtp_security") or "ssl").strip().lower()
        if not host or not username:
            raise SMTPTransportError("Canal SMTP incompleto.")
        try:
            if security == "ssl":
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, context=context) as server:
                    server.login(username, password)
                    server.send_message(message)
            elif security == "starttls":
                context = ssl.create_default_context()
                with smtplib.SMTP(host, port) as server:
                    server.starttls(context=context)
                    server.login(username, password)
                    server.send_message(message)
            else:
                raise SMTPTransportError("Seguridad SMTP no soportada.")
        except SMTPTransportError:
            raise
        except Exception as error:
            raise SMTPTransportError("No se pudo enviar la notificación SMTP.") from error
        return {"recipients": self.recipients(shipment), "subject": str(message["Subject"])}

    @staticmethod
    def recipients(shipment: dict[str, Any]) -> list[str]:
        recipients = []
        for recipient in shipment.get("recipients", []):
            if not isinstance(recipient, dict):
                continue
            email = str(recipient.get("email", "")).strip()
            if email:
                recipients.append(email)
        return recipients
