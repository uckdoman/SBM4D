from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sbm4d.batch import find_batch_output_conflicts


class BatchConflictTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.root = Path(self._temporary_directory.name)

    def test_finds_case_insensitive_stem_collision_in_same_output(self) -> None:
        output = self.root / "Output"
        first = self.root / "A" / "banner.png"
        second = self.root / "B" / "BANNER.jpg"

        conflicts = find_batch_output_conflicts(
            [(first, output), (second, self.root / "output")]
        )

        self.assertEqual(1, len(conflicts))
        self.assertEqual("banner", conflicts[0].stem)
        self.assertEqual((first, second), conflicts[0].sources)

    def test_allows_same_stem_in_different_output_folders(self) -> None:
        first = self.root / "A" / "banner.png"
        second = self.root / "B" / "banner.jpg"

        conflicts = find_batch_output_conflicts(
            [
                (first, self.root / "A" / "output"),
                (second, self.root / "B" / "output"),
            ]
        )

        self.assertEqual((), conflicts)


if __name__ == "__main__":
    unittest.main()
