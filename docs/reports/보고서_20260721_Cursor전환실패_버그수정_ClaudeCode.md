# 완료보고서 — Cursor(Electron 앱) 전환 실패 버그수정

| 항목 | 내용 |
|------|------|
| 프로젝트 | smart-alt-tab |
| 유형 | 버그수정 |
| 버전 | v0.4.0 → **v0.4.1** |
| 작성일 | 2026-07-21 |
| 작업자 | Claude Code |
| 상태 | 수정·검증 완료 |

## 1. 증상

"지금 alt tab 하면 cursor로 전환이 안되는데" — Claude 등 다른 창에 있다가 Alt+Tab으로
Cursor를 선택해도 실제 포커스가 넘어가지 않고 원래 창에 그대로 머무름.

## 2. 원인 (실측)

`activate_window()`의 `SetForegroundWindow` 1차 시도는 포그라운드 락에 막혀 실패하는 게
정상이고, 그다음 `AttachThreadInput` 폴백이 이를 우회하도록 되어 있었다. `activate_window`에
임시로 디버그 로그를 넣어 실제 배포 앱(pythonw)에서 재현해보니:

```
[DIAG] first SetForegroundWindow(Cursor) -> False
[DIAG] AttachThreadInput(cur,fg) -> True
[DIAG] AttachThreadInput(cur,tgt) -> False err=5   ← ERROR_ACCESS_DENIED
[DIAG] retry SetForegroundWindow -> False err=5
```

Cursor(Electron/Chromium 계열) 창은 렌더러 프로세스가 **저무결성(Low integrity,
SID RID `0x1000`)** 으로 뜬다. 확인해보니 우리 프로세스는 일반 **Medium 무결성(`0x2000`)**.
`AttachThreadInput`은 서로 다른 무결성 수준의 스레드에 붙이려 하면 `ERROR_ACCESS_DENIED`로
거부된다 — 그래서 그 위에서 재시도하는 `SetForegroundWindow`도 같이 실패했다. 클로드/일반
앱처럼 우리와 같은 무결성 수준인 대상은 문제없이 전환됐기 때문에 M1~M3 테스트 때는 드러나지
않았다.

## 3. 수정

`AttachThreadInput` 폴백보다 먼저, **더미 키 입력 방식**을 시도하도록 `win/windows.py`에
`_inject_dummy_key()`를 추가했다. `VK_F15`(아무 앱에도 기본 바인딩이 없어 부작용 없음)를
press+release로 주입하면, 우리 스레드가 "방금 실제 입력을 받은 스레드" 자격을 얻어
`SetForegroundWindow`가 무결성 수준과 무관하게 통과한다. `AttachThreadInput` 경로는 최종
폴백으로 남겨뒀다(더미 입력마저 막히는 극단적 상황 대비).

```python
def activate_window(hwnd):
    ...
    if user32.SetForegroundWindow(hwnd):
        return True
    _inject_dummy_key()                    # 신규: 무결성 수준 무관
    if user32.SetForegroundWindow(hwnd):
        return True
    # 기존 AttachThreadInput 폴백 (최종 안전망)
    ...
```

## 4. 검증 (실측)

- 원인 진단: 실제 pythonw 배포 프로세스에 임시 디버그 로그를 넣고, 외부에서 keybd_event로
  Alt+Tab을 주입해 정확한 실패 지점(err=5)을 확인.
- 수정 후 동일 시나리오(Claude → Alt+Tab → Cursor) **4회 연속 성공**.
- 단위 테스트 12/12 유지(컨트롤러 로직 무변경, `windows.py`만 수정).
- 실 배포 인스턴스(Startup 등록 프로세스)에 직접 재현·수정 확인 후 재배포.

## 5. 교훈

Electron/Chromium 기반 앱(VS Code 계열, Cursor, Discord 등 다수)은 창별로 무결성 수준이
다를 수 있어, 순수 `SetForegroundWindow`/`AttachThreadInput`만으로는 전환이 실패할 수 있다.
창 전환 유틸리티는 더미 입력 주입 방식을 기본 폴백으로 포함해야 이런 앱까지 안정적으로
지원한다. `CLAUDE.md`에 기록해 재발 방지.
