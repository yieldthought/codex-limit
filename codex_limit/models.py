from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QuotaSample:
    observed_at: float
    used_percent: float
    window_minutes: float
    resets_at: float
    limit_id: str | None = None
    limit_name: str | None = None
    source_path: str | None = None
    assumed: bool = False

    @property
    def remaining_percent(self) -> float:
        return max(0.0, min(100.0, 100.0 - self.used_percent))

    @property
    def reset_start(self) -> float:
        return self.resets_at - self.window_minutes * 60.0

    def to_json(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at,
            "used_percent": self.used_percent,
            "window_minutes": self.window_minutes,
            "resets_at": self.resets_at,
            "limit_id": self.limit_id,
            "limit_name": self.limit_name,
            "source_path": self.source_path,
            "assumed": self.assumed,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "QuotaSample | None":
        try:
            observed_at = float(data["observed_at"])
            used_percent = float(data["used_percent"])
            window_minutes = float(data["window_minutes"])
            resets_at = float(data["resets_at"])
        except (KeyError, TypeError, ValueError):
            return None
        return cls(
            observed_at=observed_at,
            used_percent=used_percent,
            window_minutes=window_minutes,
            resets_at=resets_at,
            limit_id=_optional_str(data.get("limit_id")),
            limit_name=_optional_str(data.get("limit_name")),
            source_path=_optional_str(data.get("source_path")),
            assumed=bool(data.get("assumed", False)),
        )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None
