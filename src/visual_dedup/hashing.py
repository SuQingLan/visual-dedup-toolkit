"""Image hashing: MD5 for exact duplicates, perceptual hash for similarity."""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import imagehash
from PIL import Image, ImageFile

# Allow loading truncated images and remove pixel limit for large images.
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None


def compute_md5(file_path: Path) -> str:
    """Compute MD5 hash of a file in streaming mode."""
    with open(file_path, 'rb') as stream:
        return hashlib.file_digest(stream, 'md5').hexdigest()


def compute_phash(
    file_path: Path,
    hash_size: int = 16,
    highfreq_factor: int = 8,
) -> imagehash.ImageHash:
    """Compute perceptual hash (pHash) of an image file.

    Args:
        file_path: Path to the image.
        hash_size: pHash size parameter (default 16 -> 256-bit hash).
        highfreq_factor: pHash high-frequency factor.

    Returns:
        An ImageHash object.

    Raises:
        Exception: If the image cannot be opened or processed.
    """
    with Image.open(file_path) as img:
        return imagehash.phash(img, hash_size=hash_size, highfreq_factor=highfreq_factor)


def similarity(hash_a: imagehash.ImageHash, hash_b: imagehash.ImageHash) -> float:
    """Compute normalized similarity between two perceptual hashes.

    Returns:
        Float in [0, 1], where 1 means identical hashes.
    """
    distance = hash_a - hash_b  # Hamming distance
    max_distance = hash_a.hash.size  # Total bits
    if max_distance == 0:
        return 1.0
    return 1.0 - distance / max_distance


def batch_md5(
    paths: List[Path],
    workers: int = 8,
    on_error: Optional[Callable[[Path, str], None]] = None,
    cancel_flag: Optional[Callable[[], bool]] = None,
) -> Tuple[Dict[str, List[Path]], List[Tuple[Path, str]]]:
    """Compute MD5 hashes for a batch of files.

    Args:
        paths: List of image file paths.
        workers: Number of threads.
        on_error: Optional callback for individual file errors.
        cancel_flag: Optional callable returning True to cancel.

    Returns:
        (md5_dict: mapping from hash -> list of paths, errors: list of (path, error_str))
    """
    md5_map: Dict[str, List[Path]] = {}
    errors: List[Tuple[Path, str]] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(compute_md5, p): p for p in paths}
        for future in as_completed(futures):
            if cancel_flag and cancel_flag():
                pool.shutdown(wait=False, cancel_futures=True)
                break
            path = futures[future]
            try:
                md5 = future.result()
                md5_map.setdefault(md5, []).append(path)
            except Exception as e:
                err_msg = f'{type(e).__name__}: {e}'
                errors.append((path, err_msg))
                if on_error:
                    on_error(path, err_msg)

    return md5_map, errors


def batch_phash(
    paths: List[Path],
    workers: int = 8,
    hash_size: int = 16,
    highfreq_factor: int = 8,
    on_error: Optional[Callable[[Path, str], None]] = None,
    cancel_flag: Optional[Callable[[], bool]] = None,
) -> Tuple[Dict[Path, imagehash.ImageHash], List[Tuple[Path, str]]]:
    """Compute perceptual hashes for a batch of image files.

    Args:
        paths: List of image file paths.
        workers: Number of threads.
        hash_size: pHash size parameter.
        highfreq_factor: pHash high-frequency factor.
        on_error: Optional callback for individual file errors.
        cancel_flag: Optional callable returning True to cancel.

    Returns:
        (phash_dict: mapping from path -> ImageHash, errors: list of (path, error_str))
    """
    phash_map: Dict[Path, imagehash.ImageHash] = {}
    errors: List[Tuple[Path, str]] = []

    def _task(p: Path):
        return p, compute_phash(p, hash_size, highfreq_factor)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_task, p): p for p in paths}
        for future in as_completed(futures):
            if cancel_flag and cancel_flag():
                pool.shutdown(wait=False, cancel_futures=True)
                break
            path = futures[future]
            try:
                _, phash = future.result()
                phash_map[path] = phash
            except Exception as e:
                err_msg = f'{type(e).__name__}: {e}'
                errors.append((path, err_msg))
                if on_error:
                    on_error(path, err_msg)

    return phash_map, errors