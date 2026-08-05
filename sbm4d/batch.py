"""Shared preflight checks for multi-image SBM4D jobs."""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BatchOutputConflict:
    """Inputs whose generated PNG names would overlap in one output folder."""

    output_dir: Path
    stem: str
    sources: tuple[Path, ...]


def path_key(path: Path) -> str:
    """Return a stable, case-insensitive key for a Windows-oriented path."""

    resolved = path.expanduser().resolve(strict=False)
    return os.path.normcase(str(resolved)).casefold()


def find_batch_output_conflicts(
    assignments: Iterable[tuple[Path, Path]],
) -> tuple[BatchOutputConflict, ...]:
    """Find source names that would generate overlapping result paths."""

    grouped: dict[tuple[str, str], list[tuple[Path, Path]]] = defaultdict(list)
    for source, output_dir in assignments:
        source_path = Path(source)
        destination = Path(output_dir)
        grouped[(path_key(destination), source_path.stem.casefold())].append(
            (source_path, destination)
        )

    conflicts: list[BatchOutputConflict] = []
    for key in sorted(grouped):
        items = grouped[key]
        if len(items) < 2:
            continue
        conflicts.append(
            BatchOutputConflict(
                output_dir=items[0][1],
                stem=items[0][0].stem,
                sources=tuple(source for source, _ in items),
            )
        )
    return tuple(conflicts)
