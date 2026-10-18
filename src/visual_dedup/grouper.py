"""Grouping logic: form duplicate and similar-image candidate groups."""

from pathlib import Path
from typing import Dict, List, Tuple

import imagehash

from .hashing import similarity


def group_exact_duplicates(md5_map: Dict[str, List[Path]]) -> List[List[Path]]:
    """Extract groups of exact duplicates (more than one file sharing a hash).

    Args:
        md5_map: Mapping from MD5 hex to list of paths.

    Returns:
        List of groups, each with 2+ files sharing the same MD5.
    """
    groups: List[List[Path]] = []
    for paths in md5_map.values():
        if len(paths) > 1:
            groups.append(list(paths))
    return groups


def group_similar(
    phash_map: Dict[Path, imagehash.ImageHash],
    threshold: float = 0.80,
) -> List[Tuple[List[Path], Dict[Tuple[Path, Path], float]]]:
    """Form similarity groups using pairwise perceptual hash comparison.

    Historical candidate grouping: each image leads at most one group;
    if image B is already in image A's group and A≈B, assign B to A's group.

    Args:
        phash_map: Mapping from path to ImageHash.
        threshold: Similarity threshold in (0, 1]. Strictly greater-than.

    Returns:
        List of (group_paths, pair_similarities), one per similarity group.
    """
    paths = list(phash_map)
    assigned: set = set()
    groups: List[Tuple[List[Path], Dict[Tuple[Path, Path], float]]] = []

    for path_a in paths:
        if path_a in assigned:
            continue
        group: List[Path] = [path_a]
        similarities: Dict[Tuple[Path, Path], float] = {}
        hash_a = phash_map[path_a]

        for path_b in paths:
            if path_b == path_a or path_b in assigned:
                continue
            hash_b = phash_map[path_b]
            sim = similarity(hash_a, hash_b)
            if sim > threshold:
                group.append(path_b)
                similarities[(path_a, path_b)] = sim

        if len(group) > 1:
            assigned.update(group)
            groups.append((group, similarities))

    return groups