@echo off
REM Example batch file wrapper for python_dev command
REM This shows how to create a Windows batch file that calls the CLI

REM Set Python path to find the gt module
set PYTHONPATH=R:\repo\gtvfx-contrib\gt\app\wrapper\py

REM Execute the wrapper CLI with the python_dev command
python -m gt.app.wrapper python_dev %*
