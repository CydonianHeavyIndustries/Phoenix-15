Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = """" & root & "\run_desktop.bat" & """"
shell.Run cmd, 0, False
