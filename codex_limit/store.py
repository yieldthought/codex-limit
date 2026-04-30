from __future__ import annotations

import json
import os
from pathlib import Path

from .models import QuotaSample


APP_DIR_NAME = "CodexLimit"
HISTORY_FILE_NAME = "samples.jsonl"


def default_history_path() -> Path:
    override = os.environ.get("CODEX_LIMIT_HOME")
    if override:
        return Path(override).expanduser() / HISTORY_FILE_NAME
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / APP_DIR_NAME
        / HISTORY_FILE_NAME
    )


class HistoryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_history_path()

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
) -> list[QuotaSample]:
    merged: dict[int, QuotaSample] = {}
    for sample in [*existing, *incoming]:
        if reset_start <= sample.observed_at <= reset_end:
            merged[int(round(sample.observed_at * 1000))] = sample
    return sorted(merged.values(), key=lambda sample: sample.observed_at)

