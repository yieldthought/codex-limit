import sys
from pathlib import Path

from setuptools import setup


def package_version() -> str:
    init_file = Path(__file__).with_name("codex_limit") / "__init__.py"
    for line in init_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("Unable to read package version")


APP = ["CodexLimit.py"]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/CodexLimit.icns",
    "packages": ["codex_limit"],
    "plist": {
        "CFBundleName": "CodexLimit",
        "CFBundleDisplayName": "CodexLimit",
        "CFBundleIdentifier": "com.local.codexlimit",
        "CFBundleVersion": package_version(),
        "CFBundleShortVersionString": package_version(),
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
}


if "py2app" in sys.argv:
    setup(
        app=APP,
        options={"py2app": OPTIONS},
    )
else:
    setup()
