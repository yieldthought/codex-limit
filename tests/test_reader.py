import json
import tempfile
import unittest
from pathlib import Path

from codex_limit.reader import (
    collect_current_window_samples,
    latest_snapshot,
    recent_session_files,
    sample_from_json_line,
)


def event(rate_limits, timestamp="2026-04-24T06:38:54.251Z"):
    return json.dumps({"timestamp": timestamp, "payload": {"rate_limits": rate_limits}})


class ReaderTests(unittest.TestCase):
    def test_uses_codex_limit_and_weekly_secondary(self):
        line = event(
            {
                "limit_id": "codex",
                "limit_name": None,
                "primary": {"used_percent": 17, "window_minutes": 300, "resets_at": 2000},
                "secondary": {"used_percent": 4, "window_minutes": 10080, "resets_at": 100000},
            }
        )
        sample = sample_from_json_line(line)
        self.assertIsNotNone(sample)
        self.assertEqual(sample.limit_id, "codex")
        self.assertEqual(sample.used_percent, 4)
        self.assertEqual(sample.window_minutes, 10080)
        self.assertEqual(sample.resets_at, 100000)

    def test_ignores_spark_limit(self):
        line = event(
            {
                "limit_id": "codex_bengalfox",
                "limit_name": "GPT-5.3-Codex-Spark",
                "secondary": {"used_percent": 1, "window_minutes": 10080, "resets_at": 100000},
            }
        )
        self.assertIsNone(sample_from_json_line(line))

    def test_accepts_legacy_limit_without_limit_id(self):
        line = event(
            {
                "primary": {"used_percent": 5, "window_minutes": 300, "resets_at": 2000},
                "secondary": {"used_percent": 22, "window_minutes": 10080, "resets_at": 100000},
            }
        )
        sample = sample_from_json_line(line)
        self.assertIsNotNone(sample)
        self.assertEqual(sample.used_percent, 22)

    def test_supports_resets_in_seconds(self):
        line = event(
            {
                "limit_id": "codex",
                "secondary": {
                    "used_percent": 10,
                    "window_minutes": 10080,
                    "resets_in_seconds": 60,
                },
            },
            timestamp="1970-01-01T00:01:00Z",
        )
        sample = sample_from_json_line(line)
        self.assertIsNotNone(sample)
        self.assertEqual(sample.resets_at, 120)

    def test_backfill_keeps_current_reset_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            day = root / "2026" / "04" / "24"
            day.mkdir(parents=True)
            old_file = day / "old.jsonl"
            new_file = day / "new.jsonl"
            old_file.write_text(
                event(
                    {
                        "limit_id": "codex",
                        "secondary": {
                            "used_percent": 88,
                            "window_minutes": 10080,
                            "resets_at": 10000,
                        },
                    },
                    timestamp="1970-01-01T01:00:00Z",
                )
                + "\n",
                encoding="utf-8",
            )
            new_file.write_text(
                "\n".join(
                    [
                        event(
                            {
                                "limit_id": "codex",
                                "secondary": {
                                    "used_percent": 4,
                                    "window_minutes": 10080,
                                    "resets_at": 604800,
                                },
                            },
                            timestamp="1970-01-02T00:00:00Z",
                        ),
                        event(
                            {
                                "limit_id": "codex",
                                "secondary": {
                                    "used_percent": 6,
                                    "window_minutes": 10080,
                                    "resets_at": 604800,
                                },
                            },
                            timestamp="1970-01-02T01:00:00Z",
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            latest = latest_snapshot(root)
            samples = collect_current_window_samples(root, latest=latest)
            self.assertEqual([sample.used_percent for sample in samples], [4, 6])

    def test_latest_snapshot_scans_past_newer_file_with_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            stale = root / "stale.jsonl"
            fresh = root / "fresh.jsonl"
            stale.write_text(
                event(
                    {
                        "limit_id": "codex",
                        "secondary": {
                            "used_percent": 48,
                            "window_minutes": 10080,
                            "resets_at": 604800,
                        },
                    },
                    timestamp="1970-01-02T00:00:00Z",
                )
                + "\n",
                encoding="utf-8",
            )
            fresh.write_text(
                event(
                    {
                        "limit_id": "codex",
                        "secondary": {
                            "used_percent": 50,
                            "window_minutes": 10080,
                            "resets_at": 604800,
                        },
                    },
                    timestamp="1970-01-02T00:01:00Z",
                )
                + "\n",
                encoding="utf-8",
            )
            stale.touch()
            latest = latest_snapshot(root)
            self.assertIsNotNone(latest)
            self.assertEqual(latest.used_percent, 50)

    def test_recent_session_files_limits_large_log_trees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = []
            for index in range(250):
                path = root / f"{index:03d}.jsonl"
                path.write_text("", encoding="utf-8")
                files.append(path)
            for index, path in enumerate(files):
                path.touch()
            self.assertLessEqual(len(recent_session_files(root)), 200)


if __name__ == "__main__":
    unittest.main()
