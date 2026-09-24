@echo off
rem DSN -> SES router wrapper for `easyeda pcb autoroute --router "... {in} {out}"`
rem Usage: router.cmd <input.dsn> <output.ses>
setlocal
set "JRE=C:\Code\epdf-hardware\tools\jre25\jdk-25.0.4.1+1-jre\bin\java.exe"
set "FREEROUTING=C:\Code\epdf-hardware\tools\freerouting\freerouting-2.4.1.jar"
"%JRE%" -Djava.awt.headless=true -jar "%FREEROUTING%" -de "%~1" -do "%~2" -mp 20 -l en -mt 4
exit /b %ERRORLEVEL%
