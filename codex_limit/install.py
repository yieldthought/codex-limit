from __future__ import annotations

import argparse
import importlib.resources
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from . import __version__


APP_NAME = "CodexLimit"
APP_BUNDLE = f"{APP_NAME}.app"
BUNDLE_ID = "com.local.codexlimit"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    install_app(args)


def install_app(args: argparse.Namespace) -> Path:
    if platform.system() != "Darwin":
        raise SystemExit("CodexLimit.app can only be built on macOS.")

    _require_py2app()

    target_dir = _target_dir(args)
    target_dir.mkdir(parents=True, exist_ok=True)
    if not os.access(target_dir, os.W_OK):
        raise SystemExit(
            f"Target directory is not writable: {target_dir}\n"
            "Try: codex-limit-install --user"
        )

    with tempfile.TemporaryDirectory(prefix="codex-limit-build-") as tmp:
        build_root = Path(tmp)
        _write_build_project(build_root)

        print(f"Building {APP_BUNDLE}...")
        subprocess.run(
            [sys.executable, "setup.py", "py2app"],
            cwd=build_root,
            check=True,
        )

        source_app = build_root / "dist" / APP_BUNDLE
        if not source_app.is_dir():
            raise SystemExit(f"Build did not produce {source_app}")

        target_app = target_dir / APP_BUNDLE
        if not args.no_stop:
            _stop_running_app()
        _copy_app(source_app, target_app)
        _clear_quarantine(target_app)

        if not args.no_open:
            print(f"Launching {target_app}...")
            subprocess.run(["open", "-n", str(target_app)], check=False)

        print(f"Installed {target_app}")
        return target_app


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="codex-limit-install",
        description="Build and install CodexLimit.app from the installed Python package.",
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--user", action="store_true", help="Install to ~/Applications.")
    target.add_argument(
        "--system",
        action="store_true",
        help="Install to /Applications. Fails if /Applications is not writable.",
    )
    parser.add_argument("--target-dir", help="Install to a specific directory.")
    parser.add_argument("--no-open", action="store_true", help="Do not launch after install.")
    parser.add_argument("--no-stop", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _target_dir(args: argparse.Namespace) -> Path:
    if args.target_dir:
        return Path(args.target_dir).expanduser()
    if args.user:
        return Path.home() / "Applications"
    if args.system:
        return Path("/Applications")
    system_apps = Path("/Applications")
    if os.access(system_apps, os.W_OK):
        return system_apps
    return Path.home() / "Applications"


def _require_py2app() -> None:
    try:
        import py2app  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "codex-limit-install requires py2app. Install with:\n"
            '  python -m pip install "codex-limit[app]"'
        ) from exc


def _write_build_project(build_root: Path) -> None:
    icon = importlib.resources.files("codex_limit").joinpath("assets/CodexLimit.icns")
    if not icon.is_file():
        raise SystemExit("Packaged app icon is missing: codex_limit/assets/CodexLimit.icns")
    with importlib.resources.as_file(icon) as icon_path:
        shutil.copyfile(icon_path, build_root / "CodexLimit.icns")

    (build_root / "CodexLimit.py").write_text(
        "from codex_limit.__main__ import main\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    (build_root / "setup.py").write_text(
        textwrap.dedent(
            f"""
            from setuptools import setup

            APP = ["CodexLimit.py"]
            OPTIONS = {{
                "argv_emulation": False,
                "iconfile": "CodexLimit.icns",
                "packages": ["codex_limit"],
                "plist": {{
                    "CFBundleName": "{APP_NAME}",
                    "CFBundleDisplayName": "{APP_NAME}",
                    "CFBundleIdentifier": "{BUNDLE_ID}",
                    "CFBundleVersion": "{__version__}",
                    "CFBundleShortVersionString": "{__version__}",
                    "LSUIElement": True,
                    "NSHighResolutionCapable": True,
                }},
            }}

            setup(app=APP, options={{"py2app": OPTIONS}})
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _stop_running_app() -> None:
    print(f"Stopping running {APP_NAME}, if any...")
    subprocess.run(["pkill", "-x", APP_NAME], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _copy_app(source_app: Path, target_app: Path) -> None:
    print(f"Installing to {target_app}...")
    if target_app.exists():
        shutil.rmtree(target_app)
    subprocess.run(["/usr/bin/ditto", "--rsrc", "--extattr", str(source_app), str(target_app)], check=True)
    target_app.touch()


def _clear_quarantine(target_app: Path) -> None:
    subprocess.run(
        ["xattr", "-dr", "com.apple.quarantine", str(target_app)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
