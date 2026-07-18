# AGENTS.md

smart-alt-tab — Windows Alt+Tab을 대체하는 저시력 친화 창 전환기.

모든 에이전트(Cursor·Codex 등)는 프로젝트 규칙·기술 배경·검증 결과를 **`CLAUDE.md`** 에서
확인한다. 이 파일은 요약 포인터다.

- 스택: Python 3.13 · ctypes(Win32) · tkinter · PyInstaller
- 핵심: `WH_KEYBOARD_LL` 훅으로 Alt+Tab 감지·소비(콜백 stdcall 필수), `EnumWindows`+cloaked 필터로 창 목록
- 접근성: SVIL 고대비 다크·큰 글씨·DPI 인식 (`/svil-frontend-design` 스킬이 정본)
- 버전: SemVer, `VERSION`/`VERSIONING.md`
- 문서 이중 저장(로컬 docs/ + Vault), 파일명 `카테고리_YYYYMMDD_내용_작업자.md`

자세한 내용은 `CLAUDE.md` 참고.
