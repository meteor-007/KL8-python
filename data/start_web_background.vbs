' ========================================================
' K8-Quant Web Server Silent Background Launcher (VBScript)
' 纯后台静默启动守护，无任何黑窗口，关闭任何终端均不影响
' ========================================================
Set ws = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonExe = "C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe"
If Not fso.FileExists(pythonExe) Then
    pythonExe = "py.exe"
End If

cmdLine = "cmd.exe /c ""cd /d """ & currentDir & """ && """ & pythonExe & """ run_server.py --no-browser >> """ & currentDir & "\logs\web_server.log"" 2>&1"""
ws.Run cmdLine, 0, False
