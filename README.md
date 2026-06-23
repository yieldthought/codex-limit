# CodexLimit

CodexLimit is a macOS menu bar widget that reads local Codex session logs,
shows the weekly non-Spark Codex limit burn rate as a status item title, and
graphs both the weekly and 5-hour limits in the popover.

The app does not call a network API. It reads `CODEX_HOME` or
`~/.codex/sessions`, records samples in:

```text
~/Library/Application Support/CodexLimit/samples.jsonl
~/Library/Application Support/CodexLimit/five_hour_samples.jsonl
```

## Install for Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[packaging]"
```

## Install from PyPI

```bash
pip install "codex-limit[app]"
codex-limit-install --user
```

That builds `CodexLimit.app`, installs it to `~/Applications`, and launches it.
Use `codex-limit-install --system` to install to `/Applications`.

You can also run it directly as a Python menu-bar process:

```bash
codex-limit
```

## Run

```bash
python -m codex_limit
```

Click the menu bar title to open the graph popover. The title is the current
weekly burn multiple, where `1.0x` means weekly quota is being consumed at the
real-time replenishment pace. The popover shows a blue weekly graph and a green
5-hour graph, each with current used/left percentages and estimated time to
zero.

If either tracked limit is projected to hit zero within 30 minutes while its
reset is still more than 30 minutes away, the menu bar title and that limit's
ETA show a warning marker.

The burn multiple averages weekly-limit usage over the shorter of the last two
hours or the current 5% burst. If Codex has not written a newer rate-limit event
by the next poll, CodexLimit extends the graph with an assumed flat sample so
idle time counts as no additional usage. Those assumed samples are not persisted
as real observations and are ignored as lower baselines when a later Codex log
reveals a percentage jump.

CodexLimit keeps an in-process cache of parsed session-log samples. Each poll
still checks the session tree for new or modified JSONL files, but unchanged
files are not reparsed and growing files are read only from their appended
tail.

## Build a macOS App Bundle

```bash
python setup.py py2app
open dist/CodexLimit.app
```

The bundle is configured as a menu-bar-only accessory app and should not show a
Dock icon. The app icon is generated from `assets/CodexLimit.icns`.

## Install Locally

```bash
scripts/install.sh
```

The installer builds `dist/CodexLimit.app`, stops any running copy, installs to
`/Applications` when writable or `~/Applications` otherwise, and launches the
app. Use `scripts/install.sh --user` to force `~/Applications`, or
`scripts/install.sh --no-open` to install without launching.

## Test

```bash
python -m unittest discover -s tests
```

## Release

Publishing uses the local release flow from this machine:

```bash
python -m pip install --upgrade build twine
rm -rf dist build
python -m build
python -m twine check dist/*
python -m twine upload --non-interactive dist/*.tar.gz dist/*.whl
```
