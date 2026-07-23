# smart-alt-tab

Windows Alt+Tab을 대체하는 저시력 친화 창 전환기. 큰 글씨·고대비로 열린 창을 보여주고,
Alt 홀드 중 Tab/방향키로 고른 뒤 Alt를 놓으면 그 창으로 전환한다.

- 현재 버전: **v0.4.2** (M3 + 관리자 권한 앱 전환 지원)
- 로컬: `C:\Projects\smart-alt-tab`
- 상태: M1·M2·M3 완료(훅 소비·선택 이동·전환·오버레이, 필터 정교화·다중 모니터·안전장치,
  설정 화면·트레이·DPI 정밀화). 다음은 백로그(썸네일 미리보기, M4).

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
- **창 목록**: `EnumWindows` + 표준 필터 — `IsWindowVisible` + 소유 팝업 체인 워크(`GetAncestor
  (GA_ROOTOWNER)` → `GetLastActivePopup` 반복)로 대표 창만 + not `WS_EX_TOOLWINDOW` + not DWM
  cloaked(`DWMWA_CLOAKED`).
- **DPI**: per-monitor v2를 첫 Tk 창 전에 선언(`win/dpi.py`). Tk 자체 폰트 스케일은 프로세스
  시작 시 한 번 고정돼 모니터 이동에 실시간으로 안 따라오므로, 오버레이·설정창은 매 표시마다
  대상 모니터 DPI를 직접 조회해 논리 px(96dpi 기준)를 물리 px로 환산하고 Tk 음수 폰트 크기
  (=픽셀 단위)로 그린다.
- **관리자 권한 앱과의 전환 — 앱 자신이 관리자로 떠야 한다(실측, 2026-07-23, 중요)**:
  Cursor를 **관리자 권한으로 실행**하면(창 제목에 `[관리자]` 표시, 프로세스 High integrity
  `0x3000`) 일반 권한(Medium `0x2000`)인 전환기로는 두 가지가 **모두** 막힌다 —
  ① 그 앱이 활성일 때 **LL 키보드 훅이 키를 아예 받지 못해** 전환기가 뜨지 않고,
  ② `AttachThreadInput`이 `ERROR_ACCESS_DENIED`(5)로 실패해 포커스도 못 넘긴다.
  이 PC는 `ForegroundLockTimeout`이 최대값(2147483647ms)이라 포그라운드 잠금도 극도로 엄격.
  **코드로 우회 불가 — OS(UIPI) 제약이다.** 해결: 전환기 자신을 관리자 권한으로 실행
  (`scripts/install_admin_autostart.ps1` — 작업 스케줄러 "가장 높은 권한", 로그인 시 자동
  실행, 매번 UAC 창 안 뜸). 시작프로그램 바로가기 방식은 관리자 실행 시 로그인마다 UAC가
  떠서 부적합.
  주의: `_inject_dummy_key`(`VK_F15`)는 포그라운드 락 완화에 도움은 되지만 무결성 수준
  차이는 못 넘는다 — v0.4.1에서 이걸로 해결됐다고 본 건 Cursor가 포그라운드가 아닌 조건에서
  통과한 것을 오판한 것. 권한 문제의 진짜 해결책은 관리자 실행뿐.
- **트레이 아이콘 WNDPROC은 LL 훅과 달리 tkinter 호출 안전**(실측) — `Shell_NotifyIconW`
  메시지는 Tk의 mainloop가 이미 돌리는 표준 `DispatchMessage` 경로로 들어오므로(Tcl 이벤트
  펌프의 일부), LL 키보드 훅처럼 그 바깥에서 비동기 재진입하는 게 아니다. `win/tray.py`의
  WNDPROC에서 설정창을 직접 열어도(`deiconify()`) 안전 — 위 "훅 콜백 Tcl 금지"와는 다른 경로.

## 스택

Python 3.13 · ctypes(Win32) · tkinter(고대비 다크) · PyInstaller onefile.
audio-hotkeys에서 검증된 스택을 계승.

## 규칙

**버전**: SemVer, `VERSION` 파일 + 코드 `APP_VERSION`/`VERSION_HISTORY`. 상세는 `VERSIONING.md`.
설정 창 하단에 "업데이트 내역" 섹션으로 버전별 요약 표시(구현됨, `settings_window.py`).

**접근성 (SVIL 공통, 예외 없음)**: 고대비 다크, 큰 글씨, 색상만으로 상태 구분 금지(테두리+색+
체크마커), 본문 글꼴은 저시력 가독성 위해 헤비 웨이트(나눔고딕 ExtraBold 기본, 실제 설치된
것만 선택지 노출), Consolas 숫자, DPI 인식. 정본은 `/svil-frontend-design` 스킬.

**설정(§2.1, 구현됨)**: 글꼴·글자 크기·다국어 3항목 필수 — `config.py`(영속화)·`i18n.py`
(5개 언어: 한국어·English·日本語·中文·Tiếng Việt)·`settings_window.py`(UI, 선택 즉시 저장·
적용, 별도 저장 버튼 없음). 글꼴은 SVIL 8종 후보 중 시스템에 실재하는 것만 노출(현재 3종:
나눔고딕·교보손글씨2019·고딕) — 새 글꼴을 설치하면 자동으로 목록에 나타난다.

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
