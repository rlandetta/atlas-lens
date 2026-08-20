import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.settings import OutboundChannelDraft, SettingsSecretError, SettingsService, SettingsStore, SettingsValidationError
from app.settings.models import build_channel


class SettingsRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.settings_store_path = self.root / "settings.json"
        self.dispatch_store_path = self.root / "dispatch_shipments.json"
        self.lens_store_path = self.root / "lens_coverages.json"
        self.lens_media_root = self.root / "lens_media"
        self.patches = [
            patch("app.config.SETTINGS_STORE_PATH", str(self.settings_store_path)),
            patch("app.config.DISPATCH_STORE_PATH", str(self.dispatch_store_path)),
            patch("app.config.LENS_COVERAGE_STORE_PATH", str(self.lens_store_path)),
            patch("app.config.LENS_MEDIA_ROOT", str(self.lens_media_root)),
        ]
        for item in self.patches:
            item.start()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        self.service = self.app.extensions["settings"]["settings_service"]

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def valid_form(self, **overrides):
        form = {
            "id": "xinhua",
            "name": "Xinhua",
            "display_name": "Xinhua News Agency",
            "channel_type": "smtp",
            "sender_email": "atlas@lavoceria.com",
            "reply_to": "desk@xinhua.com",
            "smtp_host": "smtp.zoho.com",
            "smtp_port": "465",
            "smtp_security": "ssl",
            "smtp_username": "atlas@lavoceria.com",
            "credential_ref": "ATLAS_SMTP_CHANNEL_XINHUA",
            "is_active": "1",
            "is_default": "1",
        }
        form.update(overrides)
        return {key: value for key, value in form.items() if value is not None}

    def create_channel(self, **overrides):
        response = self.client.post("/settings/channels/new", data=self.valid_form(**overrides), follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        return self.service.list_outbound_channels()[0]

    def test_settings_blueprint_and_header_are_registered(self):
        response = self.client.get("/settings/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("SETTINGS", body)
        self.assertIn("Canales de salida", body)
        self.assertIn("Usuarios", body)
        self.assertIn("Próximamente", body)
        self.assertIn('href="/settings/"', body)

    def test_create_edit_and_delete_channel_without_secret(self):
        channel = self.create_channel()

        self.assertEqual(channel["id"], "xinhua")
        self.assertTrue(channel["is_default"])
        payload = json.loads(self.settings_store_path.read_text(encoding="utf-8"))
        raw_json = json.dumps(payload)
        self.assertIn("credential_ref", raw_json)
        self.assertNotIn("smtp_password", raw_json)
        self.assertNotIn("app_password", raw_json)
        self.assertNotIn("super-secret", raw_json)

        response = self.client.post(
            "/settings/channels/xinhua/edit",
            data=self.valid_form(name="Xinhua Editado", smtp_port="587", smtp_security="starttls", smtp_password="super-secret"),
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        updated = self.service.get_outbound_channel("xinhua")
        self.assertEqual(updated["name"], "Xinhua Editado")
        self.assertEqual(updated["smtp_port"], 587)
        self.assertEqual(updated["smtp_security"], "starttls")
        self.assertNotIn("smtp_password", updated)

        response = self.client.post("/settings/channels/xinhua/delete", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.service.list_outbound_channels(), [])

    def test_form_does_not_request_password_and_list_does_not_expose_secret(self):
        self.create_channel()

        form_body = self.client.get("/settings/channels/new").get_data(as_text=True)
        list_body = self.client.get("/settings/channels").get_data(as_text=True)

        self.assertNotIn('name="password"', form_body)
        self.assertNotIn('name="smtp_password"', form_body)
        self.assertNotIn("ATLAS_SMTP_CHANNEL_XINHUA", list_body)
        self.assertIn("Xinhua", list_body)

    def test_smtp_form_hides_sftp_fields_and_keeps_credential_help_secret_safe(self):
        body = self.client.get("/settings/channels/new").get_data(as_text=True)

        self.assertIn('data-channel-section="smtp"', body)
        self.assertIn('data-channel-section="sftp"', body)
        self.assertIn('section.dataset.channelSection === type', body)
        self.assertIn('input.disabled = !visible', body)
        self.assertIn("La contraseña se administra de forma segura fuera de ATLAS.", body)

    def test_sftp_form_renders_only_sftp_fields_after_type_selection(self):
        body = self.client.post(
            "/settings/channels/new",
            data=self.valid_form(
                channel_type="sftp",
                sender_email="",
                reply_to="",
                smtp_host="",
                smtp_port="",
                smtp_security="",
                smtp_username="",
                credential_ref="ATLAS_SFTP_XINHUA",
                host="sftp.example.com",
                port="22",
                username="atlas",
                remote_path="/incoming",
                name="",
            ),
        ).get_data(as_text=True)

        self.assertIn('data-channel-section="sftp"', body)
        self.assertIn('data-channel-section="smtp"', body)
        self.assertIn('section.dataset.channelSection === type', body)
        self.assertNotIn("Servidor SMTP es obligatorio", body)

    def test_download_link_does_not_require_smtp_or_sftp_configuration(self):
        response = self.client.post(
            "/settings/channels/new",
            data=self.valid_form(
                id="download_link",
                name="Enlace editorial",
                channel_type="download_link",
                sender_email="",
                reply_to="",
                smtp_host="",
                smtp_port="",
                smtp_security="",
                smtp_username="",
                credential_ref="",
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        channel = self.service.get_outbound_channel("download_link")
        self.assertEqual(channel["channel_type"], "download_link")
        self.assertEqual(channel["credential_ref"], "")

    def test_api_is_disabled_in_ui_and_rejected_by_backend(self):
        body = self.client.get("/settings/channels/new").get_data(as_text=True)
        self.assertIn('<option value="api" disabled', body)

        response = self.client.post(
            "/settings/channels/new",
            data=self.valid_form(channel_type="api"),
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("API todavía no está disponible", response.get_data(as_text=True))

    def test_validations_reject_invalid_email_port_security_and_missing_credential_ref(self):
        cases = [
            {"sender_email": "invalid"},
            {"smtp_port": "70000"},
            {"smtp_security": "none"},
            {"credential_ref": ""},
        ]
        for override in cases:
            response = self.client.post("/settings/channels/new", data=self.valid_form(**override), follow_redirects=False)
            self.assertEqual(response.status_code, 400)

    def test_new_channel_id_requires_lowercase_ascii_but_existing_id_is_preserved(self):
        response = self.client.post("/settings/channels/new", data=self.valid_form(id="La_Vocería"), follow_redirects=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn("minúsculas ASCII", response.get_data(as_text=True))

        legacy_draft = OutboundChannelDraft(
            id="La_Vocería",
            name="Legado",
            display_name="Legado",
            channel_type="smtp",
            sender_email="atlas@lavoceria.com",
            reply_to="",
            smtp_host="smtp.zoho.com",
            smtp_port=465,
            smtp_security="ssl",
            smtp_username="atlas@lavoceria.com",
            credential_ref="ATLAS_SMTP_CHANNEL_LEGACY",
        )
        legacy = build_channel(legacy_draft)
        self.service.store.save_channels([legacy])
        response = self.client.post(
            "/settings/channels/La_Vocería/edit",
            data=self.valid_form(id="La_Vocería", name="Legado", credential_ref="ATLAS_SMTP_CHANNEL_LEGACY"),
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.service.get_outbound_channel(legacy["id"])["id"], "La_Vocería")

    def test_only_one_default_channel(self):
        self.create_channel(id="xinhua", name="Xinhua", credential_ref="ATLAS_SMTP_CHANNEL_XINHUA")
        self.create_channel(id="afp", name="AFP", sender_email="afp@example.com", credential_ref="ATLAS_SMTP_CHANNEL_AFP")

        channels = {channel["id"]: channel for channel in self.service.list_outbound_channels()}
        self.assertFalse(channels["xinhua"]["is_default"])
        self.assertTrue(channels["afp"]["is_default"])

    def test_resolve_channel_secret_from_environment_and_fails_cleanly(self):
        channel = self.create_channel()

        with patch.dict("os.environ", {"ATLAS_SMTP_CHANNEL_XINHUA": "runtime-secret"}):
            self.assertEqual(self.service.resolve_channel_secret(channel), "runtime-secret")
        with self.assertRaises(SettingsSecretError) as context:
            self.service.resolve_channel_secret(channel)
        self.assertEqual(str(context.exception), "Credencial SMTP no configurada.")

    def test_sftp_channel_stores_remote_fields_without_secret(self):
        channel = self.create_channel(
            id="xinhua-sftp",
            name="Xinhua SFTP",
            display_name="Xinhua SFTP",
            channel_type="sftp",
            sender_email="",
            reply_to="",
            smtp_host="",
            smtp_username="",
            credential_ref="ATLAS_SFTP_XINHUA",
            host="sftp.example.com",
            port="22",
            username="atlas",
            remote_path="/incoming",
            host_key_fingerprint="SHA256:test",
            smtp_password="do-not-store",
        )

        raw_json = self.settings_store_path.read_text(encoding="utf-8")
        self.assertEqual(channel["channel_type"], "sftp")
        self.assertEqual(channel["host"], "sftp.example.com")
        self.assertEqual(channel["remote_path"], "/incoming")
        self.assertNotIn("do-not-store", raw_json)

    def test_smtp_channel_ignores_legacy_sftp_values(self):
        channel = self.create_channel(host="smtp.zoho.com", port="465", username="atlas@lavoceria.com", remote_path="/wrong")

        self.assertEqual(channel["channel_type"], "smtp")
        self.assertEqual(channel["host"], "")
        self.assertEqual(channel["port"], "")
        self.assertEqual(channel["username"], "")
        self.assertEqual(channel["remote_path"], "")

    def test_channel_list_uses_separate_badges_and_actions(self):
        self.create_channel()

        body = self.client.get("/settings/channels").get_data(as_text=True)

        self.assertIn("settings-channel-side", body)
        self.assertIn("settings-channel-badges", body)
        self.assertIn("Editar", body)
        self.assertIn("Eliminar", body)

    def test_download_link_and_api_types_are_visible(self):
        body = self.client.get("/settings/channels/new").get_data(as_text=True)

        self.assertIn("Enlace de descarga", body)
        self.assertIn("API · Próximamente", body)


class SettingsServiceStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SettingsStore(Path(self.temp_dir.name) / "settings.json")
        self.service = SettingsService(self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_duplicate_channel_id_is_rejected(self):
        draft = OutboundChannelDraft(
            id="xinhua",
            name="Xinhua",
            display_name="Xinhua",
            channel_type="smtp",
            sender_email="atlas@lavoceria.com",
            reply_to="",
            smtp_host="smtp.zoho.com",
            smtp_port=465,
            smtp_security="ssl",
            smtp_username="atlas@lavoceria.com",
            credential_ref="ATLAS_SMTP_CHANNEL_XINHUA",
        )
        self.service.create_outbound_channel(draft)
        with self.assertRaises(SettingsValidationError):
            self.service.create_outbound_channel(draft)


if __name__ == "__main__":
    unittest.main()
