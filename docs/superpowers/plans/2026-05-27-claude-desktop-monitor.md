# Claude Desktop Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Desktop App(claude.ai GUI, Windows)의 세션/주간/컨텍스트 사용량과 현재 상태를 실시간으로 표시하는 always-on-top Python 오버레이 창을 구현한다.

**Architecture:** Windows UIAutomation으로 Claude Desktop App UI를 0.5초마다 폴링해 상태를 감지하고, tkinter always-on-top 창에 사용량을 표시한다. config.json 없으면 최초 실행 플랜 선택 다이얼로그를 띄우고, tracker.json에 세션/주간 데이터를 누적한다.

**Tech Stack:** Python 3.8+, tkinter(표준), uiautomation 2.0.18+, pytest

---

## 파일 구조

| 파일 | 책임 |
|------|------|
| `main.py` | 진입점 — config 존재 여부 확인 후 setup 또는 overlay 시작 |
| `monitor/__init__.py` | 빈 파일 |
| `monitor/config.py` | config.json 로드/저장, PLAN_LIMITS 상수 |
| `monitor/state_machine.py` | UISnapshot 데이터클래스, 5가지 상태 전환 로직 |
| `monitor/tracker.py` | 5h 윈도우 계산, 주간 누적, rate limit 시간 파싱 |
| `monitor/accessibility.py` | uiautomation으로 Claude 앱 폴링 → UISnapshot 반환 |
| `monitor/overlay.py` | tkinter always-on-top 창, 1초마다 UI 갱신 |
| `setup/__init__.py` | 빈 파일 |
| `setup/setup_dialog.py` | tkinter 최초 실행 플랜 선택 다이얼로그 |
| `requirements.txt` | uiautomation>=2.0.18 |
| `tests/test_config.py` | config.py 단위 테스트 |
| `tests/test_state_machine.py` | 상태 전환 단위 테스트 |
| `tests/test_tracker.py` | 시간 계산 및 파싱 단위 테스트 |

---

## Task 1: 프로젝트 스캐폴딩 + requirements.txt

**Files:**
- Create: `requirements.txt`
- Create: `monitor/__init__.py`
- Create: `setup/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: requirements.txt 작성**

```
uiautomation>=2.0.18
pytest>=7.0
```

- [ ] **Step 2: __init__.py 파일 생성**

`monitor/__init__.py`, `setup/__init__.py`, `tests/__init__.py` 모두 빈 파일로 생성.

```bash
touch /mnt/d/claude-desktop-monitor/monitor/__init__.py
touch /mnt/d/claude-desktop-monitor/setup/__init__.py
touch /mnt/d/claude-desktop-monitor/tests/__init__.py
```

- [ ] **Step 3: 커밋**

```bash
cd /mnt/d/claude-desktop-monitor
git add requirements.txt monitor/__init__.py setup/__init__.py tests/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: config.py — 설정 관리

**Files:**
- Create: `monitor/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_config.py`:
```python
import json
import os
import tempfile
import pytest
from monitor.config import AppConfig, load_config, save_config, PLAN_LIMITS

def test_plan_limits_has_required_plans():
    assert "free" in PLAN_LIMITS
    assert "pro" in PLAN_LIMITS
    assert "max_5x" in PLAN_LIMITS
    assert "max_20x" in PLAN_LIMITS

def test_plan_limits_session_hours():
    assert PLAN_LIMITS["pro"]["session_hours"] == 5
    assert PLAN_LIMITS["free"]["session_hours"] == 1

def test_load_config_returns_default_when_file_missing():
    config = load_config("/nonexistent/path/config.json")
    assert config is None

def test_save_and_load_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        cfg = AppConfig(plan="pro", timezone="Asia/Seoul", window_x=100, window_y=200)
        save_config(cfg, path)
        loaded = load_config(path)
        assert loaded.plan == "pro"
        assert loaded.timezone == "Asia/Seoul"
        assert loaded.window_x == 100
        assert loaded.window_y == 200
    finally:
        os.unlink(path)

def test_appconfig_session_hours():
    cfg = AppConfig(plan="pro", timezone="Asia/Seoul", window_x=0, window_y=0)
    assert cfg.session_hours == 5

def test_appconfig_session_hours_free():
    cfg = AppConfig(plan="free", timezone="Asia/Seoul", window_x=0, window_y=0)
    assert cfg.session_hours == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /mnt/d/claude-desktop-monitor
python -m pytest tests/test_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'monitor.config'`

