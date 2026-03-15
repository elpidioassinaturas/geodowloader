@echo off
chcp 65001 > nul
title GeoDownloader

echo ==================================================
echo   GeoDownloader — Iniciando...
echo ==================================================

:: Verifica se venv existe
if not exist ".venv\Scripts\activate.bat" (
    echo Criando ambiente virtual...
    python -m venv .venv
)

:: Ativa o venv
call .venv\Scripts\activate.bat

:: Instala dependências se necessário
python -c "import flask" 2>nul || (
    echo Instalando dependencias...
    pip install -r requirements.txt
)

:: Cria config se não existir
if not exist "config.yaml" (
    copy config.yaml.example config.yaml > nul
    echo config.yaml criado a partir do exemplo.
    echo Por favor, preencha suas credenciais em config.yaml
)

:: Inicia o app
echo Iniciando GeoDownloader em http://localhost:5000
python app.py

pause
