@echo off
REM logel2txt — export ArmLogel logs to txt
REM usage: logel2txt.bat <armlog_dir|.logel> [-o out.txt] [--ue-base 17:15:12.275]
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%logel2txt.py" %*
exit /b %ERRORLEVEL%