- [ ] **Step 3: monitor/config.py 구현**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_config.py -v
```
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add monitor/config.py tests/test_config.py
git commit -m "feat: add config module with plan limits"
```

---

## Task 3: state_machine.py — 상태 전환

**Files:**
- Create: `monitor/state_machine.py`
- Create: `tests/test_state_machine.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_state_machine.py`:
```python
import time
import pytest
from monitor.state_machine import AppState, UISnapshot, StateMachine

def test_initial_state_is_idle():
    sm = StateMachine()
    assert sm.state == AppState.IDLE

def test_app_not_running_stays_idle():
    sm = StateMachine()
    snap = UISnapshot(app_running=False, is_loading=False, is_streaming=False,
                      rate_limit_text=None, conversation_char_count=0)
    sm.update(snap)
    assert sm.state == AppState.IDLE

def test_loading_transitions_to_thinking():
    sm = StateMachine()
    snap = UISnapshot(app_running=True, is_loading=True, is_streaming=False,
                      rate_limit_text=None, conversation_char_count=0)
    sm.update(snap)
    assert sm.state == AppState.THINKING

def test_streaming_transitions_to_writing():
    sm = StateMachine()
    snap = UISnapshot(app_running=True, is_loading=False, is_streaming=True,
                      rate_limit_text=None, conversation_char_count=100)
    sm.update(snap)
    assert sm.state == AppState.WRITING

def test_rate_limit_text_transitions_to_limit_reached():
    sm = StateMachine()
    snap = UISnapshot(app_running=True, is_loading=False, is_streaming=False,
                      rate_limit_text="resets 3:40pm (Asia/Seoul)",
                      conversation_char_count=0)
    sm.update(snap)
    assert sm.state == AppState.LIMIT_REACHED

def test_done_after_writing_stops():
    sm = StateMachine()
    writing_snap = UISnapshot(app_running=True, is_loading=False, is_streaming=True,
                              rate_limit_text=None, conversation_char_count=100)
    sm.update(writing_snap)
    assert sm.state == AppState.WRITING

    idle_snap = UISnapshot(app_running=True, is_loading=False, is_streaming=False,
                           rate_limit_text=None, conversation_char_count=100)
    sm.update(idle_snap)
    assert sm.state == AppState.DONE

def test_done_reverts_to_idle_after_30s():
    sm = StateMachine()
    writing_snap = UISnapshot(app_running=True, is_loading=False, is_streaming=True,
                              rate_limit_text=None, conversation_char_count=100)
    sm.update(writing_snap)
    idle_snap = UISnapshot(app_running=True, is_loading=False, is_streaming=False,
                           rate_limit_text=None, conversation_char_count=100)
    sm.update(idle_snap)
    assert sm.state == AppState.DONE

    sm._done_since = time.time() - 31
    sm.update(idle_snap)
    assert sm.state == AppState.IDLE
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_state_machine.py -v
```
Expected: `ModuleNotFoundError: No module named 'monitor.state_machine'`

- [ ] **Step 3: monitor/state_machine.py 구현**

```python
from __future__ import annotations
import time
from dataclasses import dataclass
from enum import Enum

class AppState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    WRITING = "writing"
    DONE = "done"
    LIMIT_REACHED = "limit_reached"

@dataclass
class UISnapshot:
    app_running: bool
    is_loading: bool
    is_streaming: bool
    rate_limit_text: str | None
    conversation_char_count: int

class StateMachine:
    DONE_TIMEOUT = 30.0

    def __init__(self) -> None:
        self.state = AppState.IDLE
        self._done_since: float | None = None

    def update(self, snap: UISnapshot) -> AppState:
        if not snap.app_running:
            self.state = AppState.IDLE
            self._done_since = None
            return self.state

        if snap.rate_limit_text:
            self.state = AppState.LIMIT_REACHED
            self._done_since = None
            return self.state

        if snap.is_streaming:
            self.state = AppState.WRITING
            self._done_since = None
            return self.state

        if snap.is_loading:
            self.state = AppState.THINKING
            self._done_since = None
            return self.state

        if self.state in (AppState.WRITING, AppState.THINKING):
            self.state = AppState.DONE
            self._done_since = time.time()
            return self.state

        if self.state == AppState.DONE:
            if self._done_since and time.time() - self._done_since > self.DONE_TIMEOUT:
                self.state = AppState.IDLE
                self._done_since = None

        return self.state
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_state_machine.py -v
```
Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add monitor/state_machine.py tests/test_state_machine.py
git commit -m "feat: add state machine with 5 states"
```

---

## Task 4: tracker.py — 사용량 계산

**Files:**
- Create: `monitor/tracker.py`
- Create: `tests/test_tracker.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tracker.py`:
```python
import json
import os
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from monitor.tracker import UsageTracker, parse_reset_time

