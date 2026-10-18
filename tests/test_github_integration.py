"""Tests for the GitHub API integration (no real network calls)."""

import json
import unittest
from unittest import mock


class TestGitHubIntegration(unittest.TestCase):
    def _sample_report(self) -> dict:
        return {
            "scan_time": "2026-10-18T12:00:00+00:00",
            "total_images": 6,
            "exact_duplicate_groups": 1,
            "similar_group_count": 1,
            "error_count": 1,
            "elapsed_seconds": 0.9,
            "exact_groups": [
                {
                    "keep": "/data/original.png",
                    "candidates": ["/data/original.png", "/data/duplicate.png"],
                }
            ],
            "similar_groups": [
                {
                    "group": ["/data/resized_128.png", "/data/resized_64.png"],
                    "keep": "/data/resized_128.png",
                    "similarities": {
                        "/data/resized_128.png <-> /data/resized_64.png": 0.984,
                    },
                }
            ],
            "errors": [
                {"path": "/data/corrupt.jpg", "message": "cannot identify image file"}
            ],
        }

    def test_get_token_from_env(self):
        from visual_dedup.github_integration import get_token
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "abc123"}, clear=False):
            self.assertEqual(get_token(), "abc123")

    def test_get_token_missing_returns_none(self):
        from visual_dedup.github_integration import get_token
        with mock.patch.dict("os.environ", {}, clear=False):
            self.assertIsNone(get_token())

    def test_build_issue_body_contains_summary(self):
        from visual_dedup.github_integration import build_issue_body
        body = build_issue_body(self._sample_report())
        self.assertIn("图片总数", body)
        self.assertIn("6", body)
        self.assertIn("完全重复组", body)
        self.assertIn("duplicate.png", body)
        self.assertIn("resized_128.png", body)
        self.assertIn("corrupt.jpg", body)
        self.assertIn("visual-dedup-toolkit", body)

    def test_issue_body_strips_absolute_paths(self):
        """Regression: public issue bodies must not leak local absolute paths."""
        from visual_dedup.github_integration import build_issue_body
        report = self._sample_report()
        report["exact_groups"][0]["candidates"] = [
            r"C:\Users\素质\secret\original.png",
            r"C:\Users\素质\secret\duplicate.png",
        ]
        report["errors"][0]["message"] = (
            "cannot identify image file 'C:\\Users\\素质\\secret\\corrupt.jpg'"
        )
        body = build_issue_body(report)
        self.assertNotIn("C:\\", body)
        self.assertNotIn("Users", body)
        self.assertIn("duplicate.png", body)
        self.assertIn("corrupt.jpg", body)

    def test_create_issue_makes_post_request(self):
        from visual_dedup import github_integration as gh

        captured = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"html_url": "https://github.com/x/y/issues/1"}).encode("utf-8")

        def fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = json.loads(req.data.decode("utf-8")) if req.data else None
            captured["auth"] = req.get_header("Authorization")
            return FakeResp()

        with mock.patch.object(gh.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = gh.create_issue("owner/repo", "Title", "Body", "tok123")

        self.assertEqual(captured["url"], "https://api.github.com/repos/owner/repo/issues")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["auth"], "Bearer tok123")
        self.assertEqual(captured["body"]["title"], "Title")
        self.assertEqual(result["html_url"], "https://github.com/x/y/issues/1")

    def test_create_issue_http_error(self):
        import urllib.error
        from visual_dedup.github_integration import GitHubAPIError, create_issue

        class FakeHTTPError(urllib.error.HTTPError):
            def __init__(self, code, msg, fp=None, headers=None):
                super().__init__("https://api.github.com/repos/o/r/issues", code, msg,
                                 headers or {}, fp or None)

            def read(self):
                return b'{"message": "Resource not accessible"}'

        with mock.patch.object(
            urllib.request, "urlopen",
            side_effect=FakeHTTPError(403, "Forbidden"),
        ):
            with self.assertRaises(GitHubAPIError) as ctx:
                create_issue("owner/repo", "t", "b", "tok")
        self.assertIn("403", str(ctx.exception))

    def test_submit_dedup_issue_title(self):
        from visual_dedup.github_integration import submit_dedup_issue
        with mock.patch(
            "visual_dedup.github_integration.create_issue",
            return_value={"html_url": "https://example.com/i"},
        ) as m:
            submit_dedup_issue("owner/repo", self._sample_report(), "tok")
        title = m.call_args[0][1]
        self.assertIn("6 images", title)
        self.assertIn("1 exact", title)
        self.assertIn("1 similar", title)


if __name__ == "__main__":
    unittest.main()