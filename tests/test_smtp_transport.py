import unittest
from unittest.mock import Mock, patch

from app.dispatch.smtp_transport import SMTPLinkTransport, SMTPTransportError


class FakeSettingsService:
    def resolve_channel_secret(self, channel):
        return "secret"


class SMTPServerStub:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.login_calls = []
        self.messages = []
        self.started_tls = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self, *, context):
        self.started_tls = True
        self.tls_context = context

    def login(self, username, password):
        self.login_calls.append((username, password))

    def send_message(self, message):
        self.messages.append(message)


class SMTPLinkTransportTest(unittest.TestCase):
    def setUp(self):
        self.transport = SMTPLinkTransport(settings_service=FakeSettingsService())
        self.channel = {
            "name": "Xinhua SMTP",
            "display_name": "Xinhua News Agency",
            "sender_email": "atlas@example.com",
            "reply_to": "editor@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "smtp_security": "ssl",
            "smtp_username": "atlas@example.com",
        }
        self.shipment = {
            "id": "ship-1",
            "name": "Cobertura Quito",
            "delivery_note": "Lista para descargar.",
            "recipients": [
                {"name": "Mesa", "email": "desk@example.com"},
                {"name": "Editor", "email": "editor@example.com"},
            ],
        }

    def test_build_message_contains_link_and_no_attachments(self):
        message = self.transport.build_message(
            channel=self.channel,
            shipment=self.shipment,
            download_url="https://atlas.example/d/token",
        )

        self.assertEqual(message["From"], "atlas@example.com")
        self.assertEqual(message["To"], "desk@example.com, editor@example.com")
        self.assertEqual(message["Reply-To"], "editor@example.com")
        self.assertIn("Cobertura fotográfica - Cobertura Quito", message["Subject"])
        self.assertIn("https://atlas.example/d/token", message.get_content())
        self.assertFalse(message.is_multipart())
        self.assertEqual(list(message.iter_attachments()), [])

    def test_send_link_uses_ssl_smtp(self):
        server = SMTPServerStub()
        smtp_factory = Mock(return_value=server)

        with patch("app.dispatch.smtp_transport.smtplib.SMTP_SSL", smtp_factory):
            result = self.transport.send_link(
                channel=self.channel,
                shipment=self.shipment,
                download_url="https://atlas.example/d/token",
            )

        smtp_factory.assert_called_once()
        self.assertEqual(server.login_calls, [("atlas@example.com", "secret")])
        self.assertEqual(len(server.messages), 1)
        self.assertEqual(result["recipients"], ["desk@example.com", "editor@example.com"])

    def test_send_link_uses_starttls_when_configured(self):
        server = SMTPServerStub()
        smtp_factory = Mock(return_value=server)
        channel = dict(self.channel)
        channel.update({"smtp_security": "starttls", "smtp_port": 587})

        with patch("app.dispatch.smtp_transport.smtplib.SMTP", smtp_factory):
            self.transport.send_link(
                channel=channel,
                shipment=self.shipment,
                download_url="https://atlas.example/d/token",
            )

        smtp_factory.assert_called_once()
        self.assertTrue(server.started_tls)
        self.assertEqual(server.login_calls, [("atlas@example.com", "secret")])

    def test_send_link_rejects_missing_recipients(self):
        shipment = dict(self.shipment)
        shipment["recipients"] = []

        with self.assertRaises(SMTPTransportError):
            self.transport.send_link(
                channel=self.channel,
                shipment=shipment,
                download_url="https://atlas.example/d/token",
            )


if __name__ == "__main__":
    unittest.main()
