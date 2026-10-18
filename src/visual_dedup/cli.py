"""Command-line interface for visual-dedup-toolkit."""

import argparse
import time
from pathlib import Path
from typing import List

from .scanner import discover_images, SUPPORTED_EXTENSIONS
from .hashing import batch_md5, batch_phash
from .grouper import group_exact_duplicates, group_similar
from .selector import select_keep
from .reporter import generate_json_report, generate_html_report
from .organizer import OperationPlan


def main(args: List[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Visual similarity image deduplication and safe organization tool."
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Root directory to scan for images.",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="dedup-report",
        help="Output directory for reports (default: dedup-report).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.80,
        help="Similarity threshold (0-1, default: 0.80).",
    )
    parser.add_argument(
        "--hash-size",
        type=int,
        default=16,
        help="pHash size parameter (default: 16).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of worker threads (default: 8).",
    )
    parser.add_argument(
        "--extensions",
        type=str,
        nargs="+",
        help="Image extensions to scan (default: jpg jpeg png bmp gif tiff webp).",
    )
    parser.add_argument(
        "--move-duplicates",
        type=str,
        default=None,
        help="Move duplicate candidates to this directory (enables write operations).",
    )
    parser.add_argument(
        "--move-similar",
        type=str,
        default=None,
        help="Move similar candidates to this directory (enables write operations).",
    )
    parser.add_argument(
        "--copy-duplicates",
        type=str,
        default=None,
        help="Copy duplicate candidates to this directory (enables write operations).",
    )
    parser.add_argument(
        "--copy-similar",
        type=str,
        default=None,
        help="Copy similar candidates to this directory (enables write operations).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview operations without executing (default).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually execute file operations. Use with caution!",
    )

    opts = parser.parse_args(args)

    extensions = set(opts.extensions) if opts.extensions else SUPPORTED_EXTENSIONS
    root = Path(opts.directory).resolve()
    output_dir = Path(opts.output).resolve()

    if not root.is_dir():
        print(f"Error: '{root}' is not a valid directory.")
        return 1

    print(f"Scanning: {root}")
    started = time.monotonic()

    # Phase 1: Discover images
    images = discover_images(str(root), extensions=extensions, exclude_dirs=[str(output_dir)])
    print(f"Found {len(images)} images.")

    if not images:
        print("No images found.")
        return 0

    # Phase 2: MD5 hashing
    print("Computing MD5 hashes...")
    md5_map, md5_errors = batch_md5(images, workers=opts.workers)

    # Phase 3: Exact duplicate groups
    exact_groups = group_exact_duplicates(md5_map)
    print(f"Exact duplicate groups: {len(exact_groups)}")

    # Select one representative per MD5 group for pHash.
    # Sort for determinism: which file represents a duplicate group
    # must not depend on thread completion order.
    representatives = [sorted(paths)[0] for paths in md5_map.values()]

    # Phase 4: Perceptual hashing
    print("Computing perceptual hashes...")
    phash_map, phash_errors = batch_phash(
        representatives, workers=opts.workers,
        hash_size=opts.hash_size,
    )

    # Phase 5: Similar groups
    similar_groups = group_similar(phash_map, threshold=opts.threshold)
    print(f"Similar groups: {len(similar_groups)}")

    # Phase 6: Select keep files
    keep_map = {}
    for group in exact_groups:
        keep = select_keep(group)
        for p in group:
            keep_map[str(p)] = str(keep)

    for group, _ in similar_groups:
        keep = select_keep(group)
        for p in group:
            keep_map[str(p)] = str(keep)

    # Phase 7: Plan operations
    plan = OperationPlan()
    for group in exact_groups:
        keep = Path(keep_map[str(group[0])])
        for p in group:
            if p != keep:
                if opts.move_duplicates:
                    plan.add_move(p, Path(opts.move_duplicates))
                elif opts.copy_duplicates:
                    plan.add_copy(p, Path(opts.copy_duplicates))
                else:
                    plan.add_keep(p)
            else:
                plan.add_keep(p)

    for group, _ in similar_groups:
        keep = Path(keep_map[str(group[0])])
        for p in group:
            if p != keep:
                if opts.move_similar:
                    plan.add_move(p, Path(opts.move_similar))
                elif opts.copy_similar:
                    plan.add_copy(p, Path(opts.copy_similar))
                else:
                    plan.add_keep(p)
            else:
                plan.add_keep(p)

    elapsed = time.monotonic() - started

    # Phase 8: Report
    all_errors = [(Path(p), msg) for p, msg in md5_errors + phash_errors]
    report = generate_json_report(
        total_images=len(images),
        exact_groups=exact_groups,
        similar_groups=similar_groups,
        keep_map=keep_map,
        errors=all_errors,
        elapsed=elapsed,
        output_path=output_dir / "report.json",
    )

    html = generate_html_report(report)
    (output_dir / "report.html").write_text(html, encoding="utf-8")

    # Phase 9: Execute or preview
    if opts.execute:
        results = plan.execute()
        success = sum(1 for _, _, _, err in results if err is None)
        failed = len(results) - success
        print(f"\nExecution: {success} succeeded, {failed} failed.")
        for action, src, dst, err in results:
            if err:
                print(f"  [{action}] FAILED: {src} -> {dst}: {err}")
            else:
                print(f"  [{action}] {src} -> {dst}")
    else:
        print("\n" + plan.preview())
        print("\n(Dry run — use --execute to apply operations)")

    print(f"\nReport saved to: {output_dir}")
    print(f"Elapsed: {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())