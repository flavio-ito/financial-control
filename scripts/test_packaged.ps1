param([string]$PackageDirectory = '')
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $PackageDirectory) { $PackageDirectory = Join-Path $repo 'dist\ControleFinanceiroLocal' }
$package = (Resolve-Path -LiteralPath $PackageDirectory).Path
$expectedRoot = [IO.Path]::GetFullPath((Join-Path $repo 'dist')).TrimEnd('\') + '\'
if (-not ($package + '\').StartsWith($expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Pacote fora de dist.' }
$testData = Join-Path $repo 'build\packaged-smoke-data'
$expectedDataRoot = [IO.Path]::GetFullPath((Join-Path $repo 'build')).TrimEnd('\') + '\'
$resolvedData = [IO.Path]::GetFullPath($testData)
if (-not ($resolvedData + '\').StartsWith($expectedDataRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Dados de smoke fora de build.' }
if (Test-Path -LiteralPath $testData) { Remove-Item -LiteralPath $testData -Recurse -Force }
New-Item -ItemType Directory -Path $testData | Out-Null
$oldData = $env:FINANCAS_DATA_DIR
$oldBrowser = $env:FINANCAS_NO_BROWSER
$oldDialog = $env:FINANCAS_NO_DIALOG
$env:FINANCAS_DATA_DIR = $testData
$env:FINANCAS_NO_BROWSER = '1'
$env:FINANCAS_NO_DIALOG = '1'
$originalPath = $env:Path
$env:Path = "$env:SystemRoot\System32;$env:SystemRoot"
$selfTest = Start-Process -FilePath (Join-Path $package 'ControleFinanceiroLocal.exe') -ArgumentList '--self-test' -WorkingDirectory $package -WindowStyle Hidden -PassThru -Wait
if ($selfTest.ExitCode -ne 0) {
  $details = Get-Content -LiteralPath (Join-Path $testData 'self-test-result.json') -Raw -ErrorAction SilentlyContinue
  throw "Autoteste empacotado falhou: $details"
}
$selfTestResult = Get-Content -LiteralPath (Join-Path $testData 'self-test-result.json') -Raw | ConvertFrom-Json
if ($selfTestResult.status -ne 'ok' -or $selfTestResult.account_count -ne 1 -or $selfTestResult.payment_count -ne 1 -or $selfTestResult.foreign_keys -ne 1) { throw 'Resultado inválido do autoteste empacotado.' }
$process = Start-Process -FilePath (Join-Path $package 'ControleFinanceiroLocal.exe') -WorkingDirectory $package -WindowStyle Hidden -PassThru
try {
  $runtime = Join-Path $testData 'runtime.json'
  $deadline = [DateTime]::UtcNow.AddSeconds(30)
  while (-not (Test-Path -LiteralPath $runtime)) {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Executável não iniciou em 30 segundos.' }
    Start-Sleep -Milliseconds 200
  }
  $info = Get-Content -LiteralPath $runtime -Raw | ConvertFrom-Json
  $health = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/api/v1/health" -f $info.port) -TimeoutSec 10
  if ($health.status -ne 'ok') { throw 'Health check empacotado falhou.' }
  $spa = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:{0}/planejamento" -f $info.port) -TimeoutSec 10
  if ($spa.StatusCode -ne 200 -or $spa.Content -notmatch '<div id="root">') { throw 'Fallback SPA empacotado falhou.' }
  try { Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:{0}/api/v1/inexistente" -f $info.port) -TimeoutSec 10 | Out-Null; throw 'API inexistente não retornou erro.' } catch { if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw } }
  $second = Start-Process -FilePath (Join-Path $package 'ControleFinanceiroLocal.exe') -WorkingDirectory $package -WindowStyle Hidden -PassThru -Wait
  if ($second.ExitCode -ne 2) { throw "Segunda instância retornou $($second.ExitCode), esperado 2." }
  $database = Join-Path $testData 'database.sqlite3'
  if (-not (Test-Path -LiteralPath $database)) { throw 'Banco não foi criado fora do pacote.' }
  Write-Output "PACKAGED_SMOKE_OK port=$($info.port) pid=$($info.pid)"
} finally {
  if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
  $env:FINANCAS_DATA_DIR = $oldData
  $env:FINANCAS_NO_BROWSER = $oldBrowser
  $env:FINANCAS_NO_DIALOG = $oldDialog
  $env:Path = $originalPath
}
