$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend = (Resolve-Path (Join-Path $repo 'frontend')).Path
$source = Join-Path $frontend 'dist'
$target = Join-Path $repo 'backend\app\static'

& npm.cmd --prefix $frontend run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$resolvedRepo = [IO.Path]::GetFullPath($repo).TrimEnd('\') + '\'
$resolvedTarget = [IO.Path]::GetFullPath($target).TrimEnd('\') + '\'
if (-not $resolvedTarget.StartsWith($resolvedRepo, [StringComparison]::OrdinalIgnoreCase)) {
  throw "Destino de build fora do workspace: $resolvedTarget"
}
New-Item -ItemType Directory -Force -Path $target | Out-Null
Get-ChildItem -LiteralPath $target -Force | Remove-Item -Recurse -Force
Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force

