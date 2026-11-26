Option Explicit
Dim shell, files, folder, runtime, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
runtime = "D:\Program Files\APPs\cs\python3.11.5\pythonw.exe"
If Not files.FileExists(runtime) Then
    MsgBox "Python runtime was not found. See README.md in this folder.", 48, "Xiaohan"
    WScript.Quit 1
End If
shell.CurrentDirectory = folder
command = Chr(34) & runtime & Chr(34) & " " & Chr(34) & folder & "\app.py" & Chr(34)
shell.Run command, 1, False
