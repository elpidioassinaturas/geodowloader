@echo off
chcp 65001 >nul
title GeoDownloader
cls

echo ==================================================
echo   GeoDownloader - Iniciando...
echo ==================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale o Python 3.9 ou superior.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
    echo Criando ambiente virtual...
    python -m venv .venv
    echo.
)

call .venv\Scripts\activate.bat

echo Verificando dependencias...
pip install -r requirements.txt --quiet --disable-pip-version-check
echo.

if not exist "config.yaml" (
    copy config.yaml.example config.yaml >nul
    echo config.yaml criado. Preencha suas credenciais pelo menu Configuracoes.
    echo.
)

for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000 " ^| find "LISTENING" 2^>nul') do (
    echo Encerrando processo anterior na porta 5000...
    taskkill /PID %%a /F >nul 2>&1
)

echo ==================================================
echo   Abrindo em: http://localhost:5000
echo   Para encerrar: Ctrl+C
echo ==================================================
echo.
python app.py

pause