@echo off
REM Main entry point for gt.app.wrapper CLI
REM Usage: do [command] [args...]
REM        do --list
REM        do --info <command>

REM Set PYTHONPATH to find the gt module
set "PYTHONPATH=%~dp0..\py"

REM Execute the wrapper CLI module
python -m gt.app.wrapper %*

REM Exit with the same code as the Python process
exit /b %errorlevel%
