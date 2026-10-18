"""Tests for the report generation module."""

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


class TestReporter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_groups(self):
        """Create paths with a known exact + similar structure."""
        a1 = self.root / 'a1.png'
        a2 = self.root / 'a2.png'
        b1 = self.root / 'b1.png'
        b2 = self.root / 'b2.png'
        for p in (a1, a2, b1, b2):
            Image.new('RGB', (32, 32), 'red').save(p)
        return ([a1, a2], [b1, b2])

    def test_report_json_keys_and_counts(self):
        """Regression: similar count must not be shadowed by the similar array.

        Previously the JSON used the same key 'similar_groups' for both the
        integer count and the array of groups, so the count was lost.
        """
        from visual_dedup.reporter import generate_json_report

        exact, similar = self._make_groups()
        b1, b2 = similar
        # Build similar group structure like grouper.output
        similar_with_sims = [([b1, b2], {(b1, b2): 0.95})]

        report = generate_json_report(
            total_images=4,
            exact_groups=[exact],
            similar_groups=similar_with_sims,
            keep_map={str(p): str(exact[0]) for p in exact}
                     | {str(p): str(similar[0]) for p in similar},
            errors=[],
            elapsed=1.0,
        )

        # Counts are integers
        self.assertEqual(report['exact_duplicate_groups'], 1)
        self.assertEqual(report['similar_group_count'], 1)
        self.assertIsInstance(report['similar_group_count'], int)
        # Arrays exist separately
        self.assertIsInstance(report['exact_groups'], list)
        self.assertIsInstance(report['similar_groups'], list)
        self.assertEqual(len(report['similar_groups']), 1)
        self.assertEqual(len(report['exact_groups']), 1)

    def test_report_written_to_disk(self):
        from visual_dedup.reporter import generate_json_report
        exact, _ = self._make_groups()
        out = self.root / 'out' / 'report.json'
        report = generate_json_report(
            total_images=2,
            exact_groups=[exact],
            similar_groups=[],
            keep_map={str(p): str(exact[0]) for p in exact},
            errors=[],
            elapsed=0.5,
            output_path=out,
        )
        self.assertTrue(out.exists())
        with open(out, encoding='utf-8') as f:
            loaded = json.load(f)
        self.assertEqual(loaded['total_images'], 2)
        self.assertEqual(loaded['similar_group_count'], 0)


if __name__ == '__main__':
    unittest.main()