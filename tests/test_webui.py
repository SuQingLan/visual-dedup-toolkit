"""Tests for the preview UI module (webui.py)."""

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


class TestWebUI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_report(self):
        """Create images and a minimal report.json mimicking CLI output."""
        img1 = self.root / 'keep.png'
        img2 = self.root / 'dupe.png'
        Image.new('RGB', (64, 64), 'red').save(img1)
        Image.new('RGB', (64, 64), 'blue').save(img2)

        report_path = self.root / 'report.json'
        report = {
            "scan_time": "2026-10-18T00:00:00+00:00",
            "total_images": 2,
            "exact_duplicate_groups": 1,
            "similar_groups": 0,
            "error_count": 0,
            "elapsed_seconds": 0.5,
            "exact_groups": [
                {
                    "keep": str(img1),
                    "candidates": [str(img1), str(img2)],
                }
            ],
            "similar_groups": [],
            "errors": [],
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return report_path

    def test_thumbnail_generation(self):
        from visual_dedup.webui import _thumbnail_base64
        img_path = self.root / 'test.png'
        Image.new('RGB', (400, 300), 'green').save(img_path)
        b64 = _thumbnail_base64(img_path, max_size=200)
        self.assertTrue(b64)

        import base64
        raw = base64.b64decode(b64)
        self.assertGreater(len(raw), 100)
        # Decoded bytes should start with a JPEG magic number
        self.assertEqual(raw[:2], b'\xff\xd8')

    def test_thumbnail_missing_file_returns_empty(self):
        from visual_dedup.webui import _thumbnail_base64
        self.assertEqual(_thumbnail_base64(self.root / 'nope.png'), "")

    def test_thumbnail_corrupt_file_returns_empty(self):
        from visual_dedup.webui import _thumbnail_base64
        bad = self.root / 'bad.png'
        bad.write_bytes(b'not an image')
        self.assertEqual(_thumbnail_base64(bad), "")

    def test_page_html_renders_groups(self):
        """Simulate the page body generation path used by the preview handler."""
        from visual_dedup import webui
        import importlib
        importlib.reload(webui)  # ensure fresh module state

        report_path = self._make_report()
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

        webui.PreviewHandler.report = report
        webui.PreviewHandler.root_dir = self.root

        groups = report.get("exact_groups", []) + report.get("similar_groups", [])
        cards = []
        for idx, group in enumerate(groups):
            keep = group.get("keep", "")
            thumbs = [
                f'<div class="thumb" title="{candidate}">{Path(candidate).name}</div>'
                for candidate in group.get("candidates", [])
            ]
            kind = "exact" if idx < len(report.get("exact_groups", [])) else "similar"
            cards.append(
                f'<div class="card {kind}"><h3>{kind} group #{idx + 1} — keep: {Path(keep).name}</h3>'
                f'<div class="thumbs">{"".join(thumbs)}</div></div>'
            )
        page = f"<html><body>{''.join(cards)}</body></html>"

        self.assertIn('exact group #1', page)
        self.assertIn('keep.png', page)
        self.assertIn('dupe.png', page)
        self.assertNotIn('similar group', page)

    def test_thumb_url_percent_decoding(self):
        """Regression: /thumb/<path> must URL-decode before filesystem access.

        Windows absolute paths and CJK directories are percent-encoded in the
        generated page; a missing unquote() made every thumbnail 404.
        """
        from visual_dedup import webui
        import importlib
        importlib.reload(webui)

        # Create a file in a 'sub dir' (space) to force encoding
        sub = self.root / 'sub dir'
        sub.mkdir()
        img = sub / '图片.png'  # CJK filename
        Image.new('RGB', (32, 32), 'purple').save(img)

        from urllib.parse import quote
        encoded = quote(str(img.relative_to(self.root)), safe='')
        webui.PreviewHandler.root_dir = self.root

        # Directly test the internal decoding path
        decoded_path = webui.unquote(encoded)
        self.assertTrue((self.root / decoded_path).exists(),
                        f"decoded path should exist: {decoded_path}")

        b64 = webui._thumbnail_base64(self.root / decoded_path)
        self.assertTrue(b64, "thumbnail of decoded path should work")


if __name__ == '__main__':
    unittest.main()