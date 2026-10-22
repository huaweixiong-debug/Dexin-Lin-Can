@echo off
REM Batch file to run Python scripts using the Miniconda3 interpreter

set PYTHON_EXE="D:\miniconda3\python.exe"

if exist %PYTHON_EXE% (
    echo Using Python interpreter: %PYTHON_EXE%
    %PYTHON_EXE% %*
) else (
    echo Python interpreter not found at %PYTHON_EXE%
    pause
    exit /b 1
)