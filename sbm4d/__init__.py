"""Public API for SBM4D image cutting."""

from .cutter import (
    ExistingOutputError,
    UnsupportedImageSizeError,
    UnsupportedMultiFrameImageError,
    cut_image,
)

__all__ = [
    "ExistingOutputError",
    "UnsupportedImageSizeError",
    "UnsupportedMultiFrameImageError",
    "cut_image",
]
