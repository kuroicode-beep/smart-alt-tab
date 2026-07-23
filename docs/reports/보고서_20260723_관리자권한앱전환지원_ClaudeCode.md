# 완료보고서 — 관리자 권한 앱(Cursor 등) 전환 지원

| 항목 | 내용 |
|------|------|
| 프로젝트 | smart-alt-tab |
| 유형 | 기능 추가(배포 방식 변경) |
| 버전 | v0.4.1 → **v0.4.2** |
| 작성일 | 2026-07-23 |
| 작업자 | Claude Code |
| 상태 | 구현 완료 · **사용자 조치 대기**(UAC 승인 필요) |

## 1. 증상

v0.4.1로 "무결성 수준 차이" 문제를 고쳤다고 판단했으나, 사용자 리포트로 재발 확인:

> "cursor 전환시 아직도 한번씩 오류가 나고 전환이 안됨.
> 포커스가 cursor에 가 있으면 기존 alt tab 화면이 뜨고 다른데선 정상이야."

**핵심 단서**: Cursor가 활성일 때 *우리 전환기가 아예 안 뜨고 Windows 기본 Alt+Tab이 뜬다.*
이는 전환 실패가 아니라 **키 입력 자체를 가로채지 못한 것**이다.

## 2. 원인 (실측, v0.4.1 진단의 오판 정정)

Cursor를 **관리자 권한으로 실행**한 상태였다(창 제목에 `[관리자]` 표시, 프로세스 High
integrity `0x3000`). 전환기는 일반 권한(Medium `0x2000`).

Windows UIPI 때문에 **두 가지가 모두** 막힌다:

1. **저수준 키보드 훅이 키를 아예 못 받는다** — 더 높은 무결성 프로세스가 포그라운드일 때,
   낮은 무결성 프로세스의 `WH_KEYBOARD_LL` 훅은 그 입력을 수신하지 못한다. 그래서 Alt+Tab을
   소비하지 못하고 Windows 기본 전환기가 그대로 뜬다.
2. `AttachThreadInput`이 `ERROR_ACCESS_DENIED`(5)로 실패해 포커스도 못 넘긴다.

추가로 이 PC는 `ForegroundLockTimeout`이 최대값(2147483647ms)이라 포그라운드 잠금도 극도로
엄격하다.

### v0.4.1 판단의 오류 정정

v0.4.1에서 도입한 `_inject_dummy_key()`(`VK_F15`)는 **포그라운드 락 완화에는 도움이 되지만
무결성 수준 차이는 넘지 못한다.** 당시 "고쳤다"고 본 것은 Cursor가 포그라운드가 아닌 조건에서
테스트가 통과한 것을 오판한 결과다. 더미 키 방식 자체는 유효하므로 코드에 유지하되, 권한
문제의 진짜 해결책은 아니었다.

**결론: 코드로 우회 불가 — OS(UIPI) 제약이다. 전환기 자신이 관리자 권한으로 실행되어야 한다.**

## 3. 조치

`scripts/install_admin_autostart.ps1` 신규 작성 — 작업 스케줄러에 **"가장 높은 권한으로 실행"**
작업을 등록해 로그인 시 관리자 권한으로 자동 실행되게 한다.

**왜 시작프로그램 폴더가 아니라 작업 스케줄러인가**: 시작프로그램 바로가기로 관리자 실행을
하면 로그인마다 UAC 창이 뜬다. 작업 스케줄러의 `-RunLevel Highest`는 **UAC 창 없이** 상승된
채로 자동 시작된다.

스크립트가 하는 일:
1. 관리자 권한 여부 확인(아니면 명확한 메시지와 함께 중단)
2. `pythonw.exe`·`run.py` 경로 검증
3. 기존 동명 작업이 있으면 제거 후 재등록(멱등)
4. 작업 등록(로그인 트리거, Highest, 배터리/시간 제한 없음, `MultipleInstances IgnoreNew`)
5. **중복 방지**: 기존 시작프로그램 바로가기(`smart-alt-tab.lnk`) 제거
6. 실행 중인 일반 권한 인스턴스 종료 → 작업 즉시 시작 → 실행 확인 출력

## 4. 검증

| 항목 | 결과 |
|------|------|
| 원인 규명 | Cursor High(`0x3000`) vs 전환기 Medium(`0x2000`) 실측 확인, 훅 미수신·`AttachThreadInput` err=5 확인 |
| 스크립트 문법 | `[Parser]::ParseFile` 파싱 검사 통과(오류 0) |
| 인코딩 | UTF-8 **BOM 포함** 확인(`ef bb bf`) — 한글 주석 포함 `.ps1`의 PowerShell 5.1 파싱 깨짐 방지 |
| 실제 등록·동작 | **미검증 — 사용자 조치 대기** |

## 5. 사용자 조치 필요 (미완)

이 스크립트는 **UAC 승인이 필요해 AI가 대신 실행할 수 없다.** 사용자가 한 번 실행해야 한다:

```
powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy','Bypass','-File','C:\Projects\smart-alt-tab\scripts\install_admin_autostart.ps1'"
```

실행 후 확인할 것:
- 작업 스케줄러에 `smart-alt-tab` 작업 등록됨(`Get-ScheduledTask -TaskName 'smart-alt-tab'`)
- 앱 프로세스가 High integrity로 실행 중
- **Cursor가 활성인 상태에서 Alt+Tab** → 기본 전환기가 아니라 우리 전환기가 뜨는지

현재 상태(2026-07-23 기준): 작업 스케줄러 **미등록**, 앱은 여전히 일반 권한(Medium)으로 실행
중이라 증상 그대로임.

## 6. 남은 것

- 위 사용자 조치 후 실동작 검증.
- 백로그(변동 없음): M4 창 썸네일 미리보기(선택), PyInstaller exe 빌드 + GitHub Pages
  다운로드 연결.
