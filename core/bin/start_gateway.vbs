Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strBinDir = fso.GetParentFolderName(WScript.ScriptFullName)
strRootDir = fso.GetParentFolderName(strBinDir)
WshShell.CurrentDirectory = strRootDir

' Locate Python executable dynamically without hardcoded usernames
strPy = "pythonw.exe"
strLocalAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
strSysDrive = WshShell.ExpandEnvironmentStrings("%SystemDrive%")

If fso.FileExists(strLocalAppData & "\Microsoft\WindowsApps\pythonw.exe") Then
    strPy = strLocalAppData & "\Microsoft\WindowsApps\pythonw.exe"
ElseIf fso.FileExists(strLocalAppData & "\Microsoft\WindowsApps\python.exe") Then
    strPy = strLocalAppData & "\Microsoft\WindowsApps\python.exe"
Else
    strUsers = strSysDrive & "\Users"
    If fso.FolderExists(strUsers) Then
        For Each oSub In fso.GetFolder(strUsers).SubFolders
            If fso.FileExists(oSub.Path & "\AppData\Local\Microsoft\WindowsApps\pythonw.exe") Then
                strPy = oSub.Path & "\AppData\Local\Microsoft\WindowsApps\pythonw.exe"
                Exit For
            End If
        Next
    End If
End If

' Run TheDoom Gateway silently in background (0 = hidden window, False = don't wait)
WshShell.Run """" & strPy & """ """ & strRootDir & "\thedoomcontrol.py""", 0, False
