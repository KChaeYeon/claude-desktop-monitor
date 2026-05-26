from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict

PLAN_LIMITS: dict[str, dict] = {
    "free":    {"session_hours": 1},
    "pro":     {"session_hours": 5},
    "max_5x":  {"session_hours": 5},
    "max_20x": {"session_hours": 5},
}

@dataclass
class AppConfig:
    plan: str
    timezone: str
    window_x: int
    window_y: int

    @property
    def session_hours(self) -> int:
        return PLAN_LIMITS.get(self.plan, {"session_hours": 5})["session_hours"]

def load_config(path: str) -> AppConfig | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return AppConfig(**data)

def save_config(cfg: AppConfig, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
