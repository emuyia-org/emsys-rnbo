Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "wsl ssh -X patch@192.168.1.203 'thunar'", 0, False
