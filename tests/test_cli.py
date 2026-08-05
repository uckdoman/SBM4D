from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from PIL import Image

from sbm4d.cli import _run_batch, build_parser, default_output_dir


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.root = Path(self._temporary_directory.name)

    @staticmethod
    def _create_image(path: Path, size: tuple[int, int] = (720, 450)) -> None:
        with Image.new("RGB", size, (25, 50, 75)) as image:
            image.save(path)

    def test_parser_accepts_multiple_images_output_and_overwrite(self) -> None:
        arguments = build_parser().parse_args(
            ["첫 번째.png", "두 번째.png", "-o", "결과", "--overwrite"]
        )

        self.assertEqual(
            [Path("첫 번째.png"), Path("두 번째.png")],
            arguments.images,
        )
        self.assertEqual(Path("결과"), arguments.output)
        self.assertTrue(arguments.overwrite)

    def test_default_output_is_beside_the_source(self) -> None:
        source = self.root / "입력" / "배너.png"

        self.assertEqual(self.root / "입력" / "output", default_output_dir(source))

    def test_batch_continues_after_a_broken_image_and_returns_failure(self) -> None:
        broken = self.root / "손상.png"
        valid = self.root / "깡담비.하단배너.png"
        output = self.root / "결과"
        broken.write_bytes(b"not an image")
        self._create_image(valid)
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = _run_batch([broken, valid], output)

        self.assertEqual(1, exit_code)
        self.assertIn("손상.png", stderr.getvalue())
        self.assertEqual(
            [output / f"깡담비.하단배너_{index}.png" for index in range(1, 4)],
            [Path(line) for line in stdout.getvalue().splitlines()],
        )

    def test_overwrite_flag_controls_existing_results(self) -> None:
        source = self.root / "배너.png"
        output = self.root / "output"
        self._create_image(source)

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(0, _run_batch([source], output))
            self.assertEqual(1, _run_batch([source], output))
            self.assertEqual(0, _run_batch([source], output, overwrite=True))

    def test_batch_name_collision_is_blocked_even_with_overwrite(self) -> None:
        first_dir = self.root / "첫째"
        second_dir = self.root / "둘째"
        first_dir.mkdir()
        second_dir.mkdir()
        first = first_dir / "banner.png"
        second = second_dir / "BANNER.jpg"
        unique = self.root / "unique.png"
        output = self.root / "output"
        self._create_image(first)
        self._create_image(second)
        self._create_image(unique)
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = _run_batch(
                [first, second, unique],
                output,
                overwrite=True,
            )

        self.assertEqual(1, exit_code)
        self.assertIn("결과 이름이 겹쳐", stderr.getvalue())
        self.assertIn(str(first), stderr.getvalue())
        self.assertIn(str(second), stderr.getvalue())
        self.assertEqual(
            [output / f"unique_{index}.png" for index in range(1, 4)],
            [Path(line) for line in stdout.getvalue().splitlines()],
        )
        self.assertEqual(
            [f"unique_{index}.png" for index in range(1, 4)],
            sorted(path.name for path in output.glob("*.png")),
        )


if __name__ == "__main__":
    unittest.main()
