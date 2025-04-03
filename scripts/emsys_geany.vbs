Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "wsl ssh -X patch@192.168.1.203 'geany'", 0, False
