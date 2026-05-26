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
