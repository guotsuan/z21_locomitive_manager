import json
import threading
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.ocr import (
    AppleVisionOCRService,
    BoundingBox,
    DEFAULT_LANGUAGES,
    OCRError,
    OCRPage,
    OCRResult,
    OCRService,
    RAILWAY_CUSTOM_WORDS,
    TextObservation,
)


class AppleVisionOCRServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.temp_path = Path(self.temp_directory.name)
        self.source_path = self.temp_path / "vision.swift"
        self.source_path.write_text("// helper", encoding="utf-8")
        self.input_path = self.temp_path / "manual.png"
        self.input_path.write_bytes(b"image")
        self.service = AppleVisionOCRService(
            source_path=self.source_path,
            cache_directory=self.temp_path / "cache",
        )

    def test_recognize_preserves_candidates_confidence_and_coordinates(self):
        payload = {
            "status": "ok",
            "languages": ["de-DE", "en-US", "fr-FR"],
            "pages": [{
                "index": 0,
                "width": 1200,
                "height": 800,
                "observations": [{
                    "text": "PluX22",
                    "confidence": 0.96,
                    "boundingBox": {
                        "x": 0.1, "y": 0.7,
                        "width": 0.2, "height": 0.05,
                    },
                    "candidates": [
                        {"text": "PluX22", "confidence": 0.96},
                        {"text": "PluX 22", "confidence": 0.74},
                    ],
                }],
            }],
        }

        def run(command, **kwargs):
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(json.dumps(payload), encoding="utf-8")
            config_path = Path(command[command.index("--config") + 1])
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["languages"], list(DEFAULT_LANGUAGES))
            self.assertIn("DCC", config["customWords"])
            self.assertIn("F32", config["customWords"])
            return subprocess.CompletedProcess(
                args=command, returncode=0, stdout="", stderr="")

        with mock.patch.object(self.service, "_ensure_helper",
                               return_value=Path("/fake/vision-helper")), \
                mock.patch("src.ocr.subprocess.run", side_effect=run):
            result = self.service.recognize(self.input_path)

        observation = result.pages[0].observations[0]
        self.assertEqual(result.engine, "apple-vision")
        self.assertEqual(result.text, "PluX22")
        self.assertAlmostEqual(observation.confidence, 0.96)
        self.assertEqual(observation.bounding_box,
                         BoundingBox(0.1, 0.7, 0.2, 0.05))
        self.assertEqual(observation.candidates[1].text, "PluX 22")

    def test_page_text_uses_vision_reading_order(self):
        low = TextObservation(
            "second", 0.9, BoundingBox(0.1, 0.2, 0.3, 0.1), ())
        high_right = TextObservation(
            "right", 0.9, BoundingBox(0.6, 0.8, 0.2, 0.1), ())
        high_left = TextObservation(
            "first", 0.9, BoundingBox(0.1, 0.8, 0.2, 0.1), ())
        page = OCRPage(0, 100, 100, (low, high_right, high_left))
        self.assertEqual(page.text, "first\nright\nsecond")

    def test_railway_dictionary_contains_required_terms(self):
        for word in ("DCC", "RailCom", "PluX22", "NEM 652", "SUSI",
                     "F0", "F32", "Roco", "Bremsenquietschen"):
            self.assertIn(word, RAILWAY_CUSTOM_WORDS)


class OCRServiceSelectionTests(unittest.TestCase):
    def test_macos_prefers_apple_vision(self):
        result = OCRResult("apple-vision", (), ())
        vision = mock.Mock()
        vision.recognize.return_value = result
        fallback = mock.Mock()
        service = OCRService(vision, fallback, system_name="Darwin")

        self.assertIs(service.recognize(Path("manual.png")), result)
        fallback.recognize.assert_not_called()

    def test_macos_falls_back_after_vision_error(self):
        fallback_result = OCRResult("tesseract", (), ())
        vision = mock.Mock()
        vision.recognize.side_effect = OCRError("Vision unavailable")
        fallback = mock.Mock()
        fallback.recognize.return_value = fallback_result
        service = OCRService(vision, fallback, system_name="Darwin")

        self.assertIs(service.recognize(Path("manual.png")), fallback_result)

    def test_cancellation_token_is_forwarded_to_engine(self):
        result = OCRResult("apple-vision", (), ())
        vision = mock.Mock()
        vision.recognize.return_value = result
        cancel_event = threading.Event()
        service = OCRService(vision, mock.Mock(), system_name="Darwin")

        self.assertIs(service.recognize(Path("manual.pdf"),
                                        cancel_event=cancel_event), result)
        vision.recognize.assert_called_once_with(
            Path("manual.pdf"), cancel_event=cancel_event)


if __name__ == "__main__":
    unittest.main()
