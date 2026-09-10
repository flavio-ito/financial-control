$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
  & python -m venv (Join-Path $repo '.venv')
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $venvPython -m pip install -r (Join-Path $repo 'backend\requirements.lock')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd --prefix (Join-Path $repo 'frontend') ci
exit $LASTEXITCODE
