@echo off
REM Batch file to set up Python environment and run Python scripts
REM This serves as a workaround for the Trae IDE Python interpreter issue

setlocal

REM Set the path to the Python interpreter
set PYTHON_EXE="D:\miniconda3\python.exe"

REM Check if Python is available
if not exist %PYTHON_EXE% (
    echo Error: Python interpreter not found at %PYTHON_EXE%
    echo Please check the path to your Python installation
    pause
    exit /b 1
)

REM Display Python version
echo Python version:
echo %PYTHON_EXE% --version
%PYTHON_EXE% --version
echo.

REM Check if a script was provided
if "%~1" == "" (
    echo Usage: run_python_script.bat ^<script.py^> [args...]
    echo.
    echo Example: run_python_script.bat test_python_simple.py
    pause
    exit /b 1
)

REM Get the script path and arguments
set SCRIPT_PATH=%~1
shift
set ARGS=%*

REM Check if the script exists
if not exist "%SCRIPT_PATH%" (
    echo Error: Script "%SCRIPT_PATH%" does not exist
    pause
    exit /b 1
)

REM Run the script
echo Running script: %SCRIPT_PATH%
if not "%ARGS%" == "" (
    echo With arguments: %ARGS%
    %PYTHON_EXE% "%SCRIPT_PATH%" %ARGS%
) else (
    %PYTHON_EXE% "%SCRIPT_PATH%"
)

REM Capture the exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo Script completed with exit code: %EXIT_CODE%
pause

exit /b %EXIT_CODE%