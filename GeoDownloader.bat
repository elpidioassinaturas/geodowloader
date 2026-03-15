@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title GeoDownloader
cls

set "BASE=%~dp0"
set "PYTHON=!BASE!python\python.exe"

echo ==================================================
echo   GeoDownloader - Iniciando...
echo ==================================================
echo.

if not exist "!PYTHON!" (
    echo ERRO: Python embutido nao encontrado.
    echo       Reinstale usando o INSTALAR.bat
    pause
    exit /b 1
)

:: Verifica se ja foi instalado
if exist "!BASE!.installed" goto :iniciar

::  Primeira execucao: instalar dependencias 
echo Primeira execucao detectada.
echo Instalando dependencias. Aguarde, isso leva alguns minutos...
echo.

:: Bootstrap pip
if exist "!BASE!python\Lib\site-packages\pip" goto :instalar_pkgs
echo Configurando pip...
"!PYTHON!" "!BASE!get-pip.py" --no-warn-script-location -q
if !errorlevel! neq 0 (
    echo ERRO ao instalar pip. Verifique sua conexao com a internet.
    pause
    exit /b 1
)

:instalar_pkgs
echo Instalando pacotes (flask, earthaccess, pystac-client, etc.)...
"!PYTHON!" -m pip install -r "!BASE!requirements.txt" --target "!BASE!pkgs" --no-warn-script-location --disable-pip-version-check -q
if !errorlevel! neq 0 (
    echo ERRO ao instalar dependencias. Verifique sua conexao com a internet.
    pause
    exit /b 1
)

echo instalado > "!BASE!.installed"
echo.
echo Instalacao concluida!
echo.

:iniciar
:: Mata processo anterior na porta 5000
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| find ":5000 " ^| find "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo ==================================================
echo   Abrindo em: http://localhost:5000
echo   Para encerrar: Ctrl+C ou feche esta janela
echo ==================================================
echo.

set "PYTHONPATH=!BASE!pkgs"
"!PYTHON!" "!BASE!app.py"

pause
endlocal