# --- parse_reset_time 테스트 ---

def test_parse_reset_time_pm():
    text = "You've hit your session limit · resets 3:40pm (Asia/Seoul)"
    result = parse_reset_time(text, "Asia/Seoul")
    assert result is not None
    assert result.hour == 15
    assert result.minute == 40

def test_parse_reset_time_am():
    text = "You've hit your limit · resets 9:15am (Asia/Seoul)"
    result = parse_reset_time(text, "Asia/Seoul")
    assert result is not None
    assert result.hour == 9
    assert result.minute == 15

def test_parse_reset_time_returns_none_for_no_match():
    result = parse_reset_time("Some other error message", "Asia/Seoul")
    assert result is None

# --- UsageTracker 테스트 ---

def test_session_pct_zero_before_activity():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)
    try:
        tracker = UsageTracker(path, session_hours=5)
        assert tracker.session_pct == 0.0
    finally:
        if os.path.exists(path):
            os.unlink(path)

def test_session_pct_after_start():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)
    try:
        tracker = UsageTracker(path, session_hours=5)
        tracker.mark_session_start()
        pct = tracker.session_pct
        assert 0.0 <= pct <= 1.0
    finally:
        if os.path.exists(path):
            os.unlink(path)

def test_session_reset_time_is_5h_after_start():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)
    try:
        tracker = UsageTracker(path, session_hours=5)
        before = datetime.now(timezone.utc)
        tracker.mark_session_start()
        reset = tracker.session_reset_time
        assert reset is not None
        diff = (reset - before).total_seconds()
        assert 17999 <= diff <= 18001
    finally:
        if os.path.exists(path):
            os.unlink(path)

def test_weekly_pct_increments_with_active_minutes():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)
    try:
        tracker = UsageTracker(path, session_hours=5)
        tracker.add_active_minutes(60)
        assert tracker.weekly_active_minutes == 60
    finally:
        if os.path.exists(path):
            os.unlink(path)

def test_context_pct():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)
    try:
        tracker = UsageTracker(path, session_hours=5)
        pct = tracker.context_pct(char_count=70000)
        assert abs(pct - (70000 / 3.5 / 200000 * 100)) < 0.01
    finally:
        if os.path.exists(path):
            os.unlink(path)

def test_tracker_persists_across_instances():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)
    try:
        t1 = UsageTracker(path, session_hours=5)
        t1.mark_session_start()
        t1.add_active_minutes(30)
        t1.save()

        t2 = UsageTracker(path, session_hours=5)
        assert t2.weekly_active_minutes == 30
        assert t2.session_reset_time is not None
    finally:
        if os.path.exists(path):
            os.unlink(path)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_tracker.py -v
