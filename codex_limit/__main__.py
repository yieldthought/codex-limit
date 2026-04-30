def main() -> None:
    try:
        from .cocoa_app import run
    except ModuleNotFoundError as exc:
        if exc.name in {"AppKit", "Foundation", "objc"}:
            raise SystemExit(
                "CodexLimit requires PyObjC on macOS. Install with:\n"
                '  python -m pip install -e ".[packaging]"'
            ) from exc
        raise
    run()


if __name__ == "__main__":
    main()

