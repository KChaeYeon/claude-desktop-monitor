# Claude Desktop Monitor — 설계 문서

**작성일:** 2026-05-27  
**상태:** 승인됨

---

## 개요

Claude Desktop App(claude.ai GUI, Windows)의 세션 사용량, 주간 사용량, 컨텍스트 사용량, 현재 상태를 실시간으로 표시하는 always-on-top 오버레이 프로그램.

Claude Code CLI가 아닌 **Claude Desktop App 전용** 모니터링 도구이며, Windows에서 독립 실행되는 Python 앱이다.

---

## 목표

- Claude Desktop App 사용 중 별도 창 확인 없이 사용량을 항상 인지
- 세션 한도 도달 전 시각적 경고 제공
- 구독 플랜에 따라 자동 설정, 누구든 설치 즉시 사용 가능

---

## 아키텍처

### 전체 구조

```
claude-desktop-monitor/
├── main.py                  # 진입점 — 최초 실행 감지 후 setup 또는 overlay 시작
├── config.json              # 플랜, 타임존 등 사용자 설정 (자동 생성)
├── tracker.json             # 세션 시작 시각, 주간 누적 데이터 (자동 생성)
├── requirements.txt
├── monitor/
│   ├── overlay.py           # tkinter always-on-top 창 + 렌더링
│   ├── accessibility.py     # Windows UIAutomation 폴링 (0.5초)
│   ├── state_machine.py     # UI 감지 결과 → 5가지 상태 전환
│   ├── tracker.py           # 5h 윈도우 계산, 주간 누적, 리셋 시간 파싱
│   └── config.py            # config.json 로드/저장, PLAN_LIMITS 정의
└── setup/
    └── setup_dialog.py      # 최초 실행 플랜 선택 다이얼로그 (tkinter)
```

### 데이터 흐름

```
[Claude Desktop App (Windows)]
        ↓ Windows UIAutomation (0.5초 폴링)
[accessibility.py]  →  [state_machine.py]  →  [overlay.py]
        ↓
[tracker.py]  ←→  tracker.json
        ↓
[config.py]  ←→  config.json
```

---

## 컴포넌트 상세

### 1. accessibility.py — UI 상태 폴링

Windows `uiautomation` 라이브러리로 Claude Desktop App 창을 0.5초마다 폴링한다.

감지 대상:
- **로딩 스피너 존재 여부** → 생각 중
- **텍스트 스트리밍 진행 여부** (이전 폴링과 텍스트 길이 비교) → 작성 중
- **rate limit 메시지 포함 여부** (`"resets X:XXpm"` 패턴) → 한도 도달
- **Claude 앱 창 존재 여부** → 앱 실행 여부

반환 인터페이스:
```python
@dataclass
class UISnapshot:
    app_running: bool
    is_loading: bool
    is_streaming: bool
    rate_limit_text: str | None   # "resets 3:40pm (Asia/Seoul)" 또는 None
    conversation_char_count: int
```

### 2. state_machine.py — 상태 전환

`UISnapshot`을 받아 5가지 상태 중 하나를 반환한다.

| 상태 | 조건 |
|------|------|
| `IDLE` (● 쉬는 중) | 앱 실행 중, 변화 없음, Stop 이후 30초 경과 |
| `THINKING` (💡 생각 중) | `is_loading == True` |
| `WRITING` (✏️ 작성 중) | `is_streaming == True` |
| `DONE` (⭐ 답변 완료) | 이전 상태가 WRITING/THINKING이고 변화 멈춤 |
| `LIMIT_REACHED` (⚠️ 한도 도달) | `rate_limit_text is not None` |

상태 전환 시 `DONE`은 30초 후 자동으로 `IDLE`로 전환된다.

### 3. tracker.py — 사용량 계산

**세션 5h 윈도우:**
- 최초 활동 감지(THINKING 진입) 시 `session_start`를 `tracker.json`에 기록
- `session_pct = (now - session_start).seconds / 18000 * 100`
- `session_reset = session_start + 5h`
- rate limit 메시지 감지 시 파싱한 시각으로 `session_reset` 덮어쓰기

**주간 사용량:**
- 매일 00:00 자정 기준으로 일별 활성 시간(분) 누적
- 주간 리셋: 매주 월요일 00:00

**컨텍스트 창:**
- `conversation_char_count ÷ 3.5` 로 토큰 추정
- `context_pct = estimated_tokens / 200000 * 100`

### 4. overlay.py — UI 렌더링

tkinter 기반 always-on-top 창. 기본 위치: 우하단, 드래그 이동 가능.

**색상 체계:**
| 항목 | 색상 |
|------|------|
| 세션 바/% | `#e94560` (빨강) |
| 주간 바/% | `#f7b731` (노랑) |
| 컨텍스트 바/% | `#4ecdc4` (청록) |
| 상태 — 쉬는 중 | `#555555` (회색) |
| 상태 — 생각 중 | `#f7b731` (노랑) |
| 상태 — 작성 중 | `#4ecdc4` (청록) |
| 상태 — 답변 완료 | `#a8ff78` (연두) |
| 상태 — 한도 도달 | `#ff8300` (주황) |

1초마다 UI 갱신. 드래그로 위치 이동, 위치는 `config.json`에 저장.

### 5. config.py — 설정 관리

```python
PLAN_LIMITS = {
    "free":    {"session_hours": 1},
    "pro":     {"session_hours": 5},
    "max_5x":  {"session_hours": 5},
    "max_20x": {"session_hours": 5},
}
```

`config.json` 없으면 최초 실행으로 판단 → `setup_dialog.py` 호출.

### 6. setup_dialog.py — 최초 실행 설정

tkinter 다이얼로그:
1. 구독 플랜 선택 (Free / Pro / Max 5x / Max 20x)
2. 타임존 자동 감지 (변경 가능)
3. 확인 → `config.json` 생성 → 오버레이 시작

---

## UI 레이아웃

```
┌─────────────────────┐
│  CLAUDE MONITOR     │
├─────────────────────┤
│ 상태   💡 생각 중    │
├─────────────────────┤
│ 세션       2h 15m  42%│
│ ████░░░░░░░░░░░░░░  │
├─────────────────────┤
│ 주간       3일 4h  67%│
│ ██████████░░░░░░░░  │
├─────────────────────┤
│ 컨텍스트  112k/200k 55%│
│ █████████░░░░░░░░░  │
└─────────────────────┘
```

크기: 약 200×180px. 배경: `#16213e`. 테두리: 상태 색상으로 글로우 효과.

---

## 의존성

```
uiautomation>=2.0.18   # Windows UIAutomation API
```

Python 3.8+ 필요. `tkinter`는 표준 라이브러리 포함.

---

## 배포 고려사항

- `main.py` 단독 실행으로 동작 (`python main.py`)
- Windows 시작 프로그램 등록 옵션 제공 (setup 시)
- `config.json`이 없으면 항상 setup 다이얼로그 표시 → 누구든 설치 후 바로 사용
- `tracker.json`은 앱이 자동 생성/관리
