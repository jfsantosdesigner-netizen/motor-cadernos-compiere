@echo off

chcp 65001 >nul

set P=%~1

if "%P%"=="" set /p P=Arraste aqui a PASTA do ambiente e aperte Enter: 

python "%~dp0novo_ambiente.py" "%P%"

pause

