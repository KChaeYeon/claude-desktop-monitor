import json
import os
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from monitor.tracker import UsageTracker, parse_reset_time

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
