$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $root "tools\whispercpp"
$modelsDir = Join-Path $root "models"
$tempDir = Join-Path $env:TEMP "local-wispr-transcript-whispercpp"

New-Item -ItemType Directory -Force -Path $toolsDir,$modelsDir,$tempDir | Out-Null

$release = Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/whisper.cpp/releases/latest"
$asset = $release.assets | Where-Object { $_.name -eq "whisper-bin-x64.zip" } | Select-Object -First 1

if (-not $asset) {
  throw "Unable to find whisper-bin-x64.zip in the latest whisper.cpp release."
}

$zipPath = Join-Path $tempDir "whisper-bin-x64.zip"
$extractDir = Join-Path $tempDir "whisper-bin-x64"
$modelPath = Join-Path $modelsDir "ggml-base.en.bin"

Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath

if (Test-Path -LiteralPath $extractDir) {
  Remove-Item -LiteralPath $extractDir -Recurse -Force
}

Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

Get-ChildItem -LiteralPath $extractDir -Recurse | ForEach-Object {
  if (-not $_.PSIsContainer) {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $toolsDir $_.Name) -Force
  }
}

if (-not (Test-Path -LiteralPath $modelPath)) {
  Invoke-WebRequest -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin" -OutFile $modelPath
}

Write-Host "Installed whisper.cpp to $toolsDir"
Write-Host "Model available at $modelPath"
