@echo off
chcp 65001 >nul
title GeoDownloader - Build Portavel
cls

echo ==================================================
echo   GeoDownloader - Build Versao Portatil
echo ==================================================
echo.

set BASE=%~dp0
set DIST=%BASE%dist_portable
set VERSION_STR=
for /f %%v in (%BASE%VERSION) do set VERSION_STR=%%v

echo Versao: %VERSION_STR%
echo Destino: %DIST%
echo.

:: Limpa build anterior
if exist "%DIST%" (
    echo Removendo build anterior...
    rmdir /s /q "%DIST%"
)
mkdir "%DIST%"

::  Baixa Python Embeddable 3.12 (Windows x64) 
set PY_VER=3.12.9
set PY_ZIP=python-%PY_VER%-embed-amd64.zip
set PY_URL=https://www.python.org/ftp/python/%PY_VER%/%PY_ZIP%

if not exist "%TEMP%\%PY_ZIP%" (
    echo Baixando Python Embeddable %PY_VER%...
    powershell -Command "Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%TEMP%\%PY_ZIP%' -UseBasicParsing"
    if errorlevel 1 (
        echo ERRO ao baixar Python. Verifique a conexao.
        pause
        exit /b 1
    )
)

echo Extraindo Python Embeddable...
mkdir "%DIST%\python"
powershell -Command "Expand-Archive -Path '%TEMP%\%PY_ZIP%' -DestinationPath '%DIST%\python' -Force"

:: Habilita import site no Python Embeddable (necessario para pip funcionar)
powershell -Command ^
    "(Get-Content '%DIST%\python\python312._pth') -replace '#import site','import site' | " ^
    "Set-Content '%DIST%\python\python312._pth'"

::  Baixa get-pip.py 
if not exist "%TEMP%\get-pip.py" (
    echo Baixando get-pip.py...
    powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%TEMP%\get-pip.py' -UseBasicParsing"
)
copy "%TEMP%\get-pip.py" "%DIST%\get-pip.py" >nul

::  Copia arquivos do app 
echo Copiando arquivos do app...
copy "%BASE%app.py"              "%DIST%\" >nul
copy "%BASE%geodata.py"          "%DIST%\" >nul
copy "%BASE%requirements.txt"    "%DIST%\" >nul
copy "%BASE%config.yaml.example" "%DIST%\" >nul
copy "%BASE%VERSION"             "%DIST%\" >nul
copy "%BASE%APP_STATE"           "%DIST%\" >nul
copy "%BASE%GeoDownloader.bat"   "%DIST%\" >nul

xcopy /E /I /Y "%BASE%templates" "%DIST%\templates" >nul
xcopy /E /I /Y "%BASE%sources"   "%DIST%\sources"   >nul

:: Cria pasta downloads vazia
mkdir "%DIST%\downloads"

::  LEIAME.txt 
(
echo GeoDownloader v%VERSION_STR% - Versao Portatil
echo ================================================
echo.
echo COMO USAR:
echo   1. Clique duas vezes em GeoDownloader.bat
echo   2. Na PRIMEIRA execucao: aguarde a instalacao dos pacotes (~2-5 min)
echo   3. O browser abrira automaticamente em http://localhost:5000
echo   4. Configure suas credenciais no menu Configuracoes (icone engrenagem)
echo.
echo REQUISITOS:
echo   - Windows 10 ou superior (64-bit)
echo   - Conexao com internet (apenas na 1a execucao para instalar pacotes)
echo.
echo DOWNLOADS:
echo   Os arquivos baixados ficam na pasta 'downloads\' ao lado deste arquivo.
echo.
echo CREDENCIAIS NECESSARIAS:
echo   - NASA Earthdata: https://urs.earthdata.nasa.gov (gratuito)
echo   - Copernicus CDSE: https://dataspace.copernicus.eu (gratuito)
echo.
echo SUPORTE: https://github.com/elpidioassinaturas/geodowloader
) > "%DIST%\LEIAME.txt"

::  Compacta em ZIP 
set ZIP_NAME=GeoDownloader_%VERSION_STR%_Windows.zip
echo.
echo Compactando em ZIP...
if exist "%BASE%dist\%ZIP_NAME%" del "%BASE%dist\%ZIP_NAME%"
if not exist "%BASE%dist" mkdir "%BASE%dist"
powershell -Command "Compress-Archive -Path '%DIST%\*' -DestinationPath '%BASE%dist\%ZIP_NAME%' -Force"

echo.
echo ==================================================
echo   Build concluido!
echo   Arquivo: dist\%ZIP_NAME%
for %%F in ("%BASE%dist\%ZIP_NAME%") do echo   Tamanho: %%~zF bytes
echo ==================================================
pause