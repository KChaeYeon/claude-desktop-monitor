from __future__ import annotations
import re
from PIL import ImageGrab, ImageChops
from monitor.state_machine import UISnapshot

try:
    import uiautomation as auto
    _UIA_AVAILABLE = True
except ImportError:
    _UIA_AVAILABLE = False

try:
    import pytesseract
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

_prev_img = None


def _find_claude_window():
    if not _UIA_AVAILABLE:
        return None
    root = auto.GetRootControl()
    for ctrl in root.GetChildren():
        name = ctrl.Name or ""
        if name == "Claude" or name.startswith("Claude "):
            return ctrl
    return None


def _capture_window(window):
    try:
        r = window.BoundingRectangle
        return ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True)
    except Exception:
        return None


def _images_differ(img1, img2) -> bool:
    """대화 영역(상단 10% 제외)의 픽셀 변화를 비교한다."""
    try:
        w, h = img1.size
        crop = (0, int(h * 0.1), w, h)
        a = img1.crop(crop).convert("L")
        b = img2.crop(crop).convert("L")
        diff = ImageChops.difference(a, b)
        pixels = list(diff.getdata())
        return sum(pixels) / len(pixels) > 0.5
    except Exception:
        return False


def _ocr_rate_limit(img) -> str | None:
    if not _OCR_AVAILABLE:
        return None
    try:
        text = pytesseract.image_to_string(img, lang="kor+eng")
        match = re.search(r'resets?\s+\d{1,2}:\d{2}\s*(?:am|pm)', text, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 50)
            return text[start:match.end() + 50]
        return None
    except Exception:
        return None


def get_snapshot(prev_char_count: int = 0) -> UISnapshot:
    global _prev_img

    window = _find_claude_window()
    if window is None:
        _prev_img = None
        return UISnapshot(
            app_running=False,
            is_loading=False,
            is_streaming=False,
            rate_limit_text=None,
            conversation_char_count=0,
        )

    img = _capture_window(window)
    if img is None:
        return UISnapshot(
            app_running=True,
            is_loading=False,
            is_streaming=False,
            rate_limit_text=None,
            conversation_char_count=0,
        )

    is_streaming = _prev_img is not None and _images_differ(_prev_img, img)
    _prev_img = img

    rate_limit_text = _ocr_rate_limit(img)

    # 화면 변화량을 char_count 대용으로 사용 (context % 추정)
    char_count = prev_char_count + 50 if is_streaming else prev_char_count

    return UISnapshot(
        app_running=True,
        is_loading=False,
        is_streaming=is_streaming,
        rate_limit_text=rate_limit_text,
        conversation_char_count=char_count,
    )


def debug_dump_tree(max_depth: int = 5) -> None:
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
