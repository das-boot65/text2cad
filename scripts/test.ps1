$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location "$projectRoot/backend"
$pythonExe = "$projectRoot/.venv/Scripts/python.exe"
foreach ($checkArgs in @(@('-m','ruff','check','.'), @('-m','ruff','format','--check','.'), @('-m','mypy','app'), @('-m','pytest','-q'))) {
    & $pythonExe @checkArgs
    if ($LASTEXITCODE -ne 0) { throw "Check failed: $checkArgs" }
}
Set-Location "$projectRoot/frontend"
foreach ($taskName in @('lint','format:check','typecheck','test','build')) {
    npm.cmd run $taskName
    if ($LASTEXITCODE -ne 0) { throw "Frontend check failed: $taskName" }
}
