from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .metrics import BurnRate, calculate_burn_rate, format_eta, format_multiple
from .models import QuotaSample
from .reader import collect_current_window_samples, latest_snapshot
from .store import HistoryStore, merge_and_trim_samples


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
        current = latest_snapshot(self.sessions_dir)
        now = time.time()
        if current is None:
            burn_rate = BurnRate(0.0, 0.0, None, None)
            return DisplayState([], None, burn_rate, "--", "unknown", "No Codex rate-limit logs found.", now)

        reset_changed = self._last_reset_end is None or abs(
            self._last_reset_end - current.resets_at
        ) > 300
        existing = self.history_store.load()
        incoming = [current]
        if backfill or reset_changed:
            incoming.extend(
                collect_current_window_samples(self.sessions_dir, latest=current)
            )

        samples = merge_and_trim_samples(
            existing,
            incoming,
            reset_start=current.reset_start,
            reset_end=current.resets_at,
        )
        self.history_store.save(samples)
        self._last_reset_end = current.resets_at

        burn_rate = calculate_burn_rate(samples, current=samples[-1] if samples else current)
        title = format_multiple(burn_rate.multiple)
        eta_text = format_eta(burn_rate.eta_minutes)
        error = None
        if current.resets_at < now:
            error = "Latest Codex limit sample is from a completed reset window."

        return DisplayState(samples, current, burn_rate, title, eta_text, error, now)

