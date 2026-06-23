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
    lookback_minutes: float = 120.0,
    burst_delta_percent: float = 5.0,
) -> BurnRate:
    ordered = sorted(samples, key=lambda sample: sample.observed_at)
    if current is None:
        current = ordered[-1] if ordered else None
    if current is None or current.window_minutes <= 0:
        return BurnRate(0.0, 0.0, None, current)

    baseline = _adaptive_baseline(
        ordered,
        current=current,
        lookback_minutes=lookback_minutes,
        burst_delta_percent=burst_delta_percent,
    )
    if baseline is None:
        return BurnRate(0.0, 0.0, None, current)

    elapsed_minutes = (current.observed_at - baseline.observed_at) / 60.0
    consumed_percent = current.used_percent - baseline.used_percent
    if elapsed_minutes <= 0 or consumed_percent <= 0:
        return BurnRate(0.0, 0.0, None, current, baseline=baseline)
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
        threshold_percent=burst_delta_percent,
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


def _adaptive_baseline(
    samples: list[QuotaSample],
    *,
    current: QuotaSample,
    lookback_minutes: float,
    burst_delta_percent: float,
) -> QuotaSample | None:
    candidates = [
        sample
        for sample in samples
        if sample.observed_at < current.observed_at and _same_window(sample, current)
        and not (sample.assumed and sample.used_percent < current.used_percent)
    ]
    if not candidates:
        return None

    baselines = [
        baseline
        for baseline in (
            _lookback_baseline(candidates, current, lookback_minutes),
            _burst_baseline(candidates, current, burst_delta_percent),
        )
        if baseline is not None
    ]
    if not baselines:
        return None
    return max(baselines, key=lambda sample: sample.observed_at)


def _lookback_baseline(
    samples: list[QuotaSample],
    current: QuotaSample,
    lookback_minutes: float,
) -> QuotaSample | None:
    target = max(current.reset_start, current.observed_at - lookback_minutes * 60.0)
    previous = [
        sample
        for sample in samples
        if sample.observed_at <= target
    ]
    if previous:
        sample = previous[-1]
        if sample.observed_at < target:
            if sample.used_percent < current.used_percent:
                return sample
            return QuotaSample(
                observed_at=target,
                used_percent=sample.used_percent,
                window_minutes=current.window_minutes,
                resets_at=current.resets_at,
                limit_id=sample.limit_id,
                limit_name=sample.limit_name,
                source_path=sample.source_path,
                assumed=True,
            )
        return sample
    return samples[0]


def _burst_baseline(
    samples: list[QuotaSample],
    current: QuotaSample,
    burst_delta_percent: float,
) -> QuotaSample | None:
    threshold = current.used_percent - burst_delta_percent
    if threshold <= 0:
        return None
    for sample in reversed(samples):
        if not sample.assumed and sample.used_percent <= threshold:
            return sample
    return None


def _same_window(sample: QuotaSample, current: QuotaSample) -> bool:
    return (
        abs(sample.resets_at - current.resets_at) <= 300
        and abs(sample.window_minutes - current.window_minutes) < 1
        and current.reset_start <= sample.observed_at <= current.resets_at
    )
