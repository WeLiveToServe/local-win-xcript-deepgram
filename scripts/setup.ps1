$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$pythonCandidates = @(
  (Join-Path $HOME "AppData\Local\Programs\Python\Python312\python.exe"),
  (Join-Path $HOME "AppData\Local\Programs\Python\Python313\python.exe"),
  "py",
  "python"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
  if ($candidate -like "*.exe") {
    if (Test-Path -LiteralPath $candidate) {
      $python = $candidate
      break
    }
  } else {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) {
      $python = $candidate
      break
    }
  }
}

if (-not $python) {
  throw "Unable to locate a usable Python interpreter."
}

if (-not (Test-Path -LiteralPath $venv)) {
  & $python -m venv $venv
}

$venvPython = Join-Path $venv "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $root "requirements.txt")
& $venvPython -m pip install -e $root

if (-not (Test-Path -LiteralPath (Join-Path $root ".env")) -and (Test-Path -LiteralPath (Join-Path $root ".env.example"))) {
  Copy-Item -LiteralPath (Join-Path $root ".env.example") -Destination (Join-Path $root ".env")
}

Write-Host "Setup complete."
Write-Host "Next steps:"
Write-Host "1. Populate .env with DEEPGRAM_API_KEY if needed."
Write-Host "2. Run scripts/install-whispercpp.ps1 for local fallback."
Write-Host "3. Run scripts/test-backend.ps1 or scripts/run.ps1."
