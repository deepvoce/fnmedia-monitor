$codex = Get-ChildItem -Path "C:\Program Files\WindowsApps" -Recurse -Filter "Codex.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if ($codex) {
    Write-Host "Codex found at: $codex"
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Codex.lnk")
    $Shortcut.TargetPath = $codex
    $Shortcut.WorkingDirectory = Split-Path $codex
    $Shortcut.Save()
    Write-Host "Shortcut created on desktop"
} else {
    Write-Host "Codex not found in WindowsApps"
}
