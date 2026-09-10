$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = if ($env:FINANCAS_PYTHON) { $env:FINANCAS_PYTHON } else { Join-Path $repo '.venv\Scripts\python.exe' }
& $python (Join-Path $PSScriptRoot 'export_openapi.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd --prefix (Join-Path $repo 'frontend') run generate:api
exit $LASTEXITCODE
