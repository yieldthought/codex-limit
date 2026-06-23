import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from codex_limit.controller import CodexLimitMonitor
from codex_limit.models import QuotaSample
from codex_limit.store import HistoryStore


def event(
    used,
    timestamp="2026-05-05T09:17:00Z",
    resets_at=1778541342,
    *,
    primary_used=None,
    primary_resets_at=1777972620,
):
    rate_limits = {
        "limit_id": "codex",
        "secondary": {
            "used_percent": used,
            "window_minutes": 10080,
            "resets_at": resets_at,
        },
    }
    if primary_used is not None:
        rate_limits["primary"] = {
            "used_percent": primary_used,
            "window_minutes": 300,
            "resets_at": primary_resets_at,
        }
    return json.dumps(
        {
            "timestamp": timestamp,
            "payload": {
                "rate_limits": rate_limits,
            },
        }
    )


class ControllerTests(unittest.TestCase):
    def test_refresh_discards_poisoned_history_after_reset_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = root / "sessions"
            sessions.mkdir()
            log = sessions / "current.jsonl"
            log.write_text(event(5) + "\n", encoding="utf-8")

            store = HistoryStore(root / "samples.jsonl")
            store.save(
                [
                    QuotaSample(
                        observed_at=1777965000,
                        used_percent=88,
                        window_minutes=10080,
                        resets_at=1778541342,
                        limit_id="codex",
                    )
                ]
            )

            state = CodexLimitMonitor(
                sessions_dir=sessions,
                history_store=store,
            ).refresh()

            self.assertEqual(state.current.used_percent, 5)
            self.assertTrue(all(sample.used_percent == 5 for sample in state.samples))

    def test_refresh_extends_latest_sample_to_poll_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = root / "sessions"
            sessions.mkdir()
            raw_time = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc).timestamp()
            now = raw_time + 60 * 60
            log = sessions / "current.jsonl"
            log.write_text(
                event(10, timestamp="2026-05-07T10:00:00Z") + "\n",
                encoding="utf-8",
            )

            store = HistoryStore(root / "samples.jsonl")
            with patch("codex_limit.controller.time.time", return_value=now):
                state = CodexLimitMonitor(
                    sessions_dir=sessions,
                    history_store=store,
                ).refresh()

            self.assertEqual(state.current.observed_at, now)
            self.assertEqual(state.current.used_percent, 10)
            self.assertTrue(state.current.assumed)
            self.assertIn(raw_time, [sample.observed_at for sample in state.samples])
            self.assertIn(now, [sample.observed_at for sample in state.samples])
            self.assertEqual(
                [sample.observed_at for sample in store.load()],
                [raw_time],
            )

    def test_refresh_populates_five_hour_limit_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = root / "sessions"
            sessions.mkdir()
            raw_time = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc).timestamp()
            now = raw_time + 60
            log = sessions / "current.jsonl"
            log.write_text(
                event(
                    10,
                    timestamp="2026-05-07T10:00:00Z",
                    primary_used=71,
                    primary_resets_at=raw_time + 5 * 60 * 60,
                )
                + "\n",
                encoding="utf-8",
            )

            weekly_store = HistoryStore(root / "weekly.jsonl")
            five_hour_store = HistoryStore(root / "five-hour.jsonl")
            with patch("codex_limit.controller.time.time", return_value=now):
                state = CodexLimitMonitor(
                    sessions_dir=sessions,
                    history_store=weekly_store,
                    five_hour_history_store=five_hour_store,
                ).refresh()

            self.assertEqual(state.current.used_percent, 10)
            self.assertIsNotNone(state.five_hour)
            self.assertEqual(state.five_hour.current.used_percent, 71)
            self.assertEqual(state.five_hour.current.window_minutes, 300)
            self.assertEqual([sample.used_percent for sample in weekly_store.load()], [10])
            self.assertEqual([sample.used_percent for sample in five_hour_store.load()], [71])

    def test_refresh_counts_idle_time_in_burn_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = root / "sessions"
            sessions.mkdir()
            raw_time = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc).timestamp()
            now = raw_time + 30 * 60
            log = sessions / "current.jsonl"
            log.write_text(
                event(12, timestamp="2026-05-07T10:00:00Z") + "\n",
                encoding="utf-8",
            )

            store = HistoryStore(root / "samples.jsonl")
            store.save(
                [
                    QuotaSample(
                        observed_at=raw_time - 30 * 60,
                        used_percent=10,
                        window_minutes=10080,
                        resets_at=1778541342,
                        limit_id="codex",
                    )
                ]
            )
            with patch("codex_limit.controller.time.time", return_value=now):
                state = CodexLimitMonitor(
                    sessions_dir=sessions,
                    history_store=store,
                ).refresh()

            self.assertAlmostEqual(state.burn_rate.multiple, 3.4, places=1)


if __name__ == "__main__":
    unittest.main()