```
Expected: `ModuleNotFoundError: No module named 'monitor.tracker'`

- [ ] **Step 3: monitor/tracker.py 구현**

```python
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

    # --- 세션 ---

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

    # --- 주간 ---

    def add_active_minutes(self, minutes: int) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        weekly = self._data.setdefault("weekly", {})
        weekly[today] = weekly.get(today, 0) + minutes
        self.save()

    @property
    def weekly_active_minutes(self) -> int:
        now = datetime.now(timezone.utc)
        days_since_monday = now.weekday()
        week_start = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        total = 0
        for date_str, minutes in self._data.get("weekly", {}).items():
            day = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            if day >= week_start:
                total += minutes
        return total

    # --- 컨텍스트 ---

    @staticmethod
    def context_pct(char_count: int, max_tokens: int = 200_000) -> float:
        estimated_tokens = char_count / 3.5
        return min(estimated_tokens / max_tokens * 100, 100.0)

    # --- 저장 ---

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_tracker.py -v
```
Expected: 9 passed

- [ ] **Step 5: 커밋**

```bash
git add monitor/tracker.py tests/test_tracker.py
git commit -m "feat: add usage tracker with session/weekly/context calculation"
```

---

## Task 5: accessibility.py — UIAutomation 폴링

**Files:**
- Create: `monitor/accessibility.py`

> ⚠️ 이 모듈은 Windows 전용이며 `uiautomation` 설치가 필요하다. 먼저 `pip install uiautomation` 실행.

- [ ] **Step 1: uiautomation 설치**

```bash
pip install uiautomation>=2.0.18
```

- [ ] **Step 2: monitor/accessibility.py 구현**

```python
from __future__ import annotations
import re
from monitor.state_machine import UISnapshot

try:
    import uiautomation as auto
    _UIA_AVAILABLE = True
except ImportError:
    _UIA_AVAILABLE = False

CLAUDE_WINDOW_NAMES = ("Claude", "Claude -")


def _find_claude_window():
    """Claude Desktop App 창을 찾아 반환. 없으면 None."""
    if not _UIA_AVAILABLE:
        return None
    root = auto.GetRootControl()
    for ctrl in root.GetChildren():
        name = ctrl.Name or ""
        if any(name == n or name.startswith(n + " ") for n in CLAUDE_WINDOW_NAMES):
            return ctrl
    return None


def _find_stop_button(window) -> bool:
    """'Stop' 버튼 또는 생성 중 표시 요소 존재 여부 반환."""
    try:
        btn = window.ButtonControl(searchDepth=15, Name="Stop")
        if btn.Exists(0, 0):
            return True
        btn2 = window.ButtonControl(searchDepth=15, Name="Stop generating")
        return btn2.Exists(0, 0)
    except Exception:
        return False


def _get_conversation_text_length(window) -> int:
    """대화 영역 텍스트 전체 길이 추정 (토큰 계산에 사용)."""
    try:
        total = 0
        for ctrl in window.GetChildren():
            name = ctrl.Name or ""
            total += len(name)
        return total
    except Exception:
        return 0


def _find_rate_limit_text(window) -> str | None:
    """rate limit 메시지 텍스트 탐색. 'resets X:XXam/pm' 패턴 포함 시 반환."""
    pattern = re.compile(r'resets\s+\d{1,2}:\d{2}(?:am|pm)', re.IGNORECASE)
    try:
        def search(ctrl, depth=0):
            if depth > 20:
                return None
            name = ctrl.Name or ""
            if pattern.search(name):
                return name
            for child in ctrl.GetChildren():
                result = search(child, depth + 1)
                if result:
                    return result
            return None
        return search(window)
    except Exception:
        return None


def get_snapshot(prev_char_count: int = 0) -> UISnapshot:
    """Claude Desktop App UI를 폴링해 UISnapshot을 반환한다."""
    window = _find_claude_window()
    if window is None:
        return UISnapshot(
            app_running=False,
            is_loading=False,
            is_streaming=False,
            rate_limit_text=None,
            conversation_char_count=0,
        )

    rate_limit_text = _find_rate_limit_text(window)
    stop_active = _find_stop_button(window)
    char_count = _get_conversation_text_length(window)
    is_streaming = stop_active and char_count > prev_char_count
    is_loading = stop_active and not is_streaming

    return UISnapshot(
        app_running=True,
        is_loading=is_loading,
        is_streaming=is_streaming,
        rate_limit_text=rate_limit_text,
        conversation_char_count=char_count,
    )


def debug_dump_tree(max_depth: int = 5) -> None:
    """Claude 앱 UI 트리를 콘솔에 출력 (디버깅용)."""
    window = _find_claude_window()
    if window is None:
        print("Claude Desktop App 창을 찾을 수 없습니다.")
        return

    def dump(ctrl, depth=0):
        if depth > max_depth:
            return
        indent = "  " * depth
        print(f"{indent}[{ctrl.ControlTypeName}] Name={ctrl.Name!r}")
        for child in ctrl.GetChildren():
            dump(child, depth + 1)

    dump(window)
