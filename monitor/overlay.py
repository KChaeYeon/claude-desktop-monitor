from __future__ import annotations
import tkinter as tk
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
                 font=("Segoe UI", 7, "bold")).pack(pady=(8, 2))
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
        reset_lbl = tk.Label(right, text="--", bg=BG, fg=color,
                              font=("Segoe UI", 10, "bold"))
        reset_lbl.pack(side="left", padx=(0, 4))
        pct_lbl = tk.Label(right, text="0%", bg=BG, fg=color,
                            font=("Segoe UI", 11, "bold"))
        pct_lbl.pack(side="left")

        canvas = tk.Canvas(frame, bg=BG, height=4, width=WIDTH - 20,
                           highlightthickness=0)
        canvas.pack(fill="x", pady=(2, 1))
        canvas.create_rectangle(0, 0, WIDTH - 20, 4, fill=BG_ITEM, width=0)
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
