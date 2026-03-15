@echo off
chcp 65001 >nul
title GeoDownloader - Instalador
cls

echo ==================================================
echo   GeoDownloader - Instalador / Atualizador
echo ==================================================
echo.

set "BASE=%~dp0"

::  Localiza o ZIP 
set "ZIP_FILE="
for %%F in ("%BASE%GeoDownloader_*.zip") do set "ZIP_FILE=%%F"

if not defined ZIP_FILE (
    echo ERRO: Nenhum arquivo GeoDownloader_*.zip encontrado nesta pasta.
    echo Coloque este instalador na mesma pasta do arquivo ZIP.
    pause
    exit /b 1
)

echo ZIP encontrado: %ZIP_FILE%
echo.

::  Destino da instalacao 
set "DEFAULT_DEST=C:\geodownloader"
set /p "DEST=Pasta de instalacao [%DEFAULT_DEST%]: "
if "%DEST%"=="" set "DEST=%DEFAULT_DEST%"

echo.
echo Instalando em: %DEST%
echo.

::  Modo: Nova instalacao ou Atualizacao 
set "UPDATE_MODE=0"
if exist "%DEST%\GeoDownloader.bat" (
    echo Instalacao existente detectada. Modo: ATUALIZACAO
    set "UPDATE_MODE=1"
    echo.
) else (
    echo Modo: NOVA INSTALACAO
    echo.
)

:: Garante que a pasta existe
if not exist "%DEST%" mkdir "%DEST%"

::  Preserva dados do usuario antes de atualizar 
if "%UPDATE_MODE%"=="1" (
    echo Preservando configuracoes e downloads...

    :: Backup temporario do config.yaml
    if exist "%DEST%\config.yaml" (
        copy /Y "%DEST%\config.yaml" "%TEMP%\gdl_config_backup.yaml" >nul
    )

    :: Preserva a pasta downloads (apenas move para temp se necessario)
    :: Nao movemos downloads  o extract nao sobrescreve pastas existentes no PowerShell

    :: Verifica se requirements.txt mudou (forcara reinstalacao de pacotes)
    set "FORCE_REINSTALL=0"
    if exist "%DEST%\requirements.txt" (
        fc /b "%DEST%\requirements.txt" "%TEMP%\gdl_req_check.txt" >nul 2>&1
    ) else (
        set "FORCE_REINSTALL=1"
    )
)

::  Extrai ZIP 
echo Extraindo arquivos...
powershell -Command ^
    "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%DEST%' -Force"

if errorlevel 1 (
    echo ERRO ao extrair o arquivo ZIP.

    :: Restaura config em caso de falha
    if exist "%TEMP%\gdl_config_backup.yaml" (
        copy /Y "%TEMP%\gdl_config_backup.yaml" "%DEST%\config.yaml" >nul
    )
    pause
    exit /b 1
)

::  Restaura config.yaml do usuario 
if "%UPDATE_MODE%"=="1" (
    if exist "%TEMP%\gdl_config_backup.yaml" (
        copy /Y "%TEMP%\gdl_config_backup.yaml" "%DEST%\config.yaml" >nul
        echo Configuracoes restauradas.
    )

    :: Se requirements.txt mudou, for?a reinstalacao dos pacotes
    if "%FORCE_REINSTALL%"=="1" (
        if exist "%DEST%\.installed" del "%DEST%\.installed"
        echo Dependencias serao atualizadas na proxima execucao.
    )
)

::  Cria config.yaml se nao existir ?
if not exist "%DEST%\config.yaml" (
    if exist "%DEST%\config.yaml.example" (
        copy "%DEST%\config.yaml.example" "%DEST%\config.yaml" >nul
        echo config.yaml criado. Configure suas credenciais no app.
    )
)

::  Cria atalho na Area de Trabalho 
echo Criando atalho na Area de Trabalho...
powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$s = $ws.CreateShortcut([System.IO.Path]::Combine($env:USERPROFILE, 'Desktop', 'GeoDownloader.lnk')); " ^
    "$s.TargetPath = '%DEST%\GeoDownloader.bat'; " ^
    "$s.WorkingDirectory = '%DEST%'; " ^
    "$s.Description = 'GeoDownloader - Busca e Download de Dados Raster'; " ^
    "$s.Save()"

if not errorlevel 1 (
    echo Atalho criado na Area de Trabalho.
)

::  Mensagem final 
echo.
echo ==================================================
if "%UPDATE_MODE%"=="0" (
    echo   Instalacao concluida com sucesso!
) else (
    echo   Atualizacao concluida com sucesso!
)
echo.
echo   Local: %DEST%
echo   Atalho criado na Area de Trabalho.
echo.
echo   Para iniciar: clique em GeoDownloader na Area de Trabalho
echo   ou execute: %DEST%\GeoDownloader.bat
echo ==================================================
echo.

:: Oferece iniciar agora
set /p "INICIAR=Deseja iniciar o GeoDownloader agora? [S/N]: "
if /i "%INICIAR%"=="S" (
    start "" "%DEST%\GeoDownloader.bat"
)

echo.
pause