```

- [ ] **Step 3: 수동 검증 — Claude Desktop App 실행 상태에서**

```bash
cd /mnt/d/claude-desktop-monitor
python -c "from monitor.accessibility import debug_dump_tree; debug_dump_tree()"
```
Expected: Claude Desktop App UI 트리가 출력됨. "Stop" 버튼의 실제 Name을 확인하고, 다르면 `_find_stop_button` 안의 Name 값 수정.

- [ ] **Step 4: 커밋**

```bash
git add monitor/accessibility.py
git commit -m "feat: add Windows UIAutomation polling module"
```

---

## Task 6: setup_dialog.py — 최초 실행 다이얼로그

**Files:**
- Create: `setup/setup_dialog.py`

- [ ] **Step 1: setup/setup_dialog.py 구현**

```python
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Optional
from monitor.config import AppConfig, save_config, PLAN_LIMITS


def _detect_timezone() -> str:
    try:
        from zoneinfo import ZoneInfo
        import time as _time
        offset = -_time.timezone // 3600
        if _time.daylight:
            offset = -_time.altzone // 3600
        mapping = {9: "Asia/Seoul", 0: "UTC", -5: "America/New_York",
                   -8: "America/Los_Angeles", 1: "Europe/London"}
        return mapping.get(offset, "UTC")
    except Exception:
        return "UTC"


PLAN_LABELS = {
    "free":    "Free",
    "pro":     "Pro",
    "max_5x":  "Max (5x)",
    "max_20x": "Max (20x)",
}


def run_setup(config_path: str) -> Optional[AppConfig]:
    """최초 실행 설정 다이얼로그를 실행하고 AppConfig를 반환. 취소 시 None."""
    result: list[Optional[AppConfig]] = [None]

    root = tk.Tk()
    root.title("Claude Monitor — 초기 설정")
    root.geometry("320x260")
    root.resizable(False, False)
    root.configure(bg="#16213e")
    root.eval("tk::PlaceWindow . center")

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TLabel", background="#16213e", foreground="#a8a8b3",
                    font=("Segoe UI", 10))
    style.configure("Title.TLabel", background="#16213e", foreground="#ffffff",
                    font=("Segoe UI", 13, "bold"))
    style.configure("TRadiobutton", background="#16213e", foreground="#a8a8b3",
                    font=("Segoe UI", 10))
    style.configure("Confirm.TButton", font=("Segoe UI", 10, "bold"))

    ttk.Label(root, text="Claude Desktop Monitor", style="Title.TLabel").pack(pady=(20, 4))
    ttk.Label(root, text="구독 플랜을 선택해주세요").pack(pady=(0, 12))

    plan_var = tk.StringVar(value="pro")
    for key, label in PLAN_LABELS.items():
        ttk.Radiobutton(root, text=label, variable=plan_var, value=key).pack(anchor="w", padx=40)

    ttk.Label(root, text="").pack(pady=4)

    tz_frame = tk.Frame(root, bg="#16213e")
    tz_frame.pack(fill="x", padx=40)
    ttk.Label(tz_frame, text="타임존:").pack(side="left")
    tz_var = tk.StringVar(value=_detect_timezone())
    tz_entry = ttk.Entry(tz_frame, textvariable=tz_var, width=20)
    tz_entry.pack(side="left", padx=8)

    def on_confirm():
        cfg = AppConfig(
            plan=plan_var.get(),
            timezone=tz_var.get().strip() or "UTC",
            window_x=-1,
            window_y=-1,
        )
        save_config(cfg, config_path)
        result[0] = cfg
        root.destroy()

    ttk.Button(root, text="시작", style="Confirm.TButton",
               command=on_confirm).pack(pady=16)

    root.mainloop()
    return result[0]
