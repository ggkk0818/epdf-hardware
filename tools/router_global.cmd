@echo off
rem Same as router.cmd but with the global routing strategy and more passes.
setlocal
set "JRE=C:\Code\epdf-hardware\tools\jre25\jdk-25.0.4.1+1-jre\bin\java.exe"
set "FREEROUTING=C:\Code\epdf-hardware\tools\freerouting\freerouting-2.4.1.jar"
"%JRE%" -Djava.awt.headless=true -jar "%FREEROUTING%" -de "%~1" -do "%~2" -mp 30 -us global -l en -mt 4
exit /b %ERRORLEVEL%
