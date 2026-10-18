"""Safe file organization: copy, move, with collision avoidance and source protection."""

import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple


class OrganizeError(Exception):
    """Raised when a file organization operation fails."""
    pass


def _safe_target(source: Path, destination_dir: Path) -> Path:
    """Generate a unique target path in destination_dir, never overwriting existing files.

    Appends (N) to the stem if a collision is detected.
    """
    os.makedirs(destination_dir, exist_ok=True)
    stem = source.stem
    suffix = source.suffix
    target = destination_dir / f"{stem}{suffix}"

    counter = 1
    while target.exists():
        target = destination_dir / f"{stem} ({counter}){suffix}"
        counter += 1

    return target


def copy_file(source: Path, destination_dir: Path) -> Path:
    """Copy a file to destination_dir, never overwriting existing files.

    Returns the actual target path.
    Raises OrganizeError on failure. Source is never modified.
    """
    target = _safe_target(source, destination_dir)
    try:
        shutil.copy2(source, target)
    except Exception as e:
        raise OrganizeError(f"Copy failed: {source} -> {target}: {e}") from e
    return target


def move_file(source: Path, destination_dir: Path) -> Path:
    """Move a file to destination_dir, never overwriting existing files.

    On failure (including partial copy), the source file is preserved.
    For cross-volume moves, copies first then deletes source only after copy succeeds.
    Returns the actual target path.
    Raises OrganizeError on failure.
    """
    target = _safe_target(source, destination_dir)

    same_volume = os.path.splitdrive(str(source))[0].lower() == \
                  os.path.splitdrive(str(target))[0].lower()

    if same_volume:
        try:
            os.rename(source, target)
        except OSError:
            # Fall back to copy+delete on rename failure
            same_volume = False

    if not same_volume:
        # Copy first, delete only after successful copy
        tmp_target = target
        try:
            with open(source, 'rb') as src, open(tmp_target, 'xb') as dst:
                shutil.copyfileobj(src, dst)
            shutil.copystat(source, tmp_target)
            os.unlink(source)
        except Exception as e:
            # Clean up partial copy, preserve source
            if tmp_target.exists() and tmp_target != target:
                try:
                    tmp_target.unlink()
                except Exception:
                    pass
            raise OrganizeError(f"Move failed: {source} -> {target}: {e}") from e

    return target


class OperationPlan:
    """Records planned file operations before execution, supporting preview."""

    def __init__(self):
        self.actions: List[Tuple[str, Path, Path]] = []  # (action, source, destination_dir)

    def add_copy(self, source: Path, destination_dir: Path):
        self.actions.append(("copy", source, destination_dir))

    def add_move(self, source: Path, destination_dir: Path):
        self.actions.append(("move", source, destination_dir))

    def add_keep(self, source: Path):
        self.actions.append(("keep", source, Path(".")))

    def preview(self) -> str:
        """Return a human-readable preview of all planned actions."""
        lines = [f"Operation Plan ({len(self.actions)} actions):"]
        for action, source, dest in self.actions:
            if action == "keep":
                lines.append(f"  [KEEP]  {source}")
            elif action == "copy":
                lines.append(f"  [COPY]  {source} -> {dest}")
            elif action == "move":
                lines.append(f"  [MOVE]  {source} -> {dest}")
        return "\n".join(lines)

    def execute(self) -> List[Tuple[str, Path, Path, Optional[str]]]:
        """Execute all planned actions sequentially.

        Returns:
            List of (action, source, target, error_message_or_None) for each action.
            Actions after a failure continue to execute.
        """
        results: List[Tuple[str, Path, Path, Optional[str]]] = []
        for action, source, dest_dir in self.actions:
            if action == "keep":
                results.append(("keep", source, source, None))
                continue
            try:
                if action == "copy":
                    target = copy_file(source, dest_dir)
                elif action == "move":
                    target = move_file(source, dest_dir)
                else:
                    results.append((action, source, dest_dir, f"Unknown action: {action}"))
                    continue
                results.append((action, source, target, None))
            except OrganizeError as e:
                results.append((action, source, dest_dir, str(e)))
            except Exception as e:
                results.append((action, source, dest_dir, f"{type(e).__name__}: {e}"))
        return results