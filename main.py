from __future__ import annotations
import sys
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


def _next_monday_midnight() -> datetime:
    now = datetime.now(timezone.utc)
    days_until_monday = (7 - now.weekday()) % 7 or 7
    return (now + timedelta(days=days_until_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


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

    # Claude가 이미 실행 중이면 세션 타이머 즉시 시작 (기존 유효한 세션은 유지)
    if not tracker.session_is_valid():
        initial_snap = get_snapshot(0)
        if initial_snap.app_running:
            tracker.mark_session_start()

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

        if state in (AppState.THINKING, AppState.WRITING) and prev_state == AppState.IDLE:
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

    overlay.schedule(500, poll)
    overlay.run()


if __name__ == "__main__":
    main()
