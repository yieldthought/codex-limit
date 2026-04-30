from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import QuotaSample


SESSION_GLOB = "*.jsonl"


def codex_sessions_dir() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "sessions"


def session_files(sessions_dir: Path | None = None) -> list[Path]:
    root = sessions_dir or codex_sessions_dir()
    if not root.exists():
        return []
    return sorted(
        (path for path in root.rglob(SESSION_GLOB) if path.is_file()),
        key=_safe_mtime,
        reverse=True,
    )


def latest_snapshot(sessions_dir: Path | None = None) -> QuotaSample | None:
    for path in session_files(sessions_dir):
        snapshots = list(snapshots_from_file(path))
        if snapshots:
            return max(snapshots, key=lambda sample: sample.observed_at)
    return None


def collect_current_window_samples(
    sessions_dir: Path | None = None,
    latest: QuotaSample | None = None,
) -> list[QuotaSample]:
    current = latest or latest_snapshot(sessions_dir)
    if current is None:
        return []

    reset_start = current.reset_start
    reset_end = current.resets_at
    candidates = []
    for path in session_files(sessions_dir):
        mtime = _safe_mtime(path)
        if mtime and mtime < reset_start - 86400:
            continue
        candidates.extend(snapshots_from_file(path))
    return sorted(
        [
            sample
            for sample in candidates
            if _same_window(sample, current)
            and reset_start <= sample.observed_at <= reset_end
        ],
        key=lambda sample: sample.observed_at,
    )


def snapshots_from_file(path: Path) -> Iterable[QuotaSample]:
    fallback_timestamp = _safe_mtime(path) or time.time()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if '"rate_limits"' not in line:
                    continue
                sample = sample_from_json_line(
                    line,
                    source_path=str(path),
                    fallback_timestamp=fallback_timestamp,
                )
                if sample is not None:
                    yield sample
    except OSError:
        return


def sample_from_json_line(
    line: str,
    *,
    source_path: str | None = None,
    fallback_timestamp: float | None = None,
) -> QuotaSample | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None

    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        return None
    rate_data = payload.get("rate_limits")
    if not isinstance(rate_data, dict) or not _is_codex_limit(rate_data):
        return None

    observed_at = _parse_timestamp(event.get("timestamp"), fallback_timestamp)
    if observed_at is None:
        observed_at = time.time()

    window = _select_weekly_window(rate_data)
    if window is None:
        return None

    used_percent = _number(window.get("used_percent"))
    window_minutes = _number(window.get("window_minutes"))
    if used_percent is None or window_minutes is None or window_minutes <= 0:
        return None

    resets_at = _resets_at(window, observed_at)
    if resets_at is None:
        return None

    return QuotaSample(
        observed_at=observed_at,
        used_percent=max(0.0, min(100.0, used_percent)),
        window_minutes=window_minutes,
        resets_at=resets_at,
        limit_id=_str_or_none(rate_data.get("limit_id")),
        limit_name=_str_or_none(rate_data.get("limit_name")),
        source_path=source_path,
    )


def _is_codex_limit(rate_data: dict[str, Any]) -> bool:
    limit_id = rate_data.get("limit_id")
    if isinstance(limit_id, str):
        return limit_id == "codex"

    limit_name = rate_data.get("limit_name")
    if isinstance(limit_name, str) and "spark" in limit_name.lower():
        return False
    return True


def _select_weekly_window(rate_data: dict[str, Any]) -> dict[str, Any] | None:
    secondary = rate_data.get("secondary")
    if _usable_window(secondary):
        return secondary

    windows = [
        value
        for key, value in rate_data.items()
        if key in {"primary", "secondary"} and _usable_window(value)
    ]
    if not windows:
        return None
    return max(windows, key=lambda item: float(item.get("window_minutes") or 0))


def _usable_window(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return _number(value.get("used_percent")) is not None and _number(
        value.get("window_minutes")
    ) is not None


def _resets_at(window: dict[str, Any], observed_at: float) -> float | None:
    reset = _number(window.get("resets_at"))
    if reset is not None:
        return reset
    resets_in = _number(window.get("resets_in_seconds"))
    if resets_in is None:
        return None
    return observed_at + resets_in


def _parse_timestamp(value: Any, fallback: float | None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return fallback
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    return fallback


def _same_window(sample: QuotaSample, current: QuotaSample) -> bool:
    if abs(sample.resets_at - current.resets_at) > 300:
        return False
    return abs(sample.window_minutes - current.window_minutes) < 1


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None
