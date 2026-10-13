@echo off
rem HR-metrics: start the local server on this PC (if not running yet) and open the browser.
set "PORT=8790"
set "PS=powershell -NoProfile -Command"
%PS% "try{(New-Object Net.Sockets.TcpClient('127.0.0.1',%PORT%)).Close();exit 0}catch{exit 1}" >nul 2>&1
if %errorlevel%==0 goto open
start "HR-metrics - do not close this window" /min "%~dp0program\node.exe" "%~dp0program\local.js"
%PS% "for($i=0;$i -lt 60;$i++){try{(New-Object Net.Sockets.TcpClient('127.0.0.1',%PORT%)).Close();exit 0}catch{Start-Sleep -Milliseconds 250}};exit 1" >nul 2>&1
if not %errorlevel%==0 (
  echo The program did not start. Check the minimized window "HR-metrics" for the reason.
  pause
  exit /b 1
)
:open
start "" "http://localhost:%PORT%/"
