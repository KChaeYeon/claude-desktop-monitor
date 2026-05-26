from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python 3.8 호환


def parse_reset_time(text: str, tz_name: str) -> Optional[datetime]:
    """rate limit 메시지에서 리셋 시각 파싱. 예: 'resets 3:40pm (Asia/Seoul)'"""
    match = re.search(r'resets\s+(\d{1,2}:\d{2})(am|pm)', text, re.IGNORECASE)
    if not match:
        return None

    time_str = match.group(1)
    period = match.group(2).lower()
    hour, minute = map(int, time_str.split(":"))

    if period == "pm" and hour != 12:
        hour += 12
    elif period == "am" and hour == 12:
        hour = 0

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    reset = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if reset <= now:
        reset += timedelta(days=1)

    return reset


class UsageTracker:
    def __init__(self, path: str, session_hours: int) -> None:
        self._path = path
        self._session_hours = session_hours
        self._data: dict = {
            "session_start": None,
            "session_reset_override": None,
            "weekly": {},
        }
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)

    def mark_session_start(self) -> None:
        self._data["session_start"] = datetime.now(timezone.utc).isoformat()
        self._data["session_reset_override"] = None
        self.save()

    def override_reset_time(self, reset_dt: datetime) -> None:
        self._data["session_reset_override"] = reset_dt.isoformat()
        self.save()

    @property
    def session_reset_time(self) -> Optional[datetime]:
        override = self._data.get("session_reset_override")
        if override:
            return datetime.fromisoformat(override)
        start = self._data.get("session_start")
        if not start:
            return None
        start_dt = datetime.fromisoformat(start)
        return start_dt + timedelta(hours=self._session_hours)

    @property
    def session_pct(self) -> float:
        start = self._data.get("session_start")
        if not start:
            return 0.0
        start_dt = datetime.fromisoformat(start)
        elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
        total = self._session_hours * 3600
        return min(elapsed / total * 100, 100.0)

    def add_active_minutes(self, minutes: float) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        weekly = self._data.setdefault("weekly", {})
        weekly[today] = weekly.get(today, 0) + minutes
        self.save()

    @property
    def weekly_active_minutes(self) -> float:
        now = datetime.now(timezone.utc)
        days_since_monday = now.weekday()
        week_start = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        total = 0.0
        for date_str, minutes in self._data.get("weekly", {}).items():
            day = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            if day >= week_start:
                total += minutes
        return total

    @staticmethod
    def context_pct(char_count: int, max_tokens: int = 200_000) -> float:
        estimated_tokens = char_count / 3.5
        return min(estimated_tokens / max_tokens * 100, 100.0)

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
