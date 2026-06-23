from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path

from .metrics import BurnRate, calculate_burn_rate, format_eta, format_multiple
from .models import QuotaSample
from .reader import (
    WINDOW_FIVE_HOUR,
    WINDOW_WEEKLY,
    collect_current_window_samples,
    latest_snapshot,
)
from .store import FIVE_HOUR_HISTORY_FILE_NAME, HistoryStore, merge_and_trim_samples


HISTORY_RESET_DROP_PERCENT = 20.0


@dataclass(frozen=True)
class LimitDisplayState:
    samples: list[QuotaSample]
    current: QuotaSample | None
    burn_rate: BurnRate
    title: str
    eta_text: str
    error: str | None


@dataclass(frozen=True)
class DisplayState:
    weekly: LimitDisplayState
    five_hour: LimitDisplayState | None
    refreshed_at: float

    @property
    def samples(self) -> list[QuotaSample]:
        return self.weekly.samples

    @property
    def current(self) -> QuotaSample | None:
        return self.weekly.current

    @property
    def burn_rate(self) -> BurnRate:
        return self.weekly.burn_rate

    @property
    def title(self) -> str:
        return self.weekly.title

    @property
    def eta_text(self) -> str:
        return self.weekly.eta_text

    @property
    def error(self) -> str | None:
        return self.weekly.error


class CodexLimitMonitor:
    def __init__(
        self,
        *,
        sessions_dir: Path | None = None,
        history_store: HistoryStore | None = None,
        five_hour_history_store: HistoryStore | None = None,
    ):
        self.sessions_dir = sessions_dir
        self.history_store = history_store or HistoryStore()
        self.five_hour_history_store = five_hour_history_store or HistoryStore(
            file_name=FIVE_HOUR_HISTORY_FILE_NAME
        )
        self._last_reset_end_by_kind: dict[str, float | None] = {
            WINDOW_WEEKLY: None,
            WINDOW_FIVE_HOUR: None,
        }

    def refresh(self, *, backfill: bool = False) -> DisplayState:
        now = time.time()
        weekly = self._refresh_limit(
            window_kind=WINDOW_WEEKLY,
            history_store=self.history_store,
            backfill=backfill,
            now=now,
        )
        five_hour = self._refresh_limit(
            window_kind=WINDOW_FIVE_HOUR,
            history_store=self.five_hour_history_store,
            backfill=backfill,
            now=now,
        )
        return DisplayState(weekly, five_hour, now)

    def _refresh_limit(
        self,
        *,
        window_kind: str,
        history_store: HistoryStore,
        backfill: bool,
        now: float,
    ) -> LimitDisplayState:
        latest = latest_snapshot(self.sessions_dir, window_kind=window_kind)
        if latest is None:
            burn_rate = BurnRate(0.0, 0.0, None, None)
            return LimitDisplayState(
                [],
                None,
                burn_rate,
                "--",
                "unknown",
                "No Codex rate-limit logs found.",
            )

        current = _assume_no_usage_until_now(latest, now)
        last_reset_end = self._last_reset_end_by_kind.get(window_kind)
        reset_changed = last_reset_end is None or abs(
            last_reset_end - current.resets_at
        ) > 300
        existing = history_store.load()
        history_conflicts = _history_conflicts_with_current(existing, current)
        if history_conflicts:
            existing = []
        incoming = [latest]
        if backfill or reset_changed or history_conflicts:
            incoming.extend(
                collect_current_window_samples(
                    self.sessions_dir,
                    latest=latest,
                    window_kind=window_kind,
                )
            )

        observed_samples = merge_and_trim_samples(
            existing,
            incoming,
            reset_start=current.reset_start,
            reset_end=current.resets_at,
            resets_at=current.resets_at,
            window_minutes=current.window_minutes,
        )
        observed_samples = [sample for sample in observed_samples if not sample.assumed]
        history_store.save(observed_samples)
        self._last_reset_end_by_kind[window_kind] = current.resets_at

        display_samples = observed_samples
        if current.observed_at != latest.observed_at:
            display_samples = merge_and_trim_samples(
                observed_samples,
                [current],
                reset_start=current.reset_start,
                reset_end=current.resets_at,
                resets_at=current.resets_at,
                window_minutes=current.window_minutes,
            )

        display_current = display_samples[-1] if display_samples else current
        burn_rate = calculate_burn_rate(display_samples, current=display_current)
        title = format_multiple(burn_rate.multiple)
        eta_text = format_eta(burn_rate.eta_minutes)
        error = None
        if display_current.resets_at < now:
            error = "Latest Codex limit sample is from a completed reset window."

        return LimitDisplayState(
            display_samples,
            display_current,
            burn_rate,
            title,
            eta_text,
            error,
        )


def _assume_no_usage_until_now(sample: QuotaSample, now: float) -> QuotaSample:
    if sample.observed_at >= now or now >= sample.resets_at:
        return sample
    return replace(sample, observed_at=now, assumed=True)


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
