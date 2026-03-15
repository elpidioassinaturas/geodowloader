@echo off
chcp 65001 >nul
title GeoDownloader
cls

set BASE=%~dp0
set PYTHON=%BASE%python\python.exe

echo ==================================================
echo   GeoDownloader - Iniciando...
echo ==================================================
echo.

:: Verifica se Python embutido existe
if not exist "%PYTHON%" (
    echo ERRO: Python embutido nao encontrado em python\python.exe
    echo Por favor, baixe novamente o pacote completo.
    pause
    exit /b 1
)

:: primeira execucao: instala dependencias
if not exist "%BASE%.installed" (
    echo Primeira execucao detectada.
    echo Instalando dependencias (isso leva alguns minutos)...
    echo Por favor, aguarde e nao feche esta janela.
    echo.

    :: Bootstrap pip no Python embutido
    if not exist "%BASE%python\Lib\site-packages\pip" (
        echo Configurando pip...
        "%PYTHON%" "%BASE%get-pip.py" --no-warn-script-location -q
        if errorlevel 1 (
            echo ERRO ao instalar pip. Verifique sua conexao com a internet.
            pause
            exit /b 1
        )
    )

    :: Instala pacotes no diretorio pkgs\
    echo Instalando pacotes Python (flask, earthaccess, etc.)...
    "%PYTHON%" -m pip install -r "%BASE%requirements.txt" ^
        --target "%BASE%pkgs" ^
        --no-warn-script-location ^
        --disable-pip-version-check ^
        -q

    if errorlevel 1 (
        echo ERRO ao instalar dependencias. Verifique sua conexao.
        pause
        exit /b 1
    )

    echo instalado > "%BASE%.installed"
    echo.
    echo Instalacao concluida com sucesso!
    echo.
)

:: Mata processo anterior na porta 5000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000 " ^| find "LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Inicia o app
echo ==================================================
echo   Abrindo em: http://localhost:5000
echo   Para encerrar: Ctrl+C ou feche esta janela
echo ==================================================
echo.

set PYTHONPATH=%BASE%pkgs
"%PYTHON%" "%BASE%app.py"

pause