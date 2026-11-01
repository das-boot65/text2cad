param([switch]$BackendOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
if (-not (Test-Path .venv/Scripts/python.exe)) { throw 'Run scripts/setup.ps1 first.' }
Write-Host 'Text2CAD http://127.0.0.1:8001 (API); http://127.0.0.1:5174 (studio). Ctrl+C stops.'
$backendProcess = Start-Process -FilePath "$projectRoot/.venv/Scripts/python.exe" -ArgumentList @('-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8001','--env-file','.env') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
try {
    if ($BackendOnly) { Wait-Process -Id $backendProcess.Id } else {
        Set-Location frontend
        npm.cmd run dev
    }
} finally { if (-not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id } }
