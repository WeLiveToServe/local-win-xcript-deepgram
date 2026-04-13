$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Local Wispr Transcript.lnk"
$targetPath = Join-Path $root ".venv\Scripts\pythonw.exe"
$iconPath = Join-Path $root "assets\microphone.ico"

if (-not (Test-Path -LiteralPath $targetPath)) {
  throw "Launcher target not found: $targetPath"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = "-m local_wispr_transcript.cli"
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle = 1
$shortcut.Description = "Launch Local Wispr Transcript"
if (Test-Path -LiteralPath $iconPath) {
  $shortcut.IconLocation = $iconPath
}
$shortcut.Save()

Write-Host "Created Desktop shortcut at $shortcutPath"
