# scripts/build_exe.ps1
# smart-alt-tab을 콘솔창 없는 단일 exe로 빌드한다 (PyInstaller onefile).
#
# 왜 onefile + windowed인가:
#   배포 대상이 "Python을 모르는 저시력 사용자"다. 파일 하나만 받아 두 번 누르면 되어야 하고,
#   실행할 때 검은 콘솔 창이 뜨면 안 된다(--windowed = pythonw와 같은 무콘솔 실행).
#
# 관리자 권한(--uac-admin)은 일부러 넣지 않았다:
#   넣으면 수동 실행 때마다 UAC 창이 뜬다. 관리자 권한이 필요한 경우(관리자로 뜨는 Cursor 등)는
#   install_admin_autostart.ps1의 작업 스케줄러 등록으로 해결한다 — 그쪽은 UAC 창이 안 뜬다.
#
# 사용법:
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
# 결과물: dist\smart-alt-tab.exe

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$SrcPath  = Join-Path $RepoRoot "src"
$Entry    = Join-Path $RepoRoot "run.py"
$DistDir  = Join-Path $RepoRoot "dist"
$WorkDir  = Join-Path $RepoRoot "build"
$Version  = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim()
$ExePath  = Join-Path $DistDir "smart-alt-tab.exe"

if (-not (Test-Path $Entry)) { throw "진입점이 없습니다: $Entry" }

# Python 3.13 확인 (앱이 검증된 런타임)
$pyExe = (& py -3.13 -c "import sys; print(sys.executable)" 2>$null)
if (-not $pyExe) { throw "Python 3.13을 찾을 수 없습니다. 'py -3.13'이 동작하는지 확인하세요." }

# PyInstaller 확인 — 없으면 설치 명령을 알려주고 멈춘다(조용히 실패하지 않도록)
$piVer = (& py -3.13 -c "import PyInstaller; print(PyInstaller.__version__)" 2>$null)
if (-not $piVer) {
    throw "PyInstaller가 없습니다. 먼저 설치하세요:`n  py -3.13 -m pip install pyinstaller"
}

Write-Output "python      : $pyExe"
Write-Output "PyInstaller : $piVer"
Write-Output "버전        : v$Version"
Write-Output ""

# 이전 결과물 제거 — 빌드 실패를 성공으로 착각하지 않기 위해 먼저 지운다.
# PyInstaller의 --clean은 쓰지 않는다: 중간 파일(localpycs)을 지우다 간헐적으로
# "액세스가 거부되었습니다"로 빌드 전체가 죽는다(실측). 여기서 직접 지우는 편이 확실하다.
if (Test-Path $ExePath) { Remove-Item $ExePath -Force }
if (Test-Path $WorkDir) {
    try {
        Remove-Item $WorkDir -Recurse -Force -ErrorAction Stop
    } catch {
        throw "이전 빌드 폴더를 지우지 못했습니다: $WorkDir`n$($_.Exception.Message)`n(탐색기·백신이 잡고 있을 수 있습니다. 잠시 후 다시 실행하세요.)"
    }
}

# --paths src : run.py가 sys.path를 런타임에 조작하므로 정적 분석용 경로를 따로 알려줘야 한다
& py -3.13 -m PyInstaller `
    --noconfirm --onefile --windowed `
    --name "smart-alt-tab" `
    --paths $SrcPath `
    --distpath $DistDir `
    --workpath $WorkDir `
    --specpath $WorkDir `
    $Entry

if ($LASTEXITCODE -ne 0) { throw "PyInstaller 빌드 실패 (exit $LASTEXITCODE)" }
if (-not (Test-Path $ExePath)) { throw "빌드는 끝났는데 결과물이 없습니다: $ExePath" }

$sizeMb = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
Write-Output ""
Write-Output "빌드 완료: $ExePath ($sizeMb MB, v$Version)"
Write-Output ""
Write-Output "다음 단계:"
Write-Output "  1) 실행 확인   : & '$ExePath'  (Alt+Tab으로 전환기가 뜨는지, 트레이 아이콘이 있는지)"
Write-Output "  2) 자동 실행   : 관리자 PowerShell에서 scripts\install_admin_autostart.ps1"
Write-Output "  3) 릴리스 업로드: gh release create v$Version '$ExePath'"
