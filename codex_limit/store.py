from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

from .models import QuotaSample


APP_DIR_NAME = "CodexLimit"
HISTORY_FILE_NAME = "samples.jsonl"
FIVE_HOUR_HISTORY_FILE_NAME = "five_hour_samples.jsonl"


def default_history_path(file_name: str = HISTORY_FILE_NAME) -> Path:
    override = os.environ.get("CODEX_LIMIT_HOME")
    if override:
        return Path(override).expanduser() / file_name
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / APP_DIR_NAME
        / file_name
    )


class HistoryStore:
    def __init__(self, path: Path | None = None, *, file_name: str = HISTORY_FILE_NAME):
        self.path = path or default_history_path(file_name)

    def load(self) -> list[QuotaSample]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        except OSError:
            return []

        samples = []
        for line in lines:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            sample = QuotaSample.from_json(data)
            if sample is not None:
                sample = _mark_legacy_assumed_sample(sample, data)
                samples.append(sample)
        return sorted(samples, key=lambda sample: sample.observed_at)

    def save(self, samples: list[QuotaSample]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        text = "".join(json.dumps(sample.to_json(), sort_keys=True) + "\n" for sample in samples)
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(self.path)


def merge_and_trim_samples(
    existing: list[QuotaSample],
    incoming: list[QuotaSample],
    *,
    reset_start: float,
    reset_end: float,
    resets_at: float | None = None,
    window_minutes: float | None = None,
) -> list[QuotaSample]:
    merged: dict[int, QuotaSample] = {}
    for sample in [*existing, *incoming]:
        if (
            reset_start <= sample.observed_at <= reset_end
            and _matches_window(sample, resets_at, window_minutes)
        ):
            merged[int(round(sample.observed_at * 1000))] = sample
    return _monotonic_used_percent(
        sorted(merged.values(), key=lambda sample: sample.observed_at)
    )


def _matches_window(
    sample: QuotaSample,
    resets_at: float | None,
    window_minutes: float | None,
) -> bool:
    if resets_at is not None and abs(sample.resets_at - resets_at) > 300:
        return False
    if window_minutes is not None and abs(sample.window_minutes - window_minutes) >= 1:
        return False
    return True


def _monotonic_used_percent(samples: list[QuotaSample]) -> list[QuotaSample]:
    normalized = []
    highest_used = 0.0
    for sample in samples:
        if sample.used_percent < highest_used:
            sample = replace(sample, used_percent=highest_used)
        else:
            highest_used = sample.used_percent
        normalized.append(sample)
    return normalized


def _mark_legacy_assumed_sample(
    sample: QuotaSample,
    data: dict[str, object],
) -> QuotaSample:
    if "assumed" in data or sample.assumed or sample.source_path is None:
        return sample
    try:
        source_mtime = Path(sample.source_path).stat().st_mtime
    except OSError:
        return sample
    if sample.observed_at > source_mtime + 2.0:
        return replace(sample, assumed=True)
    return sample
