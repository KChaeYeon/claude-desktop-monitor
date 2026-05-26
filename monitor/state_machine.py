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
