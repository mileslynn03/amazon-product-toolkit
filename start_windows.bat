@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto local_python
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys,struct;sys.exit(0 if sys.version_info >= (3,10) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if not errorlevel 1 goto py_launcher
:try_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
python -c "import sys,struct;sys.exit(0 if sys.version_info >= (3,10) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if errorlevel 1 goto missing_python
python "%~dp0launcher.py" %*
goto finished
:local_python
"%~dp0.venv\Scripts\python.exe" "%~dp0launcher.py" %*
goto finished
:py_launcher
py -3 "%~dp0launcher.py" %*
goto finished
:missing_python
echo Please install 64-bit Python 3.11 or 3.12, then run this file again.
echo https://www.python.org/downloads/windows/
echo See README.md or README.en.md for instructions.
set "TOOLKIT_EXIT_CODE=1"
goto keep_error
:finished
set "TOOLKIT_EXIT_CODE=%errorlevel%"
if "%TOOLKIT_EXIT_CODE%"=="0" exit /b 0
:keep_error
if not defined CI pause
exit /b %TOOLKIT_EXIT_CODE%
