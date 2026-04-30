from setuptools import setup


APP = ["CodexLimit.py"]
OPTIONS = {
    "argv_emulation": False,
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


setup(
    app=APP,
    options={"py2app": OPTIONS},
)