```

- [ ] **Step 2: 수동 검증**

```bash
cd /mnt/d/claude-desktop-monitor
python -c "from setup.setup_dialog import run_setup; cfg = run_setup('/tmp/test_cfg.json'); print(cfg)"
```
Expected: 다이얼로그 창이 뜨고, 확인 클릭 시 AppConfig 객체가 출력됨.

- [ ] **Step 3: 커밋**

```bash
git add setup/setup_dialog.py
git commit -m "feat: add first-run setup dialog"
```

---

## Task 7: overlay.py — tkinter 오버레이 창

**Files:**
- Create: `monitor/overlay.py`

- [ ] **Step 1: monitor/overlay.py 구현**

```python
from __future__ import annotations
import tkinter as tk
from datetime import datetime, timezone
from typing import Callable
from monitor.state_machine import AppState

BG = "#16213e"
BG_ITEM = "#0f1f3d"
FG_DIM = "#444444"
FG_MID = "#a8a8b3"

COLORS = {
    "session":  "#e94560",
    "weekly":   "#f7b731",
    "context":  "#4ecdc4",
    AppState.IDLE:          "#555555",
    AppState.THINKING:      "#f7b731",
    AppState.WRITING:       "#4ecdc4",
    AppState.DONE:          "#a8ff78",
    AppState.LIMIT_REACHED: "#ff8300",
}

STATE_LABELS = {
    AppState.IDLE:          "● 쉬는 중",
    AppState.THINKING:      "💡 생각 중",
    AppState.WRITING:       "✏️ 작성 중",
    AppState.DONE:          "⭐ 답변 완료",
    AppState.LIMIT_REACHED: "⚠️ 한도 도달",
}

WIDTH = 210


class MonitorOverlay:
    def __init__(self, on_position_change: Callable[[int, int], None] | None = None,
                 initial_x: int = -1, initial_y: int = -1):
        self._on_position_change = on_position_change
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg=BG)

        self._state = AppState.IDLE
        self._session_pct = 0.0
        self._session_reset_str = "--"
        self._weekly_pct = 0.0
        self._weekly_reset_str = "--"
        self._context_pct = 0.0
        self._context_str = "--"

        self._build_ui()
        self._place_window(initial_x, initial_y)
        self._bind_drag()

    def _build_ui(self) -> None:
        pad = dict(padx=10, pady=2)

        tk.Label(self.root, text="CLAUDE MONITOR", bg=BG, fg=FG_DIM,
                 font=("Segoe UI", 7, "bold"), letterSpacing=2).pack(pady=(8, 2))
        tk.Frame(self.root, bg="#0f3460", height=1, width=WIDTH).pack(fill="x", padx=10)

        status_frame = tk.Frame(self.root, bg=BG)
        status_frame.pack(fill="x", **pad)
        tk.Label(status_frame, text="상태", bg=BG, fg=FG_MID,
                 font=("Segoe UI", 9)).pack(side="left")
        self._status_label = tk.Label(status_frame, text="● 쉬는 중", bg=BG,
                                       fg=COLORS[AppState.IDLE],
                                       font=("Segoe UI", 11, "bold"))
        self._status_label.pack(side="right")

        tk.Frame(self.root, bg="#0f3460", height=1, width=WIDTH).pack(fill="x", padx=10, pady=2)

        self._session_row = self._build_metric_row("세션", "session")
        self._weekly_row = self._build_metric_row("주간", "weekly")
        self._context_row = self._build_metric_row("컨텍스트", "context")

        tk.Frame(self.root, bg=BG, height=6).pack()

    def _build_metric_row(self, label: str, key: str) -> dict:
        color = COLORS[key]
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill="x", padx=10, pady=(3, 0))

        header = tk.Frame(frame, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text=label, bg=BG, fg=FG_MID,
                 font=("Segoe UI", 8)).pack(side="left")

        right = tk.Frame(header, bg=BG)
        right.pack(side="right")
        reset_lbl = tk.Label(right, text="--", bg=BG, fg=color + "99",
                              font=("Segoe UI", 10, "bold"))
        reset_lbl.pack(side="left", padx=(0, 4))
        pct_lbl = tk.Label(right, text="0%", bg=BG, fg=color,
                            font=("Segoe UI", 11, "bold"))
        pct_lbl.pack(side="left")

        canvas = tk.Canvas(frame, bg=BG, height=4, width=WIDTH - 20,
                           highlightthickness=0)
        canvas.pack(fill="x", pady=(2, 1))
        track = canvas.create_rectangle(0, 0, WIDTH - 20, 4, fill=BG_ITEM, width=0)
        bar = canvas.create_rectangle(0, 0, 0, 4, fill=color, width=0)

        return {"pct_lbl": pct_lbl, "reset_lbl": reset_lbl,
                "canvas": canvas, "bar": bar, "color": color}

    def _place_window(self, x: int, y: int) -> None:
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if x < 0 or y < 0:
            x = sw - w - 20
            y = sh - h - 60
        self.root.geometry(f"+{x}+{y}")

    def _bind_drag(self) -> None:
        self.root.bind("<ButtonPress-1>", self._on_drag_start)
        self.root.bind("<B1-Motion>", self._on_drag_motion)
        self.root.bind("<ButtonRelease-1>", self._on_drag_end)
        self._drag_x = 0
        self._drag_y = 0

    def _on_drag_start(self, e: tk.Event) -> None:
        self._drag_x = e.x
        self._drag_y = e.y

    def _on_drag_motion(self, e: tk.Event) -> None:
        x = self.root.winfo_x() + e.x - self._drag_x
        y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _on_drag_end(self, _: tk.Event) -> None:
        if self._on_position_change:
            self._on_position_change(self.root.winfo_x(), self.root.winfo_y())

    def _update_bar(self, row: dict, pct: float) -> None:
        canvas = row["canvas"]
        bar_width = max(1, int((WIDTH - 20) * pct / 100))
        canvas.coords(row["bar"], 0, 0, bar_width, 4)

    def update(self, state: AppState, session_pct: float, session_reset_str: str,
               weekly_pct: float, weekly_reset_str: str,
               context_pct: float, context_str: str) -> None:
        color = COLORS[state]
        self._status_label.config(text=STATE_LABELS[state], fg=color)

        self._session_row["pct_lbl"].config(text=f"{session_pct:.0f}%")
        self._session_row["reset_lbl"].config(text=session_reset_str)
        self._update_bar(self._session_row, session_pct)

        self._weekly_row["pct_lbl"].config(text=f"{weekly_pct:.0f}%")
        self._weekly_row["reset_lbl"].config(text=weekly_reset_str)
        self._update_bar(self._weekly_row, weekly_pct)

        self._context_row["pct_lbl"].config(text=f"{context_pct:.0f}%")
        self._context_row["reset_lbl"].config(text=context_str)
        self._update_bar(self._context_row, context_pct)

    def schedule(self, ms: int, fn: Callable) -> None:
        self.root.after(ms, fn)

    def run(self) -> None:
        self.root.mainloop()
