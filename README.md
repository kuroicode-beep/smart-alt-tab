# smart-alt-tab

Windows Alt+Tab을 대체하는 **저시력 친화 창 전환기**. 열린 창을 큰 글씨·고대비로 보여주고,
Alt를 누른 채 Tab/방향키로 고른 뒤 Alt를 놓으면 그 창으로 전환합니다.

> Windows 기본 Alt+Tab은 창 제목이 작아 저시력 사용자가 알아보기 어렵고, 전환기 내부의
> 하이라이트 이동을 표준 API로 알려주지 않습니다. 그래서 "고르는 중 실시간으로 크게 보기"는
> Alt+Tab을 통째로 대체해야만 가능합니다. 이 프로젝트가 그 대체 전환기입니다.

## 상태

M1·M2·M3 구현·검증 완료 (v0.4.0). 배경과 스펙은 [docs/prd](docs/prd/)를 참고하세요.

- Alt+Tab 가로채기·소비, 고대비 다크 텍스트 전환기, Tab/Shift+Tab/방향키 선택 이동,
  Alt 놓으면 전환, ESC 취소
- 창 목록 필터 정교화(소유 팝업 체인), 다중 모니터 배치(커서 모니터 작업영역 중앙),
  안전장치(열린 창 없으면 기본 Alt+Tab 폴백, Alt keyup 유실 시 자동 확정)
- 트레이 아이콘(설정·종료), 설정 화면(글꼴 3종·글자 크기 3단계·다국어 5종, 즉시 저장·적용),
  설정 안 업데이트 내역
- DPI: 대상 모니터별 논리→물리 px 실시간 환산

## 실행

```
py -3.13 run.py
```

Alt+Tab을 누르면 자체 전환기가 뜹니다. 트레이 아이콘을 우클릭하면 설정·종료.

### 자동 실행(시작프로그램 등록)

콘솔창 없이 로그인마다 자동 실행하려면 시작프로그램 폴더에 `pythonw.exe run.py` 바로가기를
등록하세요(작업폴더는 이 저장소 루트). 무콘솔 실행 시 로그는
`%LOCALAPPDATA%\smart-alt-tab\app.log`에 남습니다.

## 스택

Python 3.13 · ctypes(Win32 저수준 키보드 훅) · tkinter(고대비 다크) · PyInstaller

## 라이선스

MIT (예정)

---
Built by SVIL — Singularity Visual Intelligence Lab.
