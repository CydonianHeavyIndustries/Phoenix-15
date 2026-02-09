' Create a Desktop shortcut to Start Bjorgsun-26.bat or built EXE
Dim shell, desktop, link, target
Set shell = CreateObject("WScript.Shell")
desktop = shell.SpecialFolders("Desktop")

' Prefer built EXE if available
target = WScript.CreateObject("Scripting.FileSystemObject").BuildPath(WScript.CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\..", "dist\Bjorgsun-26.exe")
If Not WScript.CreateObject("Scripting.FileSystemObject").FileExists(target) Then
  target = WScript.CreateObject("Scripting.FileSystemObject").BuildPath(WScript.CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\..", "Start Bjorgsun-26.bat")
End If

Set link = shell.CreateShortcut(desktop & "\Bjorgsun-26.lnk")
link.TargetPath = target
link.WorkingDirectory = WScript.CreateObject("Scripting.FileSystemObject").GetParentFolderName(target)
link.IconLocation = WScript.CreateObject("Scripting.FileSystemObject").BuildPath(WScript.CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\..", "ui\assets\Bjorgsunexeicon.ico")
link.Description = "Launch Bjorgsun-26"
link.Save
WScript.Echo "Shortcut created on Desktop."

