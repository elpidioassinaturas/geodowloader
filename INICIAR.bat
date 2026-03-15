@echo off
chcp 65001 >nul
title GeoDownloader
cls

echo ==================================================
echo   GeoDownloader — Iniciando...
echo ==================================================
echo.

:: Verifica se Python está disponível
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale o Python 3.9 ou superior.
    pause
    exit /b 1
)

:: Cria venv se não existir
if not exist ".venv\Scripts\activate.bat" (
    echo Criando ambiente virtual...
    python -m venv .venv
    echo.
)

:: Ativa o venv
call .venv\Scripts\activate.bat

:: Sempre verifica/instala dependencias (rapido se tudo ja estiver instalado)
echo Verificando dependencias...
pip install -r requirements.txt --quiet --disable-pip-version-check
echo.

:: Cria config se não existir
if not exist "config.yaml" (
    copy config.yaml.example config.yaml >nul
    echo config.yaml criado. Preencha suas credenciais pelo menu Configuracoes.
    echo.
)

:: Mata processo anterior na porta 5000 se houver
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000 " ^| find "LISTENING" 2^>nul') do (
    echo Encerrando processo anterior na porta 5000 (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)

:: Inicia o app
echo ==================================================
echo   Abrindo em: http://localhost:5000
echo   Para encerrar: feche esta janela ou pressione Ctrl+C
echo ==================================================
echo.
python app.py

pause
