from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from sbm4d import (
    ExistingOutputError,
    UnsupportedImageSizeError,
    UnsupportedMultiFrameImageError,
    cut_image,
)


class CutImageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.root = Path(self._temporary_directory.name)

    @staticmethod
    def _create_sectioned_image(
        path: Path,
        size: tuple[int, int],
        boxes: tuple[tuple[int, int, int, int], ...],
        colors: tuple[tuple[int, ...], ...],
        mode: str,
    ) -> None:
        image = Image.new(mode, size)
        try:
            for box, color in zip(boxes, colors, strict=True):
                image.paste(color, box)
            image.save(path)
        finally:
            image.close()

    def assert_uniform_image(
        self,
        path: Path,
        expected_color: tuple[int, ...],
        expected_mode: str,
    ) -> None:
        with Image.open(path) as image:
            image.load()
            self.assertEqual((720, 150), image.size)
            self.assertEqual(expected_mode, image.mode)
            self.assertEqual(
                [(720 * 150, expected_color)],
                image.getcolors(maxcolors=720 * 150),
            )

    def test_cuts_720x450_into_three_top_to_bottom_pngs(self) -> None:
        source = self.root / "small.banner.png"
        output_dir = self.root / "generated" / "small"
        boxes = (
            (0, 0, 720, 150),
            (0, 150, 720, 300),
            (0, 300, 720, 450),
        )
        colors = ((255, 0, 0), (0, 255, 0), (0, 0, 255))
        self._create_sectioned_image(source, (720, 450), boxes, colors, "RGB")

        result = cut_image(source, output_dir)

        expected_paths = [
            output_dir / f"small.banner_{index}.png" for index in range(1, 4)
        ]
        self.assertTrue(output_dir.is_dir())
        self.assertEqual(expected_paths, result)
        for path, color in zip(result, colors, strict=True):
            self.assertTrue(path.is_file())
            self.assert_uniform_image(path, color, "RGB")

    def test_cuts_1440x450_left_to_right_then_top_to_bottom(self) -> None:
        source = self.root / "large.png"
        output_dir = self.root / "generated" / "large"
        boxes = (
            (0, 0, 720, 150),
            (720, 0, 1440, 150),
            (0, 150, 720, 300),
            (720, 150, 1440, 300),
            (0, 300, 720, 450),
            (720, 300, 1440, 450),
        )
        colors = (
            (255, 0, 0, 255),
            (0, 255, 0, 224),
            (0, 0, 255, 192),
            (255, 255, 0, 160),
            (255, 0, 255, 128),
            (0, 255, 255, 96),
        )
        self._create_sectioned_image(source, (1440, 450), boxes, colors, "RGBA")
        original_source = source.read_bytes()

        result = cut_image(source, output_dir)

        self.assertEqual(original_source, source.read_bytes())
        self.assertEqual(
            [output_dir / f"large_{index}.png" for index in range(1, 7)],
            result,
        )
        for path, color in zip(result, colors, strict=True):
            self.assert_uniform_image(path, color, "RGBA")

    def test_rejects_unsupported_exact_pixel_size(self) -> None:
        source = self.root / "wrong-size.png"
        output_dir = self.root / "should-not-exist"
        image = Image.new("RGB", (720, 449))
        try:
            image.save(source)
        finally:
            image.close()

        with self.assertRaises(UnsupportedImageSizeError) as raised:
            cut_image(source, output_dir)

        self.assertEqual((720, 449), raised.exception.actual_size)
        self.assertEqual(((720, 450), (1440, 450)), raised.exception.supported_sizes)
        self.assertFalse(output_dir.exists())

    def test_rejects_a_missing_source(self) -> None:
        with self.assertRaises(FileNotFoundError):
            cut_image(self.root / "missing.png", self.root / "output")

    def test_preflights_every_output_before_refusing_overwrite(self) -> None:
        source = self.root / "protected.png"
        output_dir = self.root / "output"
        output_dir.mkdir()
        boxes = (
            (0, 0, 720, 150),
            (0, 150, 720, 300),
            (0, 300, 720, 450),
        )
        colors = ((10, 20, 30), (40, 50, 60), (70, 80, 90))
        self._create_sectioned_image(source, (720, 450), boxes, colors, "RGB")
        existing_path = output_dir / "protected_2.png"
        existing_path.write_bytes(b"keep this file")

        with self.assertRaises(ExistingOutputError) as raised:
            cut_image(source, output_dir)

        self.assertEqual((existing_path,), raised.exception.paths)
        self.assertEqual(b"keep this file", existing_path.read_bytes())
        self.assertFalse((output_dir / "protected_1.png").exists())
        self.assertFalse((output_dir / "protected_3.png").exists())

    def test_overwrite_replaces_all_existing_outputs(self) -> None:
        source = self.root / "replace.png"
        output_dir = self.root / "output"
        boxes = (
            (0, 0, 720, 150),
            (0, 150, 720, 300),
            (0, 300, 720, 450),
        )
        first_colors = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
        replacement_colors = ((91, 92, 93), (94, 95, 96), (97, 98, 99))
        self._create_sectioned_image(
            source, (720, 450), boxes, first_colors, "RGB"
        )
        cut_image(source, output_dir)
        self._create_sectioned_image(
            source, (720, 450), boxes, replacement_colors, "RGB"
        )

        result = cut_image(source, output_dir, overwrite=True)

        for path, color in zip(result, replacement_colors, strict=True):
            self.assert_uniform_image(path, color, "RGB")
        self.assertEqual([], list(output_dir.glob(".*.tmp")))

    def test_converts_cmyk_source_to_rgb_png(self) -> None:
        source = self.root / "cmyk.tif"
        output_dir = self.root / "output"
        image = Image.new("CMYK", (720, 450), (0, 255, 255, 0))
        try:
            image.save(source)
        finally:
            image.close()

        result = cut_image(source, output_dir)

        for path in result:
            self.assert_uniform_image(path, (255, 0, 0), "RGB")

    def test_converts_transparent_palette_source_to_rgba_png(self) -> None:
        source = self.root / "palette.png"
        output_dir = self.root / "output"
        image = Image.new("P", (720, 450))
        image.putpalette(
            [255, 0, 0, 0, 255, 0, 0, 0, 255] + [0] * (768 - 9)
        )
        try:
            image.paste(0, (0, 0, 720, 150))
            image.paste(1, (0, 150, 720, 300))
            image.paste(2, (0, 300, 720, 450))
            image.info["transparency"] = 0
            image.save(source)
        finally:
            image.close()

        result = cut_image(source, output_dir)

        expected_colors = (
            (255, 0, 0, 0),
            (0, 255, 0, 255),
            (0, 0, 255, 255),
        )
        for path, color in zip(result, expected_colors, strict=True):
            self.assert_uniform_image(path, color, "RGBA")

    def test_rejects_multi_frame_source(self) -> None:
        source = self.root / "animated.gif"
        output_dir = self.root / "output"
        first = Image.new("RGB", (720, 450), (255, 0, 0))
        second = Image.new("RGB", (720, 450), (0, 255, 0))
        try:
            first.save(source, save_all=True, append_images=[second])
        finally:
            second.close()
            first.close()

        with self.assertRaises(UnsupportedMultiFrameImageError) as raised:
            cut_image(source, output_dir)

        self.assertEqual(2, raised.exception.frame_count)
        self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
