param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
if (-not $Python) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $Python = (& uv python find '>=3.11,<3.13' --no-python-downloads).Trim()
    } else {
        $Python = (& py -3.12 -c 'import sys; print(sys.executable)').Trim()
        if ($LASTEXITCODE -ne 0) { $Python = (& py -3.11 -c 'import sys; print(sys.executable)').Trim() }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { throw 'Pass -Python with a Python 3.11/3.12 executable.' }
& $Python -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,13); print(sys.version)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11/3.12 required.' }
if (-not (Test-Path .venv)) { & $Python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& .\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Python dependency check failed.' }
if (-not (Test-Path .env)) {
    $secretBytes = New-Object byte[] 32
    $secretGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $secretGenerator.GetBytes($secretBytes)
    $secretGenerator.Dispose()
    'TEXT2CAD_SECRET=' + [Convert]::ToBase64String($secretBytes) | Set-Content .env
}
Push-Location frontend
try { npm.cmd ci --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' } } finally { Pop-Location }
Write-Host 'Setup complete. Local login secret is in .env (ignored by Git). Run scripts/start.ps1.'
