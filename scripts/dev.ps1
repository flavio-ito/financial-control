$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Execute scripts\setup.ps1 primeiro.' }
if (-not (Test-Path -LiteralPath (Join-Path $repo 'frontend\node_modules'))) { throw 'Execute npm.cmd --prefix frontend ci primeiro.' }
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $repo 'backend'
    & $python (Join-Path $PSScriptRoot 'dev.py')
    $result = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
exit $result
