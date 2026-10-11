"""Self-checks for the shared content guard (tests/content_guard.py)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import content_guard  # noqa: E402


class ContentGuard(unittest.TestCase):

    def test_whole_plugin_tree_is_clean(self):
        self.assertEqual(content_guard.scan(content_guard.PLUGINS), [])

    def test_ordinary_engineering_prose_is_not_flagged(self):
        self.assertEqual(content_guard.find_banned("Plywood supports, a stress check and the span of the pipe."), [])

    def test_windows_absolute_path_is_detected(self):
        self.assertIsNotNone(content_guard.WINDOWS_PATH.search("C" + ":" + "\\" + "work"))

    def test_normalise_keeps_hyphenated_compounds(self):
        self.assertEqual(content_guard.normalise("Stress-Check, B31.3"), "stress-check b31 3")

    def test_only_hashes_are_stored(self):
        with open(content_guard.__file__, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(sorted(set(len(h) for _n, h, *_ in content_guard._BANNED)), [64])
        self.assertNotIn("_BANNED_WORDS", text)


if __name__ == "__main__":
    unittest.main()
