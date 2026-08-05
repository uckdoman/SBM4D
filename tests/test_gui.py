from __future__ import annotations

import unittest
from pathlib import Path

from sbm4d import UnsupportedImageSizeError
from sbm4d.batch import BatchOutputConflict
from sbm4d.gui import SBM4DApp


class GuiMessageTests(unittest.TestCase):
    def test_unsupported_size_message_is_friendly_korean(self) -> None:
        message = SBM4DApp._unsupported_size_message(
            Path("잘못된배너.png"),
            UnsupportedImageSizeError((800, 600)),
        )

        self.assertIn("잘못된배너.png", message)
        self.assertIn("800×600", message)
        self.assertIn("720×450", message)
        self.assertIn("1440×450", message)

    def test_batch_conflict_message_explains_how_to_fix_names(self) -> None:
        first = Path("A/banner.png")
        second = Path("B/banner.jpg")
        message = SBM4DApp._batch_conflict_message(
            (
                BatchOutputConflict(
                    output_dir=Path("output"),
                    stem="banner",
                    sources=(first, second),
                ),
            )
        )

        self.assertIn(str(first), message)
        self.assertIn(str(second), message)
        self.assertIn("파일명을 서로 다르게", message)


if __name__ == "__main__":
    unittest.main()
