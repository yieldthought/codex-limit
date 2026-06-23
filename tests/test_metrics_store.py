import tempfile
import unittest
import json
import os
from pathlib import Path

from codex_limit.metrics import calculate_burn_rate, format_eta, format_multiple
from codex_limit.models import QuotaSample
from codex_limit.store import HistoryStore, merge_and_trim_samples


def sample(observed_at, used, resets_at=100000, window=10080, assumed=False):
    return QuotaSample(
        observed_at=float(observed_at),
        used_percent=float(used),
        window_minutes=float(window),
        resets_at=float(resets_at),
        limit_id="codex",
        assumed=assumed,
    )


class MetricsStoreTests(unittest.TestCase):
    def test_burn_rate_uses_two_hour_window(self):
        current = sample(10_000, 12)
        baseline = sample(10_000 - 120 * 60, 10)
        older = sample(10_000 - 6 * 60 * 60, 6)
        rate = calculate_burn_rate([older, baseline, current])
        self.assertEqual(rate.baseline, baseline)
        self.assertAlmostEqual(rate.multiple, 1.7, places=1)
        self.assertEqual(format_multiple(rate.multiple), "1.7x")

    def test_burn_rate_tracks_sub_two_percent_over_two_hours(self):
        current = sample(10_000, 11)
        baseline = sample(10_000 - 120 * 60, 10)
        rate = calculate_burn_rate([baseline, current])
        self.assertAlmostEqual(rate.multiple, 0.8, places=1)

    def test_burn_rate_prefers_shorter_five_percent_burst_window(self):
        current = sample(10_000, 20)
        lookback = sample(10_000 - 120 * 60, 10)
        burst = sample(10_000 - 30 * 60, 15)
        rate = calculate_burn_rate([lookback, burst, current])
        self.assertEqual(rate.baseline, burst)
        self.assertAlmostEqual(rate.multiple, 16.8, places=1)

    def test_burn_rate_uses_full_single_jump_delta(self):
        current = sample(10_000, 46)
        previous = sample(10_000 - 20 * 60, 37)
        rate = calculate_burn_rate([previous, current])
        self.assertEqual(rate.baseline, previous)
        self.assertAlmostEqual(rate.multiple, 45.4, places=1)

    def test_burn_rate_does_not_synthesize_stale_single_jump_at_two_hours(self):
        current = sample(10_000, 46)
        previous = sample(10_000 - 5 * 60 * 60, 37)
        rate = calculate_burn_rate([previous, current])
        self.assertEqual(rate.baseline, previous)
        self.assertAlmostEqual(rate.multiple, 3.0, places=1)

    def test_burn_rate_ignores_assumed_lower_sample_for_jump(self):
        current = sample(10_000, 56)
        observed_lower = sample(10_000 - 9 * 60 * 60, 51)
        assumed_lower = sample(10_000 - 10 * 60, 51, assumed=True)
        rate = calculate_burn_rate([observed_lower, assumed_lower, current])
        self.assertEqual(rate.baseline, observed_lower)
        self.assertAlmostEqual(rate.multiple, 0.9, places=1)

    def test_burn_rate_can_use_assumed_flat_current_for_idle_decay(self):
        observed_lower = sample(10_000 - 60 * 60, 37)
        observed_current = sample(10_000 - 30 * 60, 46)
        assumed_current = sample(10_000, 46, assumed=True)
        rate = calculate_burn_rate([observed_lower, observed_current, assumed_current])
        self.assertEqual(rate.baseline, observed_lower)
        self.assertEqual(rate.baseline.used_percent, 37)
        self.assertAlmostEqual(rate.multiple, 15.1, places=1)

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

    def test_history_store_marks_legacy_assumed_poll_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "session.jsonl"
            source.write_text("{}\n", encoding="utf-8")
            os.utime(source, (1000, 1000))
            path = root / "samples.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "observed_at": 1100,
                        "used_percent": 10,
                        "window_minutes": 10080,
                        "resets_at": 100000,
                        "limit_id": "codex",
                        "source_path": str(source),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            loaded = HistoryStore(path).load()

            self.assertEqual(len(loaded), 1)
            self.assertTrue(loaded[0].assumed)


if __name__ == "__main__":
    unittest.main()
