import tempfile
import unittest
from pathlib import Path

from project.path_utils import resolve_mount_path


class ResolveMountPathTests(unittest.TestCase):
    def test_accepts_nested_relative_path(self):
        with tempfile.TemporaryDirectory() as base_dir:
            self.assertEqual(
                resolve_mount_path("datasets/project", base_dir),
                str(Path(base_dir) / "datasets" / "project"),
            )

    def test_rejects_absolute_path(self):
        with tempfile.TemporaryDirectory() as base_dir:
            with self.assertRaises(ValueError):
                resolve_mount_path("/tmp/outside", base_dir)

    def test_rejects_parent_directory_segments(self):
        with tempfile.TemporaryDirectory() as base_dir:
            for path in ("../outside", "datasets/../../outside"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    resolve_mount_path(path, base_dir)

    def test_rejects_symbolic_link_escape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "mounts"
            outside_dir = Path(temp_dir) / "outside"
            base_dir.mkdir()
            outside_dir.mkdir()
            (base_dir / "link").symlink_to(outside_dir, target_is_directory=True)

            with self.assertRaises(ValueError):
                resolve_mount_path("link/mount", str(base_dir))


if __name__ == "__main__":
    unittest.main()