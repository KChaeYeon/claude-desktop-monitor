from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional
from monitor.config import AppConfig, save_config, PLAN_LIMITS


def _detect_timezone() -> str:
    try:
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
