# smart-alt-tab PRD

| 항목 | 내용 |
|------|------|
| 제품명 | smart-alt-tab |
| 한 줄 요약 | Windows Alt+Tab을 대체하는, 저시력 친화 고대비·큰 글씨 창 전환기 |
| 플랫폼 | Windows 10 / 11 |
| 문서 버전 | 0.1 |
| 작성일 | 2026-07-19 |
| 상태 | 기술 검증 완료 · 초기 스펙 |

## 1. 배경

Windows 기본 Alt+Tab 전환기는 창 제목 글씨가 작아 저시력 사용자가 "지금 어느 창인지" 알아보기 어렵다. audio-hotkeys에 창 전환 표시 기능을 붙여봤으나, Windows의 Alt+Tab은 전환기 내부의 하이라이트 이동을 표준 API로 노출하지 않아(측정 완료), "고르는 중 실시간 표시"가 원리적으로 불가능했다. 유일한 해법은 Alt+Tab을 통째로 대체하는 전용 전환기다. 이 부담을 오디오 앱에 얹는 것은 부적절하여 별도 프로젝트로 분리한다.

## 2. 목표

1. Alt+Tab을 가로채 자체 전환기를 띄운다.
2. 열린 창 목록을 **큰 글씨·고대비**로 보여준다 (SVIL 저시력 접근성 기준).
3. Alt 홀드 중 Tab / Shift+Tab / 방향키로 선택을 이동하고, Alt를 놓으면 선택 창으로 전환한다.
4. 전환 중 현재 선택 창을 **실시간으로** 크게 표시한다 — 이것이 audio-hotkeys 방식으로 불가능했던 핵심.

### 2.1 비목표 (초기)

- Windows 기본 Alt+Tab의 모든 동작(가상 데스크톱 전환 등) 완전 재현
- macOS / Linux
- 창 썸네일 미리보기 (1차는 텍스트 목록 우선; 썸네일은 후속)

## 3. 기술 검증 결과 (2026-07-19, 완료)

audio-hotkeys 세션에서 프로토타입으로 실측:

| 항목 | 결과 |
|------|------|
| `WH_KEYBOARD_LL` 저수준 훅으로 Alt+Tab **감지** | 가능 (콜백은 stdcall=`WINFUNCTYPE` 필수, cdecl이면 훅 설치 실패) |
| 훅에서 `return 1`로 Alt+Tab **소비**(Windows 기본 전환기 차단) | 가능 |
| `EnumWindows`로 창 목록 + 제목 수집 | 가능하나 **필터 정교화 필요** (아래 리스크) |
| Alt+Tab 전환기 내부 하이라이트를 표준 이벤트로 추적 | **불가** — XAML 기반이라 제목이 빈 값. 자체 전환기가 필요한 이유 |

## 4. 핵심 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| 저수준 키보드 훅은 시스템 전역 | 훅 콜백이 느리거나 죽으면 전체 키 입력 지연 | 콜백은 최소 작업만(플래그 세팅), 무거운 처리는 별도 스레드/after로 |
| Alt+Tab 완전 대체 | 전환기 버그 시 창 전환 불가 | 안전장치: 훅 실패/예외 시 기본 Alt+Tab으로 폴백, ESC로 취소 |
| 창 목록 필터 부정확 | 유령 창 표시 / 실제 창 누락 | 표준 규칙 적용: `IsWindowVisible` + `GetLastActivePopup(GetAncestor(ROOTOWNER))==hwnd` + not `WS_EX_TOOLWINDOW` + not DWM cloaked(`DWMWA_CLOAKED`) |
| Windows 업데이트로 동작 변화 | 전환기·필터 회귀 | 실측 기반 유지, 회귀 시 재검증 |

## 5. 기술 개요 (안)

| 영역 | 구현 |
|------|------|
| 언어 | Python 3.13 |
| 키 훅 | `SetWindowsHookExW(WH_KEYBOARD_LL)` (ctypes, `use_last_error=True`) |
| 창 열거 | `EnumWindows` + DWM cloaked 필터 (ctypes) |
| 창 전환 | `SetForegroundWindow` (+ AttachThreadInput 우회 필요 시) |
| UI | tkinter 고대비 다크 오버레이 (SVIL 디자인 토큰) |
| 배포 | PyInstaller onefile |

audio-hotkeys에서 검증된 스택을 계승한다.

## 6. 접근성 기준 (SVIL 공통, 필수)

- 고대비 다크, 큰 글씨(본문 18px+, 전환기 목록은 더 크게), 색상만으로 상태 구분 금지(선택은 테두리+색 병행)
- 교보손글씨2019 기본, 숫자·단축키는 Consolas
- DPI 인식(per-monitor v2), `prefers_reduced_motion` 존중
- 전체 문서: `/svil-frontend-design` 스킬

## 7. 마일스톤 (초안)

| 단계 | 내용 | 상태 |
|------|------|------|
| M0 | 기술 검증 (훅 감지·소비, 창 열거) | 완료 |
| M1 | Alt+Tab 가로채기 + 자체 텍스트 전환기(큰 글씨) + 선택 이동 + 전환 | 예정 |
| M2 | 창 목록 필터 정교화(cloaked/owner), 폴백·ESC 안전장치 | 예정 |
| M3 | SVIL 디자인 적용, DPI, 설정(글꼴·크기·언어) | 예정 |
| M4 | 썸네일 미리보기(선택) | 백로그 |
