[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location -LiteralPath $projectRoot
try {
    python -c "import PIL, PyInstaller"
    if ($LASTEXITCODE -ne 0) {
        throw '빌드 도구가 없습니다. python -m pip install -r requirements-dev.txt 명령을 먼저 실행해 주세요.'
    }

    python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name SBM4D `
        --exclude-module numpy `
        --distpath dist `
        --workpath build/pyinstaller `
        --specpath build `
        main.py

    if ($LASTEXITCODE -ne 0) {
        throw "SBM4D.exe 빌드에 실패했습니다. 종료 코드: $LASTEXITCODE"
    }

    Write-Host "빌드가 완료되었습니다: $projectRoot\dist\SBM4D.exe"
}
finally {
    Pop-Location
}
