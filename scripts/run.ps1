$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
  throw "Virtual environment not found. Run scripts/setup.ps1 first."
}

& $venvPython -m local_wispr_transcript.cli @args

