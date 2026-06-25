Set oShell = CreateObject("WScript.Shell")
oShell.Run "taskkill /F /FI ""imagename eq python.exe"" /FI ""memusage gt 50000""", 0, True
WScript.Sleep 3000
oShell.Run "cmd /c ""C:\Users\chsan\hermes-python\python.exe C:\Users\chsan\hermes\brain\interface\telegram_bot.py >> C:\Users\chsan\hermes\logs\hermes.log 2>&1""", 0, False
