$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$requiredPython = '3.12'

if (-not (Test-Path -LiteralPath $venvPython)) {
  $baseVersion = & python -c "import sys; print('{}.{}'.format(*sys.version_info[:2]))"
  if ($LASTEXITCODE -ne 0 -or $baseVersion -ne $requiredPython) {
    throw "Python $requiredPython é necessário para criar o ambiente virtual; encontrado: $baseVersion."
  }
  & python -m venv (Join-Path $repo '.venv')
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$venvVersion = & $venvPython -c "import sys; print('{}.{}'.format(*sys.version_info[:2]))"
if ($LASTEXITCODE -ne 0 -or $venvVersion -ne $requiredPython) {
  throw "O ambiente .venv usa Python $venvVersion; recrie-o com Python $requiredPython."
}
& $venvPython -m pip install -r (Join-Path $repo 'backend\requirements.lock')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd --prefix (Join-Path $repo 'frontend') ci
exit $LASTEXITCODE
