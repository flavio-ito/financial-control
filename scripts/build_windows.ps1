$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$frontend = Join-Path $repo 'frontend'
$spec = Join-Path $repo 'packaging\windows\ControleFinanceiroLocal.spec'
$work = Join-Path $repo 'build\pyinstaller'
$dist = Join-Path $repo 'dist'
$package = Join-Path $dist 'ControleFinanceiroLocal'
$zip = Join-Path $dist 'ControleFinanceiroLocal-windows-x64.zip'
$checksum = "$zip.sha256"

if (-not (Test-Path -LiteralPath $python)) { throw 'Execute scripts\setup.ps1 primeiro.' }

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'scripts\generate_api_types.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest (Join-Path $repo 'backend\tests') -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd --prefix $frontend test -- --run
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd --prefix $frontend run typecheck
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'scripts\build_frontend.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m PyInstaller --noconfirm --clean --workpath $work --distpath $dist $spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = Join-Path $package 'ControleFinanceiroLocal.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "Executável ausente: $exe" }
if (-not (Test-Path -LiteralPath (Join-Path $package 'app\static\index.html'))) { throw 'SPA compilada ausente do pacote.' }
if (-not (Test-Path -LiteralPath (Join-Path $package 'migrations\env.py'))) { throw 'Migrações ausentes do pacote.' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'scripts\test_packaged.ps1') -PackageDirectory $package
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -LiteralPath $package -DestinationPath $zip -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $zip)) { throw 'ZIP final não foi criado.' }
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $checksum -Value "$hash  ControleFinanceiroLocal-windows-x64.zip" -Encoding ascii
Write-Output "PACKAGE_DIR=$package"
Write-Output "PACKAGE_ZIP=$zip"
Write-Output "PACKAGE_SHA256=$hash"
