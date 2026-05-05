from __future__ import annotations

import math
from dataclasses import dataclass

from .models import QuotaSample


@dataclass(frozen=True)
class BurnRate:
    multiple: float
    percent_per_minute: float
    eta_minutes: float | None
    current: QuotaSample | None
    baseline: QuotaSample | None = None
    threshold_percent: float | None = None


def calculate_burn_rate(
    samples: list[QuotaSample],
    *,
    current: QuotaSample | None = None,
    lookback_minutes: float = 360.0,
    min_elapsed_minutes: float = 60.0,
    min_delta_percent: float = 2.0,
) -> BurnRate:
    ordered = sorted(samples, key=lambda sample: sample.observed_at)
    if current is None:
        current = ordered[-1] if ordered else None
    if current is None or current.window_minutes <= 0:
        return BurnRate(0.0, 0.0, None, current)

    baseline = _baseline_for_threshold(
        ordered,
        current=current,
        threshold=min_delta_percent,
        lookback_minutes=lookback_minutes,
        min_elapsed_minutes=min_elapsed_minutes,
    )
    if baseline is None:
        return BurnRate(0.0, 0.0, None, current)

    elapsed_minutes = (current.observed_at - baseline.observed_at) / 60.0
    consumed_percent = current.used_percent - baseline.used_percent
    percent_per_minute = consumed_percent / elapsed_minutes
    real_time_percent_per_minute = 100.0 / current.window_minutes
    multiple = percent_per_minute / real_time_percent_per_minute
    eta_minutes = (
        current.remaining_percent / percent_per_minute
        if percent_per_minute > 0
        else None
    )
    return BurnRate(
        max(0.0, multiple),
        max(0.0, percent_per_minute),
        eta_minutes,
        current,
        baseline=baseline,
        threshold_percent=min_delta_percent,
    )


def format_multiple(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "--"
    return f"{max(0.0, value):.1f}x"


def format_eta(minutes: float | None) -> str:
    if minutes is None or not math.isfinite(minutes):
        return "unknown"
    total_minutes = max(0, int(round(minutes)))
    hours, mins = divmod(total_minutes, 60)
    if hours <= 0:
        return f"{mins}m"
    return f"{hours}h {mins}m"


def _baseline_for_threshold(
    samples: list[QuotaSample],
    *,
    current: QuotaSample,
    threshold: float,
    lookback_minutes: float,
    min_elapsed_minutes: float,
) -> QuotaSample | None:
    earliest = current.observed_at - lookback_minutes * 60.0
    candidates = [
        sample
        for sample in samples
        if earliest <= sample.observed_at < current.observed_at
        and current.used_percent - sample.used_percent >= threshold
        and current.observed_at - sample.observed_at >= min_elapsed_minutes * 60.0
        and abs(sample.resets_at - current.resets_at) <= 300
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda sample: sample.observed_at)
