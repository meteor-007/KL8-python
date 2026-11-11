' ========================================================
' K8-Quant Web Server Silent Background Launcher (VBScript)
' 纯后台静默启动守护，无任何黑窗口，关闭任何终端均不影响
' ========================================================
Set ws = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
opsDir = fso.GetParentFolderName(WScript.ScriptFullName)
' scripts/ops -> project root
projectDir = fso.GetParentFolderName(fso.GetParentFolderName(opsDir))

pythonExe = "C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe"
If Not fso.FileExists(pythonExe) Then
    pythonExe = "py.exe"
End If

cmdLine = "cmd.exe /c ""cd /d """ & projectDir & """ && """ & pythonExe & """ run_server.py --no-browser >> """ & projectDir & "\logs\web_server.log"" 2>&1"""
ws.Run cmdLine, 0, False
