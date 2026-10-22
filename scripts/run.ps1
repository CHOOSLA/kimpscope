param([ValidateRange(1, 65535)][int]$Port = 4173, [switch]$Setup)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
Push-Location $projectRoot
try {
    if ($Setup) {
        if (-not (Test-Path -LiteralPath $pythonPath)) {
            & py -3.12 -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 가상환경 생성에 실패했습니다.' }
        }
        & $pythonPath -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw '의존성 설치에 실패했습니다.' }
    }
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw '먼저 pwsh -File scripts/run.ps1 -Setup 을 실행하세요.' }
    & $pythonPath -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw '서버 실행에 실패했습니다.' }
} finally { Pop-Location }
