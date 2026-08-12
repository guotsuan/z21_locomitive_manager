import json
import unittest

from src.function_extraction import (
    SHORTCUTS,
    DeepSeekFunctionTableExtractor,
    discover_icon_mapping,
    driver_cabin_light_side,
    historical_button_types,
    infer_button_type,
    match_function_icon,
    meaningful_shortcut,
    missing_function_numbers,
    order_function_positions,
    parse_function_number,
)
from src.ocr import BoundingBox, OCRPage, OCRResult, TextObservation


def ocr_result(texts):
    observations = tuple(TextObservation(
        text=text, confidence=.96,
        bounding_box=BoundingBox(.1, .8 - index * .1, .8, .05),
        candidates=()) for index, text in enumerate(texts))
    return OCRResult("apple-vision", ("de-DE",),
                     (OCRPage(0, 1000, 1400, observations),))


class FunctionExtractionTests(unittest.TestCase):
    def test_multilingual_icon_rules_use_only_available_icons(self):
        icons = ["neutral", "light", "horn_low", "cabin_light"]
        self.assertEqual(match_function_icon("Licht vorne ein/aus", icons),
                         "light")
        self.assertEqual(match_function_icon("Signalhorn tief", icons),
                         "horn_low")
        self.assertEqual(match_function_icon(
            "Führerstandsbeleuchtung", icons), "cabin_light")
        self.assertEqual(match_function_icon("Unknown effect", icons),
                         "neutral")

    def test_button_semantics_precede_historical_prior(self):
        self.assertEqual(infer_button_type(
            "Horn short", "bugle", {"bugle": 0}), 1)
        self.assertEqual(infer_button_type(
            "Digital coupling rear", "decouple", {"decouple": 0}), 2)
        self.assertEqual(infer_button_type(
            "Engine sound", "sound2", {"sound2": 0}), 0)

    def test_historical_button_type_uses_local_database_majority(self):
        class Function:
            def __init__(self, icon, button):
                self.image_name = icon
                self.button_type = button

        class Loco:
            function_details = {
                1: Function("sound2", 0),
                2: Function("sound2", 0),
                3: Function("sound2", 1),
            }

        self.assertEqual(historical_button_types([Loco()])["sound2"], 0)

    def test_function_number_is_bounded(self):
        self.assertEqual(parse_function_number("F0"), 0)
        self.assertEqual(parse_function_number(" F 32 "), 32)
        self.assertIsNone(parse_function_number("F33"))
        self.assertIsNone(parse_function_number("CV1"))

    def test_function_sequence_reports_only_internal_gaps(self):
        self.assertEqual(missing_function_numbers([0, 2, 3, 5]), (1, 4))
        self.assertEqual(missing_function_numbers([3, 4, 5]), ())
        self.assertEqual(missing_function_numbers([7]), ())

    def test_function_positions_are_reordered_by_f_number(self):
        class Function:
            def __init__(self, number, position):
                self.function_number = number
                self.position = position

        functions = {
            14: Function(14, 1),
            0: Function(0, 0),
            15: Function(15, 3),
            1: Function(1, 2),
        }
        order_function_positions(functions)
        self.assertEqual(
            [(number, functions[number].position) for number in sorted(functions)],
            [(0, 0), (1, 1), (14, 2), (15, 3)])

    def test_shortcuts_are_meaningful_and_five_to_eight_characters(self):
        cases = (
            ("Light on/off", "light", "LIGHT"),
            ("Engine sound", "sound2", "ENGISOUN"),
            ("Signalhorn tief", "horn_low", "SIGNTIEF"),
            ("Bell", "", "BELLFX"),
        )
        for name, icon, expected in cases:
            shortcut = meaningful_shortcut(name, icon)
            self.assertEqual(shortcut, expected)
            self.assertGreaterEqual(len(shortcut), 5)
            self.assertLessEqual(len(shortcut), 8)

    def test_same_icon_uses_distinct_table_descriptions_for_shortcut(self):
        self.assertEqual(
            meaningful_shortcut("Driver Noise", "sound2"), "DRIVNOIS")
        self.assertEqual(
            meaningful_shortcut("Engine Sound", "sound2"), "ENGISOUN")
        self.assertNotEqual(
            meaningful_shortcut("Driver Noise", "sound2"),
            meaningful_shortcut("Engine Sound", "sound2"))

    def test_icon_shortcut_is_only_used_when_description_is_missing(self):
        self.assertEqual(meaningful_shortcut("", "light"), "HEADLIT")

    def test_unmatched_icon_uses_description_and_may_reach_ten_chars(self):
        cases = {
            "Station announcement": "STATIANNOU",
            "Water filling": "WATERFILLI",
            "Radio message three": "RADMESTHR",
        }
        for description, expected in cases.items():
            with self.subTest(description=description):
                shortcut = meaningful_shortcut(description, "neutral")
                self.assertEqual(shortcut, expected)
                self.assertGreaterEqual(len(shortcut), 5)
                self.assertLessEqual(len(shortcut), 10)
                self.assertNotEqual(shortcut, "FUNCTN")

    def test_icon_discovery_adds_unconfigured_png_files(self):
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            icons = Path(directory)
            (icons / "light_Normal.png").touch()
            (icons / "destination_plate_light_Normal.png").touch()
            mapping = discover_icon_mapping(icons, {
                "light": {"filename": "light_Normal.png"}})
            self.assertIn("light", mapping)
            self.assertEqual(
                mapping["destination_plate_light"]["filename"],
                "destination_plate_light_Normal.png")

    def test_filename_canonical_icon_overrides_stale_alias(self):
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            icons = Path(directory)
            (icons / "sound5_Normal.png").touch()
            mapping = discover_icon_mapping(icons, {
                "sound5": {"filename": "conductor_signal.png"}})
            self.assertEqual(mapping["sound5"]["filename"],
                             "sound5_Normal.png")

    def test_specific_sound_effect_beats_generic_sound_icon(self):
        icons = ["neutral", "sound2", "sound5", "scoop_coal_sound"]
        self.assertEqual(match_function_icon(
            "Coal shoveling sound", icons), "scoop_coal_sound")
        self.assertEqual(match_function_icon("Sound 5", icons), "sound5")

    def test_specific_light_and_fan_icons_beat_generic_icons(self):
        icons = ["neutral", "light", "destination_plate_light",
                 "fan", "fan_strong"]
        self.assertEqual(match_function_icon(
            "Destination plate light on/off", icons),
            "destination_plate_light")
        self.assertEqual(match_function_icon(
            "Fan high speed", icons), "fan_strong")

    def test_f0_light_prefers_main_beam_icon(self):
        icons = ["neutral", "light", "main_beam"]
        self.assertEqual(match_function_icon(
            "Light on/off", icons, function_number=0), "main_beam")
        self.assertEqual(match_function_icon(
            "F0 Light on/off", icons), "main_beam")
        self.assertEqual(match_function_icon(
            "Light on/off", icons, function_number=3), "light")

    def test_driver_light_cabin_pair_uses_distinct_icon_group(self):
        icons = ["neutral", "light", "light2", "cabin_light",
                 "cockpit_light_left", "cockpit_light_right"]
        cabin_one = (
            "Driver's cablin light for cabin 1",
            "Driver's cabin light for cabin 1",
            "Driver's light for cabin 1",
        )
        cabin_two = (
            "Driver's cablin light for cabin 2",
            "Driver's cabin light for cabin 2",
            "Driver's light for cabin 2",
        )
        for description in cabin_one:
            self.assertEqual(match_function_icon(description, icons), "light")
            self.assertEqual(match_function_icon(
                description, icons, cabin_occurrence=2),
                "cockpit_light_left")
        for description in cabin_two:
            self.assertEqual(match_function_icon(description, icons), "light2")
            self.assertEqual(match_function_icon(
                description, icons, cabin_occurrence=2),
                "cockpit_light_right")

    def test_driver_light_cabin_pair_falls_back_to_general_light_icons(self):
        icons = ["neutral", "light", "light2"]
        self.assertEqual(match_function_icon(
            "Driver's cabin light for cabin 1", icons), "light")
        self.assertEqual(match_function_icon(
            "Driver's cabin light for cabin 2", icons), "light2")

    def test_driver_cabin_pair_detection_excludes_deactivation_rows(self):
        self.assertEqual(driver_cabin_light_side(
            "Driver's cabin light for cabin 1"), 1)
        self.assertEqual(driver_cabin_light_side(
            "Driver's cablin light for cabin 2"), 2)
        self.assertIsNone(driver_cabin_light_side(
            "Light deactivation for driver's cabin 1"))

    def test_extractor_assigns_first_and_second_cabin_icon_groups(self):
        rows = [
            # Deliberately use an interleaved multi-column OCR/model order.
            ("F1", "Driver's cabin light for cabin 1"),
            ("F3", "Driver's light for cabin 1"),
            ("F2", "Driver's cabin light for cabin 2"),
            ("F4", "Driver's light for cabin 2"),
        ]
        response = {"choices": [{"message": {"content": json.dumps({
            "functions": [{
                "number": number, "name": name, "confidence": .95,
                "evidence": f"{number} {name}",
                "button_behavior": "switch",
            } for number, name in rows]
        })}}]}
        result = DeepSeekFunctionTableExtractor(
            "key", transport=lambda *args: response).extract(
                ocr_result([f"{number} {name}" for number, name in rows]),
                ["neutral", "light", "light2", "cockpit_light_left",
                 "cockpit_light_right"])
        self.assertEqual(
            [proposal.icon_name for proposal in result],
            ["light", "light2", "cockpit_light_left",
             "cockpit_light_right"])

    def test_additional_manual_phrases_map_to_requested_icons(self):
        icons = [
            "neutral", "sound2", "sound5", "conductor_signal",
            "cockpit_light_left", "cockpit_light_right", "door_open",
            "door_close", "compressor", "sifa", "louder", "quiter",
        ]
        cases = {
            "Driver Noise": "sound2",
            "Conductor's signal": "sound5",
            "Driver's cabin light for driver's cabin 1":
                "cockpit_light_left",
            "Light deactivation for driver's cabin 2":
                "cockpit_light_right",
            "Light deactivation for driver's cabin 1":
                "cockpit_light_left",
            "Open / close door": "door_close",
            "Air conditioning": "compressor",
            "Emergency brake": "sifa",
            "Volume increase": "louder",
            "Volume decrease": "quiter",
        }
        for function_name, expected_icon in cases.items():
            with self.subTest(function_name=function_name):
                self.assertEqual(
                    match_function_icon(function_name, icons), expected_icon)

    def test_every_predefined_shortcut_has_required_length(self):
        self.assertTrue(SHORTCUTS)
        self.assertEqual(
            [], [(icon, shortcut) for icon, shortcut in SHORTCUTS.items()
                 if not 5 <= len(shortcut) <= 8])

    def test_extracts_deduplicates_and_maps_icons(self):
        response = {"choices": [{"message": {"content": json.dumps({
            "functions": [
                {"number": "F0", "name": "Light on/off",
                 "confidence": .95, "evidence": "F0 Light on/off",
                 "button_behavior": "switch"},
                {"number": "F1", "name": "Sound on/off",
                 "confidence": .92, "evidence": "F1 Sound on/off",
                 "button_behavior": None},
                {"number": "F1", "name": "Wrong duplicate",
                 "confidence": .2, "evidence": "F1 Sound on/off",
                 "button_behavior": None},
            ]})}}]}
        captured = {}

        def transport(model, messages, config):
            captured.update(model=model, messages=messages, config=config)
            return response

        result = DeepSeekFunctionTableExtractor(
            "key", transport=transport).extract(
                ocr_result(["F0 Light on/off", "F1 Sound on/off"]),
                ["neutral", "light", "sound2"], {"sound2": 0})

        self.assertEqual([item.number for item in result], [0, 1])
        self.assertEqual([item.icon_name for item in result],
                         ["light", "sound2"])
        self.assertEqual(captured["model"], "deepseek-v4-flash")
        self.assertEqual(captured["config"]["response_format"],
                         {"type": "json_object"})
        self.assertIn("Bounding boxes", captured["messages"][0]["content"])

    def test_requires_a_detectable_function_table(self):
        with self.assertRaisesRegex(Exception, "No F0–F32"):
            DeepSeekFunctionTableExtractor(
                "key", transport=lambda *args: {}).extract(
                    ocr_result(["General locomotive instructions"]),
                    ["neutral"])


if __name__ == "__main__":
    unittest.main()
