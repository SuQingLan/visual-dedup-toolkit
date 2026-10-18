"""GitHub API integration for visual-dedup-toolkit.

Submit deduplication scan summaries as issues on GitHub using the REST API.
Uses only the Python standard library (urllib), no extra dependencies.

The token is read from the GITHUB_TOKEN environment variable and is
never logged or written into any report.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    """Raised when the GitHub API call fails."""


def get_token(env_var: str = "GITHUB_TOKEN") -> Optional[str]:
    """Read a GitHub token from the environment. Never returns a default value."""
    return os.environ.get(env_var) or None


def _request(
    method: str,
    url: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Perform a GitHub API request with bearer authentication."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "visual-dedup-toolkit/0.1.0",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            data = json.loads(e.read().decode("utf-8"))
            detail = data.get("message", "")
        except Exception:
            pass
        finally:
            # Close the error response stream to avoid leaking file handles.
            try:
                e.close()
            except Exception:
                pass
        raise GitHubAPIError(f"GitHub API {e.code}: {detail or e.reason}") from e
    except urllib.error.URLError as e:
        raise GitHubAPIError(f"Network error: {e.reason}") from e


def create_issue(
    repo: str,
    title: str,
    body: str,
    token: str,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create an issue in the given repository."""
    payload: Dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    return _request(
        "POST",
        f"{API_BASE}/repos/{urllib.parse.quote(repo)}/issues",
        token,
        payload,
    )


def _public_name(path: str) -> str:
    """Strip a local path to its basename for public issue bodies.

    Never leak local absolute paths (e.g. C:\\Users\\...) into a public repo.
    """
    return str(path).replace("\\", "/").rsplit("/", 1)[-1]


def build_issue_body(report: Dict[str, Any]) -> str:
    """Build a Markdown issue body summarizing a deduplication scan."""
    stamp = report.get("scan_time", "")
    total = report.get("total_images", 0)
    exact_count = report.get("exact_duplicate_groups", 0)
    similar_count = report.get("similar_group_count", 0)
    error_count = report.get("error_count", 0)

    lines = [
        "## 查重摘要（自动生成）",
        "",
        f"- **扫描时间**: {stamp}",
        f"- **图片总数**: {total}",
        f"- **完全重复组**: {exact_count}",
        f"- **相似组**: {similar_count}",
        f"- **错误文件数**: {error_count}",
        "",
    ]

    exact_groups = report.get("exact_groups", [])
    if exact_groups:
        lines.append("## 完全重复组")
        lines.append("")
        for i, g in enumerate(exact_groups, 1):
            keep = _public_name(g.get("keep", ""))
            candidates = [_public_name(c) for c in g.get("candidates", [])]
            lines.append(f"### 组 {i}（保留 `{keep}`）")
            lines.append("")
            lines.append("- " + "\n- ".join(f"`{c}`" for c in candidates))
            lines.append("")

    similar_groups = report.get("similar_groups", [])
    if similar_groups:
        lines.append("## 相似组")
        lines.append("")
        for i, g in enumerate(similar_groups, 1):
            keep = _public_name(g.get("keep", ""))
            group = [_public_name(p) for p in g.get("group", [])]
            sims = g.get("similarities", {})
            sim_text = "; ".join(
                f"{_public_name(k)}≈{v:.3f}" for k, v in list(sims.items())[:3]
            )
            lines.append(f"### 组 {i}（保留 `{keep}`）")
            lines.append("")
            lines.append("- " + "\n- ".join(f"`{c}`" for c in group))
            if sim_text:
                lines.append(f"\n相似度：{sim_text}")
            lines.append("")

    errors = report.get("errors", [])
    if errors:
        lines.append("## 错误文件")
        lines.append("")
        lines.append("- " + "\n- ".join(
            f"`{_public_name(e['path'])}`: {e['message']}" for e in errors[:20]
        ))
        if len(errors) > 20:
            lines.append(f"\n（共 {len(errors)} 个，以上仅显示前 20 个）")
        lines.append("")

    lines.append(
        "---\n*本 Issue 由 `visual-dedup-toolkit` 自动生成。"
        "使用 `--gh-repo owner/repo --gh-token <env:GITHUB_TOKEN>` 复现。*"
    )
    return "\n".join(lines)


def submit_dedup_issue(
    repo: str,
    report: Dict[str, Any],
    token: str,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a deduplication summary issue for a repository."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = (
        f"[visual-dedup] {report.get('total_images', 0)} images, "
        f"{report.get('exact_duplicate_groups', 0)} exact, "
        f"{report.get('similar_group_count', 0)} similar ({stamp})"
    )
    body = build_issue_body(report)
    return create_issue(repo, title, body, token, labels=labels)