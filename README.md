# CodexLimit

CodexLimit is a macOS menu bar widget that reads local Codex session logs and
shows the weekly non-Spark Codex limit burn rate as a status item title.

The app does not call a network API. It reads `CODEX_HOME` or
`~/.codex/sessions`, records samples in:

```text
~/Library/Application Support/CodexLimit/samples.jsonl
```

## Install for Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[packaging]"
```

## Run

```bash
python -m codex_limit
```

Click the menu bar title to open the graph popover. The title is the current
burn multiple, where `1.0x` means weekly quota is being consumed at the
real-time replenishment pace.

## Build a macOS App Bundle

```bash
python setup.py py2app
open dist/CodexLimit.app
```

The bundle is configured as a menu-bar-only accessory app and should not show a
Dock icon.

## Test

```bash
python -m unittest discover -s tests
```
