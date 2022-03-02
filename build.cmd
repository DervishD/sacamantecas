@echo off
setlocal

rem Get virtual environment directory from the first line of .gitignore file.
set /p VENV_DIR=<.gitignore
rem Remove trailing EOL.
set VENV_DIR=%VENV_DIR:~0,-1%
set WORKPATH=%VENV_DIR%\build
set DISTPATH=%VENV_DIR%\dist

if not exist "%VENV_DIR%\" (
    echo Virtual environment does not exist at "%VENV_DIR%"
    call venv.cmd
)

echo Activating virtual environment
call "%VENV_DIR%\Scripts\activate.bat"
echo Building binary
pyinstaller --log-level=WARN --clean --workpath="%WORKPATH%" --distpath="%DISTPATH%" --specpath="%WORKPATH%" ^
    --onefile sacamantecas.py >NUL
echo Deativating virtual environment
call "%VENV_DIR%\Scripts\deactivate.bat"

if exist "%DISTPATH%\sacamantecas.exe" (
    echo Copying binary
    copy /b /y "%DISTPATH%\sacamantecas.exe" . >NUL
)

endlocal