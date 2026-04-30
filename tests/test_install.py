import tempfile
import unittest
from pathlib import Path

from codex_limit import __version__
from codex_limit.install import _parse_args, _target_dir, _write_build_project


class InstallTests(unittest.TestCase):
    def test_target_dir_user(self):
        args = _parse_args(["--user"])
        self.assertEqual(_target_dir(args), Path.home() / "Applications")

    def test_target_dir_expands_custom_path(self):
        args = _parse_args(["--target-dir", "~/Apps/Codex"])
        self.assertEqual(_target_dir(args), Path.home() / "Apps" / "Codex")

    def test_write_build_project_includes_icon_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_build_project(root)
            self.assertTrue((root / "CodexLimit.icns").is_file())
            setup_text = (root / "setup.py").read_text(encoding="utf-8")
            self.assertIn('"iconfile": "CodexLimit.icns"', setup_text)
            self.assertIn(f'"CFBundleShortVersionString": "{__version__}"', setup_text)


if __name__ == "__main__":
    unittest.main()
