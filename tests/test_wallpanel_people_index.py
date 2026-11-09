"""Isolated tests for the optional Immich people index."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "wallpanel_photo_selector" / "people_index.py"
SPEC = importlib.util.spec_from_file_location("wallpanel_people_index", MODULE)
people_index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(people_index)


class PeopleIndexTests(unittest.TestCase):
    def test_missing_index_keeps_selection_available(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(people_index.load_people_index(Path(directory), {"a.jpg": {}}), {})

    def test_known_photos_and_names_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "immich-people.json").write_text(json.dumps({
                "a.jpg": [" Person B ", "Person B", "Person A"],
                "not-in-scanner.jpg": ["Person B"],
                "b.jpg": "invalid",
            }), encoding="utf-8")
            self.assertEqual(
                people_index.load_people_index(root, {"a.jpg": {}, "b.jpg": {}}),
                {"a.jpg": ["Person B", "Person A"]},
            )

    def test_diagnostics_count_matched_and_unmatched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "immich-people.json").write_text(json.dumps({
                "a.jpg": ["Person A"],
                "missing.jpg": ["Person B"],
                "bad.jpg": [],
            }), encoding="utf-8")
            matched, stats = people_index.load_people_index_diagnostics(
                root, {"a.jpg": {}, "b.jpg": {}}
            )
            self.assertEqual(matched, {"a.jpg": ["Person A"]})
            self.assertEqual(stats["entries"], 2)
            self.assertEqual(stats["matched"], 1)
            self.assertEqual(stats["unmatched"], 1)
            self.assertEqual(stats["status"], "loaded")

    def test_missing_index_reports_status(self):
        with tempfile.TemporaryDirectory() as directory:
            _, stats = people_index.load_people_index_diagnostics(
                Path(directory), {"a.jpg": {}}
            )
            self.assertEqual(stats["status"], "missing")
            self.assertEqual(stats["matched"], 0)

    def test_invalid_json_falls_back_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "immich-people.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(people_index.load_people_index(root, {"a.jpg": {}}), {})


if __name__ == "__main__":
    unittest.main()