```

- [ ] **Step 2: 수동 검증 — 오버레이 창 외관 확인**

```bash
cd /mnt/d/claude-desktop-monitor
python -c "
from monitor.overlay import MonitorOverlay
from monitor.state_machine import AppState
ov = MonitorOverlay()
ov.update(AppState.THINKING, 42.0, '2h 15m', 67.0, '3일 4h', 55.0, '112k/200k')
ov.run()
"
```
Expected: 설계 목업과 동일한 오버레이 창이 우하단에 표시됨.

- [ ] **Step 3: 커밋**

```bash
git add monitor/overlay.py
git commit -m "feat: add tkinter always-on-top overlay window"
```

---

## Task 8: main.py — 진입점 및 통합

**Files:**
- Create: `main.py`

- [ ] **Step 1: main.py 구현**

```python
from __future__ import annotations
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_PATH = str(BASE_DIR / "config.json")
TRACKER_PATH = str(BASE_DIR / "tracker.json")

def _format_remaining(target: datetime | None) -> str:
    if target is None:
        return "--"
    now = datetime.now(timezone.utc)
    diff = (target - now).total_seconds()
    if diff <= 0:
        return "리셋됨"
    h = int(diff // 3600)
    m = int((diff % 3600) // 60)
    if h >= 24:
        days = h // 24
        return f"{days}일 {h % 24}h"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def main() -> None:
    from monitor.config import load_config, save_config
    from monitor.state_machine import StateMachine, AppState
    from monitor.tracker import UsageTracker, parse_reset_time
    from monitor.accessibility import get_snapshot
    from monitor.overlay import MonitorOverlay

    cfg = load_config(CONFIG_PATH)
    if cfg is None:
        from setup.setup_dialog import run_setup
        cfg = run_setup(CONFIG_PATH)
        if cfg is None:
            sys.exit(0)

    tracker = UsageTracker(TRACKER_PATH, session_hours=cfg.session_hours)
    sm = StateMachine()
    prev_char_count = 0
    prev_state = AppState.IDLE

    overlay = MonitorOverlay(
        on_position_change=lambda x, y: (
            setattr(cfg, "window_x", x),
            setattr(cfg, "window_y", y),
            save_config(cfg, CONFIG_PATH),
        ),
        initial_x=cfg.window_x,
        initial_y=cfg.window_y,
    )

    def poll() -> None:
        nonlocal prev_char_count, prev_state

        snap = get_snapshot(prev_char_count)
        prev_char_count = snap.conversation_char_count
        state = sm.update(snap)

        if state == AppState.THINKING and prev_state == AppState.IDLE:
            tracker.mark_session_start()

        if state == AppState.LIMIT_REACHED and snap.rate_limit_text:
            reset_dt = parse_reset_time(snap.rate_limit_text, cfg.timezone)
            if reset_dt:
                tracker.override_reset_time(reset_dt)

        if state in (AppState.THINKING, AppState.WRITING):
            tracker.add_active_minutes(1 / 120)

        session_reset = tracker.session_reset_time
        weekly_minutes = tracker.weekly_active_minutes
        weekly_pct = min(weekly_minutes / 60 * 2, 100.0)

        weekly_reset = _next_monday_midnight()

        overlay.update(
            state=state,
            session_pct=tracker.session_pct,
            session_reset_str=_format_remaining(session_reset),
            weekly_pct=weekly_pct,
            weekly_reset_str=_format_remaining(weekly_reset),
            context_pct=tracker.context_pct(snap.conversation_char_count),
            context_str=f"{snap.conversation_char_count // 3500:.0f}k / 200k",
        )

        prev_state = state
        overlay.schedule(500, poll)

    def _next_monday_midnight() -> datetime:
        now = datetime.now(timezone.utc)
        days_until_monday = (7 - now.weekday()) % 7 or 7
        return (now + timedelta(days=days_until_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    overlay.schedule(500, poll)
    overlay.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 전체 통합 실행 확인**

Claude Desktop App을 실행한 상태에서:
```bash
cd /mnt/d/claude-desktop-monitor
python main.py
```
Expected:
1. `config.json` 없으면 설정 다이얼로그 → 플랜 선택 → 오버레이 창 표시
2. `config.json` 있으면 바로 오버레이 창 표시
3. Claude Desktop App에서 메시지 전송 시 상태 변화 확인

- [ ] **Step 3: 전체 테스트 수트 실행**

```bash
python -m pytest tests/ -v
```
Expected: 전체 통과 (accessibility.py는 mock 없이 건너뜀)

- [ ] **Step 4: 최종 커밋**

```bash
git add main.py
git commit -m "feat: add main entry point and full integration"
git push origin main
```

---

## 자기 검토 (Spec Coverage)

| 요구사항 | 구현 태스크 |
|----------|------------|
| 세션 사용량 % | Task 4 (tracker.session_pct) |
| 세션 리셋까지 남은 시간 | Task 4 (session_reset_time), Task 8 (_format_remaining) |
| 주간 사용량 % | Task 4 (weekly_active_minutes) |
| 주간 리셋까지 남은 시간 | Task 8 (_next_monday_midnight) |
| 컨텍스트 사용량 % | Task 4 (context_pct), Task 5 (char_count) |
| 5가지 상태 표시 | Task 3 (StateMachine), Task 7 (overlay) |
| Rate limit 자동 감지 | Task 4 (parse_reset_time), Task 5 (accessibility) |
| 구독 플랜 자동 설정 | Task 2 (PLAN_LIMITS), Task 6 (setup_dialog) |
| Always-on-top 드래그 이동 | Task 7 (overlay) |
| 위치 저장 | Task 8 (on_position_change) |
| GitHub 배포 | Task 8 마지막 커밋 |
