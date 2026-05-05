import json
import tempfile
import unittest
from pathlib import Path

from codex_limit.controller import CodexLimitMonitor
from codex_limit.models import QuotaSample
from codex_limit.store import HistoryStore


def event(used, timestamp="2026-05-05T09:17:00Z", resets_at=1778541342):
    return json.dumps(
        {
            "timestamp": timestamp,
            "payload": {
                "rate_limits": {
                    "limit_id": "codex",
                    "secondary": {
                        "used_percent": used,
                        "window_minutes": 10080,
                        "resets_at": resets_at,
                    },
                }
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
            self.assertEqual([sample.used_percent for sample in state.samples], [5])


if __name__ == "__main__":
    unittest.main()
