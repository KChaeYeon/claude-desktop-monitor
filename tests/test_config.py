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
