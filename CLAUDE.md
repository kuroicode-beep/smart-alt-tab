# smart-alt-tab

Windows Alt+Tab을 대체하는 저시력 친화 창 전환기. 큰 글씨·고대비로 열린 창을 보여주고,
Alt 홀드 중 Tab/방향키로 고른 뒤 Alt를 놓으면 그 창으로 전환한다.

- 현재 버전: **v0.3.0** (M2)
- 로컬: `C:\Projects\smart-alt-tab`
- 상태: M1·M2 완료(훅 소비·선택 이동·전환·오버레이, 필터 정교화·다중 모니터·안전장치), M3 예정

## 왜 별도 프로젝트인가

Windows Alt+Tab은 전환기 내부 하이라이트 이동을 표준 API로 노출하지 않는다(실측 확인).
그래서 "고르는 중 실시간 표시"는 Alt+Tab을 통째로 대체해야만 가능하다. 이 부담(시스템 전역
키보드 훅)을 오디오 앱(audio-hotkeys)에 얹는 것은 부적절하여 분리했다. 배경·검증 결과는
`docs/prd/`.

## 핵심 기술 (검증됨, 2026-07-19)

- **Alt+Tab 감지·소비**: `SetWindowsHookExW(WH_KEYBOARD_LL)`. 콜백은 **stdcall(`WINFUNCTYPE`)**
  이어야 설치된다(cdecl이면 실패). 훅에서 `return 1`로 기본 Alt+Tab을 막을 수 있다.
- **저수준 키보드 훅은 시스템 전역** — 콜백은 최소 작업만. 무거운 처리는 별도 스레드/`after`로.
  훅 실패·예외 시 기본 Alt+Tab으로 폴백, ESC로 취소하는 안전장치 필수.
- **훅 콜백에서 tkinter/Tcl 호출 금지(치명적, 실측)** — LL 훅은 Tcl 메시지 펌프 도중 재진입
  호출되므로 콜백에서 `after`/위젯 등 Tcl을 건드리면 Python 스레드 상태가 깨져 간헐적으로
  프로세스가 죽는다(GIL: thread state is NULL). 콜백은 순수 파이썬 상태만 갱신하고, UI 렌더·
  창 전환은 mainloop 문맥에서 도는 폴러(`root.after` 재무장)가 그 상태를 읽어 처리한다.
  콜백과 폴러는 같은 스레드에서 번갈아 실행돼 락이 필요 없다. (`controller.py` 참고)
- **창 목록**: `EnumWindows` + 표준 필터 — `IsWindowVisible` + `GetLastActivePopup(GetAncestor
  (hwnd, GA_ROOTOWNER)) == hwnd` + not `WS_EX_TOOLWINDOW` + not DWM cloaked(`DWMWA_CLOAKED`).
- **DPI**: per-monitor v2를 첫 Tk 창 전에 선언, 크기는 논리 px → 물리 px 환산.

## 스택

Python 3.13 · ctypes(Win32) · tkinter(고대비 다크) · PyInstaller onefile.
audio-hotkeys에서 검증된 스택을 계승.

## 규칙

**버전**: SemVer, `VERSION` 파일 + 코드 `APP_VERSION`/`VERSION_HISTORY`. 상세는 `VERSIONING.md`.
UI가 생기면 설정에 "업데이트 내역" 메뉴로 버전별 요약 표시.

**접근성 (SVIL 공통, 예외 없음)**: 고대비 다크, 큰 글씨, 색상만으로 상태 구분 금지(테두리+색),
교보손글씨2019 본문·Consolas 숫자, DPI 인식, `prefers_reduced_motion` 존중. 정본은
`/svil-frontend-design` 스킬.

**문서 이중 저장**: 완료보고서·요청문서는 두 곳에 동시 저장 —
1. 로컬 `C:\Projects\smart-alt-tab\docs\reports\` (성격에 맞는 하위 폴더)
2. Vault `G:\내 드라이브\SVIL Vault\03_PRJ\smart-alt-tab\`
파일명: `카테고리_YYYYMMDD_내용_작업자.md`, 공백 금지, UTF-8.

## docs 구조

```
docs/prd/          PRD·스펙
docs/architecture/ 아키텍처
docs/storyboard/   스토리보드
docs/handoff/      작업지시서
docs/reports/      완료보고서
```

## 작업 방식

- 코드 수정 전 수정할 파일 목록 먼저 보고.
- 검증은 실제 실행 기준. 키 훅·창 전환은 단위 테스트만으로 부족하니 실제로 눌러보고 확인.
  테스트로 바꾼 창/포커스는 원복.
- 표시 크기·타이밍은 계산하지 말고 재본다.
