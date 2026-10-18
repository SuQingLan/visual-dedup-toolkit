"""Lightweight browser preview UI for deduplication results.

Shows duplicate/similar candidate groups with image thumbnails,
using only the Python standard library (no extra dependencies).
"""

import argparse
import base64
import io
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import quote, unquote

from PIL import Image


def _thumbnail_base64(path: Path, max_size: int = 200) -> str:
    """Create a small base64-encoded thumbnail for an image file."""
    try:
        with Image.open(path) as img:
            img.thumbnail((max_size, max_size))
            buf = io.BytesIO()
            img.convert('RGB').save(buf, format='JPEG', quality=75)
            return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ""


class PreviewHandler(BaseHTTPRequestHandler):
    root_dir = Path(".")
    report: dict = {}
    server_version = "VisualDedupPreview/0.1"

    def do_GET(self):  # noqa: N802
        if self.path == "/" or self.path == "/index.html":
            self._serve_page()
        elif self.path.startswith("/thumb/"):
            self._serve_thumb(self.path[len("/thumb/"):])
        else:
            self.send_error(404)

    def _serve_page(self):
        groups = self.report.get("exact_groups", []) + self.report.get("similar_groups", [])
        cards = []
        for idx, group in enumerate(groups):
            keep = group.get("keep", "")
            sims = group.get("similarities", {})
            sim_text = " / ".join(f"{k.split(' <-> ')[0].rsplit('/',1)[-1]}≈{v:.3f}"
                                  for k, v in list(sims.items())[:5])
            thumbs = []
            for candidate in group.get("candidates", []):
                thumb_url = f"/thumb/{quote(candidate)}"
                name = Path(candidate).name
                is_keep = (candidate == keep)
                thumbs.append(
                    f'<div class="thumb{" keep" if is_keep else ""}" title="{candidate}">'
                    f'<img src="{thumb_url}" alt="{name}"><div class="name">{name}'
                    f'{"<span class=tag>KEEP</span>" if is_keep else ""}</div></div>'
                )
            kind = "exact" if idx < len(self.report.get("exact_groups", [])) else "similar"
            cards.append(
                f'<div class="card {kind}"><h3>{kind} group #{idx+1} — keep: {Path(keep).name}</h3>'
                f'<p class="sim">{sim_text}</p><div class="thumbs">{"".join(thumbs)}</div></div>'
            )

        page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Visual Dedup Preview</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1000px; margin: 0 auto; padding: 24px; }}
.summary {{ display: flex; gap: 16px; margin-bottom: 24px; }}
.card {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
.card.exact {{ border-left: 4px solid #d32f2f; }}
.card.similar {{ border-left: 4px solid #f57c00; }}
.thumbs {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.thumb {{ border: 1px solid #eee; border-radius: 6px; padding: 6px; text-align: center; width: 150px; }}
.thumb.keep {{ border-color: #2e7d32; background: #e8f5e9; }}
.thumb img {{ max-width: 140px; max-height: 140px; }}
.thumb .name {{ font-size: 0.75em; color: #555; word-break: break-all; }}
.tag {{ background: #2e7d32; color: #fff; font-size: 0.7em; padding: 1px 5px; border-radius: 3px; margin-left: 4px; }}
.sim {{ font-size: 0.8em; color: #666; }}
</style></head><body>
<h1>Visual Dedup Preview</h1>
<p>{len(groups)} groups from <code>{self.root_dir}</code> — KEEP 标注为保留图片（按像素面积选择）</p>
<div class="summary">
<div>Total images: {self.report.get('total_images', 0)}</div>
<div>Exact groups: {self.report.get('exact_duplicate_groups', 0)}</div>
<div>Similar groups: {self.report.get('similar_groups', 0)}</div>
<div>Errors: {self.report.get('error_count', 0)}</div>
</div>
{"".join(cards) if cards else "<p>No duplicate or similar groups found.</p>"}
</body></html>"""
        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_thumb(self, rel_path: str):
        # URLs are percent-encoded (spaces, CJK paths); decode before filesystem access.
        decoded = unquote(rel_path)
        path = self.root_dir / decoded
        try:
            b64 = _thumbnail_base64(path)
        except Exception:
            b64 = ""
        if not b64:
            self.send_error(404)
            return
        data = base64.b64decode(b64)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[preview] {fmt % args}\n")


def main():
    parser = argparse.ArgumentParser(description="Preview deduplication results in a browser.")
    parser.add_argument("report", type=str, help="Path to report.json produced by visual-dedup.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", type=str, default=".",
                        help="Directory containing the scanned images (default: current dir).")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        return 1

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    PreviewHandler.report = report
    PreviewHandler.root_dir = Path(args.root).resolve()
    if not PreviewHandler.root_dir.is_dir():
        print(f"Invalid root directory: {args.root}")
        return 1

    server = HTTPServer(("127.0.0.1", args.port), PreviewHandler)
    print(f"Preview server: http://127.0.0.1:{args.port}")
    print(f"Report: {report_path}  |  Image root: {PreviewHandler.root_dir}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())