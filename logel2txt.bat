@echo off
REM logel2txt — 导出 ArmLogel 日志为 txt
REM 用法: logel2txt.bat <armlog目录|.logel> [-o 输出.txt] [--ue-base 17:15:12.275]
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%logel2txt.py" %*
exit /b %ERRORLEVEL%
