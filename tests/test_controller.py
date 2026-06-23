import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from codex_limit.controller import (
    CodexLimitMonitor,
    DisplayState,
    LimitDisplayState,
    STATUS_WARNING_ICON,
)
from codex_limit.metrics import BurnRate
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
            self.assertEqual(state.status_title, state.title)
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

    def test_status_title_warns_when_limit_runs_out_before_refresh(self):
        now = 1777971600
        current = QuotaSample(
            observed_at=now,
            used_percent=95,
            window_minutes=300,
            resets_at=now + 60 * 60,
            limit_id="codex",
        )
        burn_rate = BurnRate(
            multiple=8.0,
            percent_per_minute=0.25,
            eta_minutes=20.0,
            current=current,
        )
        limit = LimitDisplayState(
            [],
            current,
            burn_rate,
            "8.0x",
            "20m",
            None,
            warns_before_refresh=True,
        )
        state = DisplayState(limit, None, now)

        self.assertEqual(state.status_title, f"{STATUS_WARNING_ICON} 8.0x")
        self.assertEqual(limit.usage_eta_text, f"{STATUS_WARNING_ICON} 20m")

    def test_refresh_flags_warning_when_limit_runs_out_before_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = root / "sessions"
            sessions.mkdir()
            now = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc).timestamp()
            resets_at = now + 60 * 60
            log = sessions / "current.jsonl"
            log.write_text(
                event(
                    95,
                    timestamp="2026-05-07T10:00:00Z",
                    resets_at=resets_at,
                )
                + "\n",
                encoding="utf-8",
            )

            store = HistoryStore(root / "samples.jsonl")
            store.save(
                [
                    QuotaSample(
                        observed_at=now - 30 * 60,
                        used_percent=87.5,
                        window_minutes=10080,
                        resets_at=resets_at,
                        limit_id="codex",
                    )
                ]
            )

            with patch("codex_limit.controller.time.time", return_value=now):
                state = CodexLimitMonitor(
                    sessions_dir=sessions,
                    history_store=store,
                ).refresh()

            self.assertTrue(state.weekly.warns_before_refresh)
            self.assertEqual(state.weekly.eta_text, "20m")
            self.assertEqual(state.weekly.usage_eta_text, f"{STATUS_WARNING_ICON} 20m")
            self.assertEqual(state.status_title, f"{STATUS_WARNING_ICON} {state.title}")

    def test_status_title_skips_warning_when_refresh_is_soon(self):
        now = 1777971600
        current = QuotaSample(
            observed_at=now,
            used_percent=95,
            window_minutes=300,
            resets_at=now + 20 * 60,
            limit_id="codex",
        )
        burn_rate = BurnRate(
            multiple=8.0,
            percent_per_minute=0.25,
            eta_minutes=20.0,
            current=current,
        )
        limit = LimitDisplayState([], current, burn_rate, "8.0x", "20m", None)
        state = DisplayState(limit, None, now)

        self.assertEqual(state.status_title, "8.0x")
        self.assertEqual(limit.usage_eta_text, "20m")


if __name__ == "__main__":
    unittest.main()
