$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Codex.lnk")
$Shortcut.TargetPath = "D:\Codex\codex.exe"
$Shortcut.WorkingDirectory = "D:\Codex"
$Shortcut.Save()
