import sys

from setuptools import setup


APP = ["CodexLimit.py"]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/CodexLimit.icns",
    "packages": ["codex_limit"],
    "plist": {
        "CFBundleName": "CodexLimit",
        "CFBundleDisplayName": "CodexLimit",
        "CFBundleIdentifier": "com.local.codexlimit",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
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
