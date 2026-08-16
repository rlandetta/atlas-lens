import unittest

from app.ai.context_engine import ContextEngine
from app.ai.prompt_builder import PromptBuilder


class AIDroneContextTest(unittest.TestCase):
    def test_drone_photo_context_and_prompt_prevent_aerial_duplication(self):
        context = ContextEngine().build(
            "cov-1",
            {
                "coverage_name": "Mitad del Mundo",
                "city": "Quito",
                "country": "Ecuador",
                "event_date": "2026-08-16",
                "submit_date": "2026-08-16",
                "agency": "Xinhua",
            },
            {
                "id": "photo-1",
                "name": "DJI_001.jpg",
                "is_drone": True,
            },
            photo_sequence=1,
        )

        instructions = PromptBuilder().build_editorial_instructions(context)
        payload = ContextEngine().to_json_payload(context)

        self.assertTrue(context.is_drone)
        self.assertTrue(payload["photo"]["is_drone"])
        self.assertIn("no comenzar la narración con 'vista aérea'", instructions)
        self.assertIn("No incluir fecha, ciudad, país, ubicación estructurada", instructions)


if __name__ == "__main__":
    unittest.main()
