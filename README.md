# smart-alt-tab

Windows Alt+Tab을 대체하는 **저시력 친화 창 전환기**. 열린 창을 큰 글씨·고대비로 보여주고,
Alt를 누른 채 Tab/방향키로 고른 뒤 Alt를 놓으면 그 창으로 전환합니다.

> Windows 기본 Alt+Tab은 창 제목이 작아 저시력 사용자가 알아보기 어렵고, 전환기 내부의
> 하이라이트 이동을 표준 API로 알려주지 않습니다. 그래서 "고르는 중 실시간으로 크게 보기"는
> Alt+Tab을 통째로 대체해야만 가능합니다. 이 프로젝트가 그 대체 전환기입니다.

## 상태

M1·M2·M3 구현·검증 완료, 단일 exe 배포까지 완료 (v0.5.0). 배경과 스펙은 [docs/prd](docs/prd/)를 참고하세요.

- Alt+Tab 가로채기·소비, 고대비 다크 텍스트 전환기, Tab/Shift+Tab/방향키 선택 이동,
  Alt 놓으면 전환, ESC 취소
- 창 목록 필터 정교화(소유 팝업 체인), 다중 모니터 배치(커서 모니터 작업영역 중앙),
  안전장치(열린 창 없으면 기본 Alt+Tab 폴백, Alt keyup 유실 시 자동 확정)
- 트레이 아이콘(설정·종료), 설정 화면(글꼴 3종·글자 크기 3단계·다국어 5종, 즉시 저장·적용),
  설정 안 업데이트 내역
- DPI: 대상 모니터별 논리→물리 px 실시간 환산

## 실행

### 1. exe로 실행 (Python 설치 불필요, 권장)

[릴리스 페이지](https://github.com/kuroicode-beep/smart-alt-tab/releases/latest)에서
`smart-alt-tab.exe`를 받아 두 번 누르면 됩니다. 설치 과정도, 검은 콘솔 창도 없습니다.

### 2. 소스로 실행 (개발용)

```
py -3.13 run.py
```

Alt+Tab을 누르면 자체 전환기가 뜹니다. 트레이 아이콘을 우클릭하면 설정·종료.

### 자동 실행

로그인할 때마다 자동으로 켜지게 하려면 **PowerShell을 관리자 권한으로 실행**한 뒤:

```
powershell -ExecutionPolicy Bypass -File scripts\install_admin_autostart.ps1
```

작업 스케줄러에 등록되어 로그인 시 UAC 창 없이 자동 실행됩니다. `dist\smart-alt-tab.exe`가
있으면 그것을, 없으면 `pythonw.exe run.py`를 사용합니다. 로그는
`%LOCALAPPDATA%\smart-alt-tab\app.log`에 남습니다.

해제: `Unregister-ScheduledTask -TaskName 'smart-alt-tab' -Confirm:$false`

### 관리자 권한으로 실행되는 앱을 쓴다면

Cursor·VS Code 등을 **관리자 권한으로 실행**하고 있다면, 일반 권한인 전환기로는 그 앱이
활성일 때 Alt+Tab을 감지하지도, 그 앱으로 포커스를 넘기지도 못합니다(Windows UIPI 제약이라
코드로 우회 불가). 이때는 위 **자동 실행** 등록이 해답입니다 — 작업 스케줄러가 전환기를
"가장 높은 권한"으로 띄워 주기 때문에 그 제약이 사라집니다.

## exe 직접 빌드하기

```
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

PyInstaller onefile로 `dist\smart-alt-tab.exe`(약 10MB)를 만듭니다. 사전 준비는
Python 3.13과 `py -3.13 -m pip install pyinstaller` 뿐입니다.

## 스택

Python 3.13 · ctypes(Win32 저수준 키보드 훅) · tkinter(고대비 다크) · PyInstaller

## 라이선스

MIT (예정)

---
Built by SVIL — Singularity Visual Intelligence Lab.
