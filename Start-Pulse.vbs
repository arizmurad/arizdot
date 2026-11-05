Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
base = fs.GetParentFolderName(WScript.ScriptFullName)
shell.Run "pythonw.exe """ & base & "\arizdot.py""", 0, False
