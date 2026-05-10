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
burn multiple, where `1.0x` means weekly quota is being consumed at the
real-time replenishment pace.

The burn multiple averages weekly-limit usage over the shorter of the last two
hours or the current 5% burst. A large single update uses the full observed
jump over the time since the previous sample, capped at two hours, so bursts are
visible without letting old activity keep the title artificially high.
If Codex has not written a newer rate-limit event by the next poll, CodexLimit
records a flat sample at the poll time with the same usage percent so idle time
counts as no additional usage.

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

Publishing uses the same trusted-publishing workflow as `codexapi`: create a
GitHub release or push a `v*` tag, and `.github/workflows/publish.yml` builds
and publishes the package to PyPI.
