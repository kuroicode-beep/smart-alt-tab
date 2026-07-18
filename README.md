# smart-alt-tab

Windows Alt+Tab을 대체하는 **저시력 친화 창 전환기**. 열린 창을 큰 글씨·고대비로 보여주고,
Alt를 누른 채 Tab/방향키로 고른 뒤 Alt를 놓으면 그 창으로 전환합니다.

> Windows 기본 Alt+Tab은 창 제목이 작아 저시력 사용자가 알아보기 어렵고, 전환기 내부의
> 하이라이트 이동을 표준 API로 알려주지 않습니다. 그래서 "고르는 중 실시간으로 크게 보기"는
> Alt+Tab을 통째로 대체해야만 가능합니다. 이 프로젝트가 그 대체 전환기입니다.

## 상태

M1 구현·검증 완료 (v0.2.0) · M2 예정. 배경과 스펙은 [docs/prd](docs/prd/)를 참고하세요.

Alt+Tab 가로채기·소비, 고대비 다크 텍스트 전환기, Tab/Shift+Tab/방향키 선택 이동,
Alt 놓으면 전환, ESC 취소가 동작합니다.

## 실행

```
py -3.13 run.py
```

Alt+Tab을 누르면 자체 전환기가 뜹니다. 종료는 실행한 콘솔에서 Ctrl+C.

## 스택

Python 3.13 · ctypes(Win32 저수준 키보드 훅) · tkinter(고대비 다크) · PyInstaller

## 라이선스

MIT (예정)

---
Built by SVIL — Singularity Visual Intelligence Lab.
