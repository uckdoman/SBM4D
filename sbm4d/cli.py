"""Command-line entry point for SBM4D."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .batch import find_batch_output_conflicts, path_key
from .cutter import ExistingOutputError, UnsupportedImageSizeError, cut_image


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="SBM4D",
        description="SOOP 하단 배너 이미지를 규격에 맞게 분할합니다.",
    )
    parser.add_argument(
        "images",
        metavar="IMAGE",
        nargs="*",
        type=Path,
        help="분할할 원본 이미지 경로입니다. 여러 장을 지정할 수 있습니다.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="결과를 저장할 폴더입니다. 생략하면 각 원본 이미지 옆 output 폴더를 사용합니다.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="같은 이름의 결과 파일이 있으면 덮어씁니다.",
    )
    return parser


def default_output_dir(source: Path) -> Path:
    """Return the default result directory for *source*."""

    return source.expanduser().parent / "output"


def _run_batch(
    images: Sequence[Path],
    output: Path | None,
    *,
    overwrite: bool = False,
) -> int:
    assignments = [
        (source, output if output is not None else default_output_dir(source))
        for source in images
    ]
    conflicts = find_batch_output_conflicts(assignments)
    blocked_sources = {
        path_key(source)
        for conflict in conflicts
        for source in conflict.sources
    }
    failed = bool(conflicts)

    for conflict in conflicts:
        source_list = ", ".join(str(source) for source in conflict.sources)
        print(
            f"결과 이름이 겹쳐 처리하지 않습니다: '{conflict.stem}' "
            f"({source_list}). 원본 파일명을 서로 다르게 바꿔 주세요.",
            file=sys.stderr,
        )

    for source, destination in assignments:
        if path_key(source) in blocked_sources:
            continue
        try:
            generated = cut_image(source, destination, overwrite=overwrite)
        except UnsupportedImageSizeError as exc:
            failed = True
            print(f"지원하지 않는 이미지 규격입니다: {source} ({exc})", file=sys.stderr)
        except ExistingOutputError as exc:
            failed = True
            print(
                f"기존 결과 파일이 있어 건너뛰었습니다: {source} ({exc}) "
                "--overwrite 옵션을 사용하면 덮어쓸 수 있습니다.",
                file=sys.stderr,
            )
        except Exception as exc:
            failed = True
            print(f"이미지를 처리하지 못했습니다: {source} ({exc})", file=sys.stderr)
        else:
            for path in generated:
                print(path)

    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Start the GUI or process images supplied on the command line."""

    args = build_parser().parse_args(argv)
    if not args.images:
        from .gui import launch_gui

        launch_gui(output_dir=args.output)
        return 0

    return _run_batch(args.images, args.output, overwrite=args.overwrite)
