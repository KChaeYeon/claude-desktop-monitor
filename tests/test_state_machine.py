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
