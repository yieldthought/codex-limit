import tempfile
import unittest
from pathlib import Path

from codex_limit.metrics import calculate_burn_rate, format_eta, format_multiple
from codex_limit.models import QuotaSample
from codex_limit.store import HistoryStore, merge_and_trim_samples


def sample(observed_at, used, resets_at=100000, window=10080):
    return QuotaSample(
        observed_at=float(observed_at),
        used_percent=float(used),
        window_minutes=float(window),
        resets_at=float(resets_at),
        limit_id="codex",
    )


class MetricsStoreTests(unittest.TestCase):
    def test_burn_rate_prefers_two_percent_delta(self):
        current = sample(10_000, 12)
        baseline = sample(10_000 - 28.8 * 60, 10)
        rate = calculate_burn_rate([baseline, current])
        self.assertAlmostEqual(rate.multiple, 7.0, places=1)
        self.assertEqual(rate.threshold_percent, 2.0)
        self.assertEqual(format_multiple(rate.multiple), "7.0x")

    def test_burn_rate_falls_back_to_one_percent_delta(self):
        current = sample(10_000, 11)
        baseline = sample(10_000 - 201.6 * 60, 10)
        rate = calculate_burn_rate([baseline, current])
        self.assertAlmostEqual(rate.multiple, 0.5, places=1)
        self.assertEqual(rate.threshold_percent, 1.0)

    def test_burn_rate_zero_when_no_positive_delta(self):
        rate = calculate_burn_rate([sample(100, 10), sample(200, 10)])
        self.assertEqual(rate.multiple, 0.0)
        self.assertEqual(rate.percent_per_minute, 0.0)
        self.assertIsNone(rate.eta_minutes)

    def test_eta_format(self):
        self.assertEqual(format_eta(184), "3h 4m")
        self.assertEqual(format_eta(4), "4m")
        self.assertEqual(format_eta(None), "unknown")

    def test_merge_and_trim_samples(self):
        kept = sample(200, 3)
        duplicate = sample(200, 4)
        old = sample(50, 1)
        future = sample(500, 5)
        merged = merge_and_trim_samples(
            [old, kept],
            [duplicate, future],
            reset_start=100,
            reset_end=400,
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].used_percent, 4)

    def test_merge_keeps_usage_monotonic_with_stale_parallel_samples(self):
        merged = merge_and_trim_samples(
            [],
            [sample(100, 48), sample(120, 50), sample(140, 48)],
            reset_start=0,
            reset_end=100000,
        )
        self.assertEqual([sample.used_percent for sample in merged], [48, 50, 50])

    def test_history_store_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.jsonl"
            store = HistoryStore(path)
            samples = [sample(100, 1), sample(200, 2)]
            store.save(samples)
            self.assertEqual(store.load(), samples)


if __name__ == "__main__":
    unittest.main()
