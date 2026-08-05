"""Split SOOP lower-banner source images into upload-sized PNG files."""

from __future__ import annotations

import os
import tempfile
from os import PathLike
from pathlib import Path
from typing import Final

from PIL import Image


ImageSize = tuple[int, int]
CropBox = tuple[int, int, int, int]

SUPPORTED_IMAGE_SIZES: Final[tuple[ImageSize, ...]] = (
    (720, 450),
    (1440, 450),
)

_CROP_BOXES: Final[dict[ImageSize, tuple[CropBox, ...]]] = {
    (720, 450): (
        (0, 0, 720, 150),
        (0, 150, 720, 300),
        (0, 300, 720, 450),
    ),
    (1440, 450): (
        (0, 0, 720, 150),
        (720, 0, 1440, 150),
        (0, 150, 720, 300),
        (720, 150, 1440, 300),
        (0, 300, 720, 450),
        (720, 300, 1440, 450),
    ),
}


class UnsupportedImageSizeError(ValueError):
    """Raised when an image does not exactly match a supported source size."""

    def __init__(self, actual_size: ImageSize) -> None:
        self.actual_size = actual_size
        self.supported_sizes = SUPPORTED_IMAGE_SIZES
        supported = ", ".join(f"{width}x{height}" for width, height in self.supported_sizes)
        super().__init__(
            f"Unsupported image size {actual_size[0]}x{actual_size[1]}; "
            f"expected one of: {supported}."
        )


class ExistingOutputError(FileExistsError):
    """Raised when cutting would replace one or more existing output paths."""

    def __init__(self, paths: tuple[Path, ...]) -> None:
        self.paths = paths
        path_list = ", ".join(str(path) for path in paths)
        super().__init__(f"Refusing to overwrite existing output path(s): {path_list}")


class UnsupportedMultiFrameImageError(ValueError):
    """Raised when an animated or otherwise multi-frame source is supplied."""

    def __init__(self, frame_count: int) -> None:
        self.frame_count = frame_count
        super().__init__(
            f"Multi-frame images are not supported; received {frame_count} frames."
        )


def _has_transparency(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info


def _existing_paths(paths: list[Path]) -> tuple[Path, ...]:
    return tuple(path for path in paths if path.exists())


def _stage_crop(
    image: Image.Image,
    box: CropBox,
    destination: Path,
    output_mode: str,
) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)

    cropped = image.crop(box)
    converted: Image.Image | None = None
    try:
        converted = cropped.convert(output_mode)
        converted.save(temporary_path, format="PNG")
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    finally:
        if converted is not None:
            converted.close()
        cropped.close()

    return temporary_path


def cut_image(
    source: str | PathLike[str],
    output_dir: str | PathLike[str],
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Cut a supported source image and return the generated PNG paths in order.

    A 720x450 source is cut into three vertical 720x150 sections. A 1440x450
    source is cut into six 720x150 sections in row-major order (left to right,
    then top to bottom). Existing results are protected unless ``overwrite``
    is explicitly enabled.
    """

    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Source image does not exist: {source_path}")
    if not source_path.is_file():
        raise IsADirectoryError(f"Source image is not a file: {source_path}")

    destination = Path(output_dir)

    with Image.open(source_path) as image:
        frame_count = getattr(image, "n_frames", 1)
        if frame_count != 1:
            raise UnsupportedMultiFrameImageError(frame_count)

        boxes = _CROP_BOXES.get(image.size)
        if boxes is None:
            raise UnsupportedImageSizeError(image.size)
        image.load()

        destination.mkdir(parents=True, exist_ok=True)

        output_paths = [
            destination / f"{source_path.stem}_{index}.png"
            for index in range(1, len(boxes) + 1)
        ]
        existing_paths = _existing_paths(output_paths)
        if existing_paths and not overwrite:
            raise ExistingOutputError(existing_paths)

        non_file_paths = tuple(
            path for path in existing_paths if not path.is_file()
        )
        if non_file_paths:
            raise ExistingOutputError(non_file_paths)

        output_mode = "RGBA" if _has_transparency(image) else "RGB"
        staged_paths: list[Path] = []
        try:
            for box, output_path in zip(boxes, output_paths, strict=True):
                staged_paths.append(
                    _stage_crop(image, box, output_path, output_mode)
                )

            # Check the full set again immediately before committing staged files.
            if not overwrite:
                existing_paths = _existing_paths(output_paths)
                if existing_paths:
                    raise ExistingOutputError(existing_paths)

            for staged_path, output_path in zip(
                staged_paths, output_paths, strict=True
            ):
                os.replace(staged_path, output_path)
        finally:
            for staged_path in staged_paths:
                staged_path.unlink(missing_ok=True)

    return output_paths
