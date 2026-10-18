"""Report generation: JSON and HTML results for deduplication scans."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def generate_json_report(
    total_images: int,
    exact_groups: List[List[Path]],
    similar_groups: List[Tuple[List[Path], Dict[Tuple[Path, Path], float]]],
    keep_map: Dict[str, str],
    errors: List[Tuple[Path, str]],
    elapsed: float,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate a structured JSON report of deduplication results.

    Args:
        total_images: Total images scanned.
        exact_groups: Groups of exact duplicates.
        similar_groups: Groups of similar images with pairwise similarities.
        keep_map: Mapping from candidate path -> keep path.
        errors: List of (path, error_message) for failed files.
        elapsed: Scan duration in seconds.
        output_path: If provided, write the report to this file.

    Returns:
        The report as a dict.
    """
    report: Dict[str, Any] = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "total_images": total_images,
        "exact_duplicate_groups": len(exact_groups),
        "similar_groups": len(similar_groups),
        "error_count": len(errors),
        "elapsed_seconds": round(elapsed, 4),
        "exact_groups": [
            {
                "keep": keep_map.get(str(group[0]), str(group[0])),
                "candidates": [str(p) for p in group],
            }
            for group in exact_groups
        ],
        "similar_groups": [
            {
                "group": [str(p) for p in group],
                "keep": keep_map.get(str(group[0]), str(group[0])),
                "similarities": {
                    f"{str(a)} <-> {str(b)}": round(sim, 6)
                    for (a, b), sim in sims.items()
                },
            }
            for group, sims in similar_groups
        ],
        "errors": [
            {"path": str(p), "message": msg} for p, msg in errors
        ],
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def generate_html_report(report: Dict[str, Any]) -> str:
    """Generate a self-contained HTML report from scan results.

    Args:
        report: The dict from generate_json_report.

    Returns:
        HTML string.
    """
    exact_html = ""
    for g in report.get("exact_groups", []):
        items = "\n".join(f"<li>{p}</li>" for p in g["candidates"])
        exact_html += f"""<div class="group">
<h3>Exact Duplicates (keep: {g['keep']})</h3><ul>{items}</ul></div>"""

    similar_html = ""
    for g in report.get("similar_groups", []):
        items = "\n".join(f"<li>{p}</li>" for p in g["group"])
        sims = "<br>".join(f"{k}: {v:.4f}" for k, v in g["similarities"].items())
        similar_html += f"""<div class="group">
<h3>Similar Group (keep: {g['keep']})</h3><p>{sims}</p><ul>{items}</ul></div>"""

    errors_html = ""
    for e in report.get("errors", []):
        errors_html += f"<li>{e['path']}: {e['message']}</li>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Visual Dedup Report</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 0 auto; padding: 24px; }}
.summary {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
.card {{ background: #f5f5f5; border-radius: 8px; padding: 16px; min-width: 140px; }}
.card .label {{ font-size: 0.85em; color: #666; }}
.card .value {{ font-size: 1.8em; font-weight: bold; }}
.group {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
.group h3 {{ margin-top: 0; }}
.group ul {{ margin: 8px 0; }}
.errors {{ margin-top: 24px; }}
</style>
</head>
<body>
<h1>Visual Dedup Scan Report</h1>
<p>{report['scan_time']} | {report['elapsed_seconds']}s</p>
<div class="summary">
  <div class="card"><div class="label">Images</div><div class="value">{report['total_images']}</div></div>
  <div class="card"><div class="label">Exact Groups</div><div class="value">{report['exact_duplicate_groups']}</div></div>
  <div class="card"><div class="label">Similar Groups</div><div class="value">{report['similar_groups']}</div></div>
  <div class="card"><div class="label">Errors</div><div class="value">{report['error_count']}</div></div>
</div>
{exact_html}
{similar_html}
<div class="errors"><h2>Errors</h2><ul>{errors_html}</ul></div>
</body>
</html>"""