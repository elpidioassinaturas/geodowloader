@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title GeoDownloader - Instalador
cls

echo ==================================================
echo   GeoDownloader - Instalador / Atualizador
echo ==================================================
echo.

set "BASE=%~dp0"

:: Localiza o ZIP na mesma pasta
set "ZIP_FILE="
for %%F in ("%BASE%GeoDownloader_*.zip") do set "ZIP_FILE=%%F"

if not defined ZIP_FILE (
    echo ERRO: Nenhum arquivo GeoDownloader_*.zip encontrado nesta pasta.
    echo Coloque este instalador na mesma pasta que o arquivo ZIP.
    pause
    exit /b 1
)

echo ZIP encontrado: !ZIP_FILE!
echo.

:: Destino padrao
set "DEFAULT_DEST=C:\geodownloader"
set /p "DEST=Pasta de instalacao [!DEFAULT_DEST!]: "
if "!DEST!"=="" set "DEST=!DEFAULT_DEST!"

echo.
echo Instalando em: !DEST!
echo.

:: Detecta modo (nova instalacao ou atualizacao)
set "UPDATE_MODE=0"
if exist "!DEST!\GeoDownloader.bat" (
    echo Instalacao existente detectada. Modo: ATUALIZACAO
    set "UPDATE_MODE=1"
) else (
    echo Modo: NOVA INSTALACAO
)
echo.

:: Garante que a pasta existe
if not exist "!DEST!" mkdir "!DEST!"

:: Backup do config.yaml antes de sobrescrever
if "!UPDATE_MODE!"=="1" (
    if exist "!DEST!\config.yaml" (
        echo Preservando configuracoes...
        copy /Y "!DEST!\config.yaml" "%TEMP%\gdl_config_backup.yaml" >nul
    )

    :: Verifica se requirements.txt mudou -- se nao existir backup, force reinstall
    if not exist "!DEST!\requirements.txt" (
        set "FORCE_PKG=1"
    ) else (
        set "FORCE_PKG=0"
    )
)

:: Extrai o ZIP
echo Extraindo arquivos...
powershell -NoProfile -Command "Expand-Archive -LiteralPath '!ZIP_FILE!' -DestinationPath '!DEST!' -Force"
if errorlevel 1 (
    echo ERRO ao extrair o ZIP.
    if exist "%TEMP%\gdl_config_backup.yaml" copy /Y "%TEMP%\gdl_config_backup.yaml" "!DEST!\config.yaml" >nul
    pause
    exit /b 1
)

:: Restaura config.yaml
if "!UPDATE_MODE!"=="1" (
    if exist "%TEMP%\gdl_config_backup.yaml" (
        copy /Y "%TEMP%\gdl_config_backup.yaml" "!DEST!\config.yaml" >nul
        echo Configuracoes restauradas.
    )
    if "!FORCE_PKG!"=="1" (
        if exist "!DEST!\.installed" del "!DEST!\.installed"
        echo Pacotes Python serao atualizados na proxima execucao.
    )
)

:: Cria config.yaml se nao existir
if not exist "!DEST!\config.yaml" (
    if exist "!DEST!\config.yaml.example" (
        copy "!DEST!\config.yaml.example" "!DEST!\config.yaml" >nul
        echo config.yaml criado. Configure suas credenciais no app.
    )
)

:: Cria atalho na Area de Trabalho
echo Criando atalho na Area de Trabalho...
set "LNK=%USERPROFILE%\Desktop\GeoDownloader.lnk"
set "TARGET=!DEST!\GeoDownloader.bat"
powershell -NoProfile -Command "$ws=$env:USERPROFILE+'\Desktop\GeoDownloader.lnk'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($ws); $s.TargetPath='!TARGET!'; $s.WorkingDirectory='!DEST!'; $s.Description='GeoDownloader'; $s.Save()"

if not errorlevel 1 echo Atalho criado na Area de Trabalho.

:: Resultado final
echo.
echo ==================================================
if "!UPDATE_MODE!"=="0" (
    echo   Instalacao concluida!
) else (
    echo   Atualizacao concluida!
)
echo.
echo   Local : !DEST!
echo   Atalho: Area de Trabalho - GeoDownloader
echo ==================================================
echo.

set /p "INICIAR=Deseja iniciar o GeoDownloader agora? [S/N]: "
if /i "!INICIAR!"=="S" start "" "!DEST!\GeoDownloader.bat"

echo.
pause
endlocal