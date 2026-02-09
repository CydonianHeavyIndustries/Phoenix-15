Set oWS = CreateObject("WScript.Shell")
Dim fso
Set fso = CreateObject("Scripting.FileSystemObject")
Dim scriptDir
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Dim desktopDir
desktopDir = oWS.SpecialFolders("Desktop")
Dim linkPath
linkPath = desktopDir & "\Phoenix-15.lnk"
Set oLink = oWS.CreateShortcut(linkPath)
oLink.TargetPath = scriptDir & "\run_desktop.vbs"
oLink.WorkingDirectory = scriptDir
oLink.WindowStyle = 7
oLink.IconLocation = scriptDir & "\NewBjorgIcon.ico"
oLink.Save
