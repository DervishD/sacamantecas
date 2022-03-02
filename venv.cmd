@echo off
setlocal

rem Get virtual environment directory from the first line of .gitignore file.
set /p VENV_DIR=<.gitignore
rem Remove trailing EOL.
set VENV_DIR=%VENV_DIR:~0,-1%

if not exist "%VENV_DIR%\" (
    echo Setting up virtual environment at "%VENV_DIR%"
    python -m venv --upgrade-deps "%VENV_DIR%" >NUL
    echo Activating virtual environment
    call "%VENV_DIR%\Scripts\activate.bat"
    echo Installing packages locally
    pip install --requirement requirements.txt >NUL
    echo Deactivating virtual environment
    call "%VENV_DIR%\Scripts\deactivate.bat"
)
endlocal