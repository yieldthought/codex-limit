from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path

from .metrics import BurnRate, calculate_burn_rate, format_eta, format_multiple
from .models import QuotaSample
from .reader import collect_current_window_samples, latest_snapshot
from .store import HistoryStore, merge_and_trim_samples


HISTORY_RESET_DROP_PERCENT = 20.0


@dataclass(frozen=True)
class DisplayState:
    samples: list[QuotaSample]
    current: QuotaSample | None
    burn_rate: BurnRate
    title: str
    eta_text: str
    error: str | None
    refreshed_at: float


class CodexLimitMonitor:
    def __init__(
        self,
        *,
        sessions_dir: Path | None = None,
        history_store: HistoryStore | None = None,
    ):
        self.sessions_dir = sessions_dir
        self.history_store = history_store or HistoryStore()
        self._last_reset_end: float | None = None

    def refresh(self, *, backfill: bool = False) -> DisplayState:
        latest = latest_snapshot(self.sessions_dir)
        now = time.time()
        if latest is None:
            burn_rate = BurnRate(0.0, 0.0, None, None)
            return DisplayState([], None, burn_rate, "--", "unknown", "No Codex rate-limit logs found.", now)

        current = _assume_no_usage_until_now(latest, now)
        reset_changed = self._last_reset_end is None or abs(
            self._last_reset_end - current.resets_at
        ) > 300
        existing = self.history_store.load()
        history_conflicts = _history_conflicts_with_current(existing, current)
        if history_conflicts:
            existing = []
        incoming = [latest]
        if current.observed_at != latest.observed_at:
            incoming.append(current)
        if backfill or reset_changed or history_conflicts:
            incoming.extend(
                collect_current_window_samples(self.sessions_dir, latest=latest)
            )

        samples = merge_and_trim_samples(
            existing,
            incoming,
            reset_start=current.reset_start,
            reset_end=current.resets_at,
        )
        self.history_store.save(samples)
        self._last_reset_end = current.resets_at

        display_current = samples[-1] if samples else current
        burn_rate = calculate_burn_rate(samples, current=display_current)
        title = format_multiple(burn_rate.multiple)
        eta_text = format_eta(burn_rate.eta_minutes)
        error = None
        if display_current.resets_at < now:
            error = "Latest Codex limit sample is from a completed reset window."

        return DisplayState(samples, display_current, burn_rate, title, eta_text, error, now)


def _assume_no_usage_until_now(sample: QuotaSample, now: float) -> QuotaSample:
    if sample.observed_at >= now or now >= sample.resets_at:
        return sample
    return replace(sample, observed_at=now)


def _history_conflicts_with_current(
    existing: list[QuotaSample],
    current: QuotaSample,
) -> bool:
    current_window = [
        sample
        for sample in existing
        if current.reset_start <= sample.observed_at <= current.resets_at
        and abs(sample.resets_at - current.resets_at) <= 300
        and abs(sample.window_minutes - current.window_minutes) < 1
    ]
    if not current_window:
        return False
    highest = max(sample.used_percent for sample in current_window)
    return highest - current.used_percent >= HISTORY_RESET_DROP_PERCENT
