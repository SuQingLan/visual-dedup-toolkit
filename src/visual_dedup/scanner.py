"""File discovery for image deduplication."""

import os
from pathlib import Path
from typing import List, Set


SUPPORTED_EXTENSIONS: Set[str] = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}


def discover_images(
    root: str,
    extensions: Set[str] | None = None,
    exclude_dirs: List[str] | None = None,
) -> List[Path]:
    """Recursively discover image files under root, excluding specified directories.

    Args:
        root: Root directory to scan.
        extensions: Lowercase file extensions to include. Defaults to SUPPORTED_EXTENSIONS.
        exclude_dirs: Directory names whose subtrees are excluded (case-insensitive on Windows).

    Returns:
        Sorted list of absolute Path objects.
    """
    if extensions is None:
        extensions = SUPPORTED_EXTENSIONS

    root_path = Path(root).resolve()
    exclude_norm: Set[str] = set()
    if exclude_dirs:
        exclude_norm = {os.path.normcase(os.path.join(root_path, d)) for d in exclude_dirs}

    result: List[Path] = []
    for folder, dirs, files in os.walk(root_path):
        # Prune excluded directories
        dirs[:] = [
            d for d in dirs
            if os.path.normcase(os.path.join(folder, d)) not in exclude_norm
        ]
        for name in sorted(files):
            if Path(name).suffix.lower() in extensions:
                result.append(Path(folder) / name)

    return result