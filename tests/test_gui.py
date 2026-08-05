from __future__ import annotations

import unittest
from pathlib import Path

from sbm4d import UnsupportedImageSizeError
from sbm4d.gui import (
    CropGuideRegion,
    SBM4DApp,
    adaptive_window_size,
    crop_guide_geometry,
    middle_ellipsis,
    preview_fit_size,
)


class AdaptiveWindowSizeTests(unittest.TestCase):
    def test_720x450_uses_a_taller_compact_window(self) -> None:
        self.assertEqual(adaptive_window_size((720, 450), (1920, 1080)), (820, 650))

    def test_1440x450_uses_a_wide_low_window(self) -> None:
        self.assertEqual(adaptive_window_size((1440, 450), (1920, 1080)), (980, 486))

    def test_small_screen_limits_the_adaptive_height(self) -> None:
        self.assertEqual(adaptive_window_size((720, 450), (900, 600)), (820, 500))

    def test_non_positive_dimensions_are_rejected(self) -> None:
        for source_size, screen_size in (
            ((0, 450), (1920, 1080)),
            ((720, 450), (0, 1080)),
        ):
            with self.subTest(source_size=source_size, screen_size=screen_size):
                with self.assertRaises(ValueError):
                    adaptive_window_size(source_size, screen_size)


class PreviewFitSizeTests(unittest.TestCase):
    def test_720x450_preview_is_aspect_fitted_inside_bounds(self) -> None:
        self.assertEqual(preview_fit_size((720, 450), (640, 360)), (576, 360))

    def test_1440x450_preview_is_aspect_fitted_inside_bounds(self) -> None:
        self.assertEqual(preview_fit_size((1440, 450), (640, 360)), (640, 200))

    def test_preview_never_upscales_source(self) -> None:
        self.assertEqual(preview_fit_size((720, 450), (1600, 900)), (720, 450))

    def test_non_positive_dimensions_are_rejected(self) -> None:
        invalid_cases = (
            ((0, 450), (640, 360)),
            ((720, -1), (640, 360)),
            ((720, 450), (0, 360)),
            ((720, 450), (640, -1)),
        )
        for source_size, bounds in invalid_cases:
            with self.subTest(source_size=source_size, bounds=bounds):
                with self.assertRaises(ValueError):
                    preview_fit_size(source_size, bounds)


class MiddleEllipsisTests(unittest.TestCase):
    def test_short_text_is_left_unchanged(self) -> None:
        self.assertEqual(middle_ellipsis("banner.png", 20), "banner.png")

    def test_long_text_keeps_both_recognizable_ends(self) -> None:
        shortened = middle_ellipsis("아주긴파일이름_banner_final.png", 16)

        self.assertEqual(16, len(shortened))
        self.assertIn("…", shortened)
        self.assertTrue(shortened.startswith("아주긴파일"))
        self.assertTrue(shortened.endswith("nal.png"))

    def test_too_small_limit_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            middle_ellipsis("banner.png", 4)


class CropGuideGeometryTests(unittest.TestCase):
    def test_720x450_guide_has_three_full_width_regions(self) -> None:
        regions = crop_guide_geometry((720, 450), (10, 20, 586, 380))

        self.assertEqual(
            regions,
            (
                CropGuideRegion(1, (10, 20, 586, 140)),
                CropGuideRegion(2, (10, 140, 586, 260)),
                CropGuideRegion(3, (10, 260, 586, 380)),
            ),
        )

    def test_1440x450_guide_has_six_row_major_regions(self) -> None:
        regions = crop_guide_geometry((1440, 450), (20, 30, 620, 210))

        self.assertEqual(
            regions,
            (
                CropGuideRegion(1, (20, 30, 320, 90)),
                CropGuideRegion(2, (320, 30, 620, 90)),
                CropGuideRegion(3, (20, 90, 320, 150)),
                CropGuideRegion(4, (320, 90, 620, 150)),
                CropGuideRegion(5, (20, 150, 320, 210)),
                CropGuideRegion(6, (320, 150, 620, 210)),
            ),
        )

    def test_unsupported_source_size_has_no_crop_guide(self) -> None:
        self.assertEqual(
            crop_guide_geometry((800, 600), (0, 0, 400, 300)),
            (),
        )

    def test_invalid_preview_box_is_rejected(self) -> None:
        for bbox in ((0, 0, 0, 100), (10, 0, 5, 100), (0, 20, 100, 20)):
            with self.subTest(bbox=bbox):
                with self.assertRaises(ValueError):
                    crop_guide_geometry((720, 450), bbox)

    def test_non_positive_source_size_is_rejected(self) -> None:
        for source_size in ((0, 450), (720, 0), (-1, 450)):
            with self.subTest(source_size=source_size):
                with self.assertRaises(ValueError):
                    crop_guide_geometry(source_size, (0, 0, 100, 100))


class GuiMessageTests(unittest.TestCase):
    def test_unsupported_size_message_is_friendly_korean(self) -> None:
        message = SBM4DApp._unsupported_size_message(
            Path("잘못된배너.png"),
            UnsupportedImageSizeError((800, 600)),
        )

        self.assertEqual(
            message,
            (
                "잘못된배너.png: 이미지 크기가 800×600입니다. "
                "720×450 또는 1440×450 이미지를 선택해 주세요."
            ),
        )


if __name__ == "__main__":
    unittest.main()
