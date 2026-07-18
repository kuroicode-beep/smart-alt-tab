# 완료보고서 — M1 전환기 구현

| 항목 | 내용 |
|------|------|
| 프로젝트 | smart-alt-tab |
| 마일스톤 | M1 — Alt+Tab 가로채기 + 자체 텍스트 전환기 + 선택 이동·전환 |
| 버전 | v0.1.0 → **v0.2.1** (M1 + 안정화) |
| 작성일 | 2026-07-19 |
| 작업자 | Claude Code |
| 상태 | 구현·검증 완료 |

## 1. 한 일

M0(기술 검증)만 있던 상태에서 실제 동작하는 전환기를 구현했다.

- **Alt+Tab 가로채기·소비**: `WH_KEYBOARD_LL` 저수준 훅(stdcall 콜백)으로 Alt+Tab을 감지하고
  `return 1`로 기본 Windows 전환기를 차단한다.
- **자체 전환기 UI**: 고대비 다크 오버레이(교보손글씨2019 본문 22–26px, Consolas 숫자).
  선택 행은 **테두리 + `▶` 마커 + 밝은색**으로 표시(색상만으로 구분하지 않음).
  창이 많으면 선택 주변 9개만 보이고 `▲ 위로 N개` / `▼ 아래로 N개` 텍스트 인디케이터를 표시.
- **선택 이동**: Alt 홀드 중 Tab(다음)/Shift+Tab(이전)/방향키로 이동, 순환(wrap).
- **전환·취소**: Alt를 놓으면 선택 창으로 전환(`SetForegroundWindow`, 실패 시 `AttachThreadInput`
  우회), ESC로 취소, Enter로 즉시 확정.
- **창 목록 필터**: `EnumWindows` + `IsWindowVisible` + `GetLastActivePopup(GetAncestor
  (ROOTOWNER))==hwnd` + not `WS_EX_TOOLWINDOW`(APPWINDOW 예외) + not DWM cloaked + 제목 있음.
- **안전장치**: 훅 콜백은 예외를 삼켜 절대 죽지 않고 `CallNextHookEx`로 폴백. 훅 설치 실패 시
  기본 Alt+Tab을 막지 않고 종료. DPI per-monitor v2 선언.

## 2. 구조

```
src/smart_alt_tab/
  __main__.py / app.py     조립·mainloop (훅은 tkinter mainloop 스레드에 설치)
  controller.py            세션 상태머신 (훅 이벤트 → 선택/전환, 렌더는 after_idle로 위임)
  switcher.py              고대비 다크 오버레이 UI (행 위젯 재사용)
  version.py               APP_VERSION / VERSION_HISTORY
  win/
    dpi.py                 per-monitor v2 DPI 선언
    windows.py             창 열거·필터·전환 (ctypes)
    hook.py                WH_KEYBOARD_LL 훅 (stdcall WINFUNCTYPE)
tests/test_controller.py   상태머신 단위 테스트 (9건)
run.py, pyproject.toml
```

훅 콜백은 시스템 전역이라 **상태만 갱신하고 소비 여부를 즉시 반환**하며, 화면 갱신은
`after_idle`로 미룬다. 창 전환은 포그라운드 권한이 살아있는 콜백 시점에 동기로 수행한다.

## 3. 검증 (실측)

| 항목 | 방법 | 결과 |
|------|------|------|
| 훅 설치(stdcall) | `SetWindowsHookExW` 설치/해제 | 정상(handle 획득) |
| 창 필터 | 실제 데스크톱 `list_windows()` | 유효 창만(Claude·Chrome), 유령 창 없음 |
| 상태머신 | 이벤트 시퀀스 단위 테스트 9건 | 9/9 통과 |
| 창 전환 API | 포그라운드 자기 전환 | True |
| **전체 E2E** | 실제 훅에 키 이벤트 주입(Alt→Tab→Tab→Alt↑) | 오버레이 실표시·선택 이동·소비·전환 호출 확인 |
| UI 디자인 | 렌더 스크린샷 | 고대비 다크·큰 글씨·선택 강조·한글 제목 정상 |

E2E는 실제 설치된 `WH_KEYBOARD_LL` 훅이 주입 키 이벤트를 받아 전체 파이프라인(감지→소비→
선택 이동→오버레이 렌더→Alt 놓음 시 전환 호출)을 도는 것을 확인했다. 기본 Windows Alt+Tab이
뜨지 않음(=소비)도 함께 확인.

## 3.1 안정화 수정 (v0.2.1) — "작동 안 함" 실사용 대응

초기 M1(v0.2.0)을 실앱으로 띄워 Alt+Tab을 넣자 **간헐적으로 프로세스가 죽었다**
(`Fatal Python error: PyEval_RestoreThread ... thread state is NULL`).

- **원인**: 훅 콜백에서 `root.after_idle`(=Tcl 호출)로 렌더를 예약했다. 저수준 훅은 Tcl
  메시지 펌프 도중 재진입 호출되므로, 콜백에서 Tcl을 건드리면 Python 스레드 상태가 깨진다.
- **수정**: 훅 콜백을 **순수 파이썬 상태 갱신 + 세대 카운터**로만 축소하고, UI 렌더와 창 전환은
  `root.after`로 재무장하는 **폴러(~15ms)**가 mainloop 문맥에서 처리하도록 분리했다. 콜백과
  폴러는 같은 스레드에서 번갈아 실행돼 락이 없다.
- **부수 수정**: 오버레이가 화면 오른쪽으로 잘려 나가던 문제 → 고정 너비(화면 82%, 최대 1280)로
  중앙 배치·화면 안 클램프, 긴 제목은 폰트 픽셀 폭 기준으로 잘라냄(…).
- **검증**: 폴러 구조 실앱에 Alt+Tab 사이클 **60회(20×3런) 주입 — 무크래시**, 오버레이 정중앙
  표시(`1280x739+640+233`), 전환 20/20 호출. 교훈은 `CLAUDE.md` 핵심 기술에 기록.

## 4. 남은 확인 / 다음(M2)

- **실사용 키 감(感)**: 표시 크기·타이밍·다중 모니터 위치는 실제 사용에서 최종 조정 권장
  (현재 오버레이는 주 모니터 중앙 상단 1/3 지점).
- **M2 예정**: 창 목록 필터 정교화(엣지 케이스), 폴백·ESC 안전장치 강화, 다중 모니터 배치,
  Alt 놓을 때 메뉴바 활성화 여부 실사용 점검(현재 Alt keyup은 통과시켜 끼임 방지).
- **M3 예정**: SVIL 디자인 토큰 정식 적용, 설정(글꼴·크기·언어) + 업데이트 내역 메뉴.

## 5. 실행

```
py -3.13 run.py
```
Alt+Tab → 자체 전환기. 종료는 콘솔 Ctrl+C.
