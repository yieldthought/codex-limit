#!/usr/bin/env bash
set -euo pipefail

APP_NAME="CodexLimit"
APP_BUNDLE="${APP_NAME}.app"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-}"
TARGET_DIR="${CODEX_LIMIT_INSTALL_DIR:-}"
OPEN_AFTER_INSTALL=1

usage() {
  cat <<'EOF'
Usage: scripts/install.sh [--user|--system] [--target-dir DIR] [--no-open]

Build and install CodexLimit.app.

Options:
  --user            Install to ~/Applications.
  --system          Install to /Applications. Fails if /Applications is not writable.
  --target-dir DIR  Install to a specific directory.
  --no-open         Do not launch the app after installing.
  -h, --help        Show this help.

Environment:
  PYTHON                   Python executable to use.
  CODEX_LIMIT_INSTALL_DIR  Default target directory when --target-dir is omitted.
EOF
}

while (($#)); do
  case "$1" in
    --user)
      TARGET_DIR="$HOME/Applications"
      ;;
    --system)
      TARGET_DIR="/Applications"
      ;;
    --target-dir)
      shift
      if [[ $# -eq 0 ]]; then
        echo "error: --target-dir requires a directory" >&2
        exit 2
      fi
      TARGET_DIR="$1"
      ;;
    --no-open)
      OPEN_AFTER_INSTALL=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "error: CodexLimit.app can only be built on macOS" >&2
  exit 1
fi

cd "$PROJECT_ROOT"

if [[ -z "$PYTHON" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
  else
    PYTHON="python3"
  fi
fi

if [[ ! -x "$PYTHON" && "$PYTHON" != */* ]]; then
  if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: Python executable not found: $PYTHON" >&2
    exit 1
  fi
elif [[ ! -x "$PYTHON" ]]; then
  echo "error: Python executable is not runnable: $PYTHON" >&2
  exit 1
fi

if [[ "$PYTHON" == "python3" && ! -d ".venv" ]]; then
  echo "Creating .venv..."
  python3 -m venv .venv
  PYTHON=".venv/bin/python"
fi

echo "Installing build dependencies..."
"$PYTHON" -m pip install -e ".[packaging]"

echo "Building ${APP_BUNDLE}..."
rm -rf build "dist/${APP_BUNDLE}"
"$PYTHON" setup.py py2app

SOURCE_APP="$PROJECT_ROOT/dist/$APP_BUNDLE"
if [[ ! -d "$SOURCE_APP" ]]; then
  echo "error: build did not produce $SOURCE_APP" >&2
  exit 1
fi

if [[ -z "$TARGET_DIR" ]]; then
  if [[ -w "/Applications" ]]; then
    TARGET_DIR="/Applications"
  else
    TARGET_DIR="$HOME/Applications"
  fi
fi

mkdir -p "$TARGET_DIR"
if [[ ! -w "$TARGET_DIR" ]]; then
  echo "error: target directory is not writable: $TARGET_DIR" >&2
  echo "Try: scripts/install.sh --user" >&2
  exit 1
fi

TARGET_APP="$TARGET_DIR/$APP_BUNDLE"

echo "Stopping running ${APP_NAME}, if any..."
pkill -x "$APP_NAME" 2>/dev/null || true
sleep 0.5

echo "Installing to $TARGET_APP..."
rm -rf "$TARGET_APP"
/usr/bin/ditto --rsrc --extattr "$SOURCE_APP" "$TARGET_APP"
find "$TARGET_APP" -exec xattr -d com.apple.quarantine {} + 2>/dev/null || true
touch "$TARGET_APP"

if [[ "$OPEN_AFTER_INSTALL" -eq 1 ]]; then
  echo "Launching $TARGET_APP..."
  open -n "$TARGET_APP"
fi

echo "Installed $TARGET_APP"
