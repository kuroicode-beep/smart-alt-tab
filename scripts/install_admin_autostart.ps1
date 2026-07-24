# scripts/install_admin_autostart.ps1
# smart-alt-tab을 "관리자 권한"으로 로그인 시 자동 실행되도록 작업 스케줄러에 등록한다.
#
# 왜 필요한가:
#   Cursor 등 관리자 권한으로 뜨는 앱은 High integrity라, 일반 권한(Medium)인 전환기는
#   Windows UIPI 때문에 (1) 그 앱이 활성일 때 저수준 키보드 훅으로 키를 받지 못하고
#   (2) 그 앱으로 포커스를 넘기지도 못한다. 전환기 자신이 관리자로 떠야 해결된다.
#
# 왜 시작프로그램 폴더가 아니라 작업 스케줄러인가:
#   시작프로그램 바로가기로 관리자 실행을 하면 로그인마다 UAC 창이 뜬다.
#   작업 스케줄러의 "가장 높은 권한으로 실행"은 UAC 창 없이 상승된 채로 자동 시작된다.
#
# 사용법: PowerShell을 "관리자 권한으로 실행"한 뒤
#   powershell -ExecutionPolicy Bypass -File scripts\install_admin_autostart.ps1

$ErrorActionPreference = "Stop"

$TaskName = "smart-alt-tab"
$RepoRoot = "C:\Projects\smart-alt-tab"
$RunPy    = Join-Path $RepoRoot "run.py"
$ExePath  = Join-Path $RepoRoot "dist\smart-alt-tab.exe"

# 관리자 권한 확인
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    throw "관리자 권한이 필요합니다. PowerShell을 '관리자 권한으로 실행'한 뒤 다시 실행하세요."
}

# 실행 방식 결정: 빌드된 exe가 있으면 그쪽을 쓴다(Python 설치에 의존하지 않아 더 안정적).
# 없으면 기존 방식(pythonw + run.py)으로 폴백한다 — 개발 중에는 exe를 매번 빌드하지 않으므로.
if (Test-Path $ExePath) {
    $Execute   = $ExePath
    $Arguments = $null
    $ModeLabel = "exe"
    Write-Output "실행 방식 : exe"
    Write-Output "exe      : $ExePath"
} else {
    $pythonw = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\pythonw.exe"
    if (-not (Test-Path $pythonw)) {
        $pyCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        if ($pyCmd) { $pythonw = $pyCmd.Source } else { throw "pythonw.exe를 찾을 수 없습니다: $pythonw" }
    }
    if (-not (Test-Path $RunPy)) { throw "exe도 run.py도 없습니다. 먼저 scripts\build_exe.ps1로 빌드하세요." }
    $Execute   = $pythonw
    $Arguments = "`"$RunPy`""
    $ModeLabel = "pythonw"
    Write-Output "실행 방식 : pythonw + run.py (exe가 없어 폴백)"
    Write-Output "pythonw  : $pythonw"
    Write-Output "run.py   : $RunPy"
}

# 기존 작업이 있으면 제거 후 재등록
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "기존 작업 '$TaskName' 제거 후 재등록합니다."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

if ($Arguments) {
    $action = New-ScheduledTaskAction -Execute $Execute -Argument $Arguments -WorkingDirectory $RepoRoot
} else {
    $action = New-ScheduledTaskAction -Execute $Execute -WorkingDirectory $RepoRoot
}
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# 가장 높은 권한(Highest) = 상승된 채 실행, UAC 창 없음
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Highest
# 배터리/유휴 상태와 무관하게 계속 실행, 실행 시간 제한 없음
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "smart-alt-tab 저시력 창 전환기 (관리자 권한 자동 실행)" | Out-Null

Write-Output "작업 스케줄러에 '$TaskName' 등록 완료 (가장 높은 권한, 로그인 시 실행)."

# 기존 시작프로그램 바로가기가 있으면 중복 실행되므로 제거
$startupLnk = Join-Path ([Environment]::GetFolderPath("Startup")) "smart-alt-tab.lnk"
if (Test-Path $startupLnk) {
    Remove-Item $startupLnk -Force
    Write-Output "중복 방지: 기존 시작프로그램 바로가기 제거됨 ($startupLnk)"
}

# 실행 중인 인스턴스를 찾는다 — exe로 뜬 것과 pythonw로 뜬 것 양쪽 모두.
# 실행 방식을 바꾸면 이전 방식의 인스턴스가 남아 중복 동작(훅 두 개)하므로 둘 다 정리해야 한다.
function Get-SmartAltTabProcess {
    @(Get-CimInstance Win32_Process -Filter "Name='smart-alt-tab.exe'") +
    @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like "*smart-alt-tab*run.py*" })
}

# 현재 실행 중인 인스턴스 종료 후 관리자 권한으로 즉시 시작
Get-SmartAltTabProcess | ForEach-Object {
    Write-Output "기존 인스턴스 종료: PID $($_.ProcessId) ($($_.Name))"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 700

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3

$running = Get-SmartAltTabProcess
if ($running) {
    Write-Output "실행 확인: PID $($running[0].ProcessId) ($ModeLabel, 관리자 권한)"
} else {
    Write-Warning "프로세스가 확인되지 않습니다. 작업 스케줄러에서 '$TaskName' 상태를 확인하세요."
}

Write-Output ""
Write-Output "완료. 다음 로그인부터 UAC 창 없이 관리자 권한으로 자동 실행됩니다."
Write-Output "해제하려면: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
