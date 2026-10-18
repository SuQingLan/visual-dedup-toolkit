"""Retention policies: decide which file to keep in each duplicate/similar group.

Policies are composable: each policy receives a list of paths and returns
the path to keep (or None to defer to the next policy).
"""

from pathlib import Path
from typing import Callable, List, Optional

from PIL import Image


Policy = Callable[[List[Path]], Optional[Path]]
"""A retention policy receives a non-empty list of paths and returns
the path to keep, or None if the policy does not apply."""


def by_pixel_area(paths: List[Path]) -> Optional[Path]:
    """Keep the image with the largest pixel area (width * height).

    If multiple images have the same pixel area, returns None (defers to next policy).
    Exif orientation and transparency are NOT considered.

    Note: pixel area is not a quality score. A larger but blurry image
    may have more pixels than a smaller but sharper one.
    """
    areas: List[tuple[int, int, Path]] = []  # (area, index, path)
    max_area = -1
    count_max = 0

    for idx, path in enumerate(paths):
        try:
            with Image.open(path) as img:
                area = img.width * img.height
        except Exception:
            return None  # Can't determine pixel area, defer
        areas.append((area, idx, path))
        if area > max_area:
            max_area = area
            count_max = 1
        elif area == max_area:
            count_max += 1

    if count_max == 1:
        for area, _, path in areas:
            if area == max_area:
                return path

    return None  # Tie: defer to next policy


def by_file_size(paths: List[Path]) -> Optional[Path]:
    """Keep the largest file by byte size.

    Used as a deterministic fallback when pixel areas tie.
    """
    max_size = -1
    best: Optional[Path] = None
    tie = False

    for path in paths:
        try:
            size = path.stat().st_size
        except OSError:
            return None
        if size > max_size:
            max_size = size
            best = path
            tie = False
        elif size == max_size:
            tie = True

    return best if best and not tie else None


def first_alphabetical(paths: List[Path]) -> Optional[Path]:
    """Keep the first path in alphabetical order (absolute last-resort)."""
    return sorted(paths)[0]


def select_keep(paths: List[Path], policies: Optional[List[Policy]] = None) -> Path:
    """Apply chained retention policies to select which file to keep.

    Policies are tried in order. The first non-None result is used.
    If all policies defer, the first path in the list is kept.

    Args:
        paths: Non-empty list of candidate paths.
        policies: Ordered list of retention policies.
                  Defaults to [by_pixel_area, by_file_size, first_alphabetical].

    Returns:
        The path selected for retention.

    Raises:
        ValueError: If paths is empty.
    """
    if not paths:
        raise ValueError("Cannot select from empty path list")

    if policies is None:
        policies = [by_pixel_area, by_file_size, first_alphabetical]

    for policy in policies:
        result = policy(paths)
        if result is not None:
            return result

    return paths[0]