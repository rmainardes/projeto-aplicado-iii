@echo off
rem ===========================================================================
rem  iniciar_aplicacao_schulz.bat - Certificados de calibracao (Schulz S.A.)
rem  Projeto Aplicado III - AV05 - versao local (Python) do MVP
rem
rem  1. Verifica o Python 3.10+ no PATH (python, python3 ou o lancador py -3)
rem  2. Cria o ambiente virtual .venv (so na primeira vez)
rem  3. Instala os pacotes do requirements.txt (de novo so se o arquivo mudar)
rem  4. Sobe a API (app.py) numa janela propria e abre a interface no navegador
rem
rem  Uso: clique duas vezes, ou no terminal:
rem      iniciar_aplicacao_schulz.bat          (so nesta maquina)
rem      iniciar_aplicacao_schulz.bat --lan    (QR Code acessivel pelo celular no mesmo Wi-Fi)
rem  Porta: variavel SCHULZ_PORTA (padrao 5000).
rem ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Schulz - iniciando
if not defined SCHULZ_PORTA set "SCHULZ_PORTA=5000"
set "URL=http://127.0.0.1:%SCHULZ_PORTA%/"
set "VENV_PY=.venv\Scripts\python.exe"

echo.
echo  ==============================================================
echo   Certificados de calibracao - Schulz S.A. (versao local)
echo  ==============================================================
echo.

rem --- 1. Python 3.10+ ---------------------------------------------------------
echo [1/4] Verificando o Python 3.10 ou superior no PATH...
set "PY="
call :testar_python python
if not defined PY call :testar_python python3
if not defined PY call :testar_python py -3
if not defined PY (
    echo.
    echo  [ERRO] Python 3.10 ou superior nao encontrado no PATH.
    echo         Instale pelo site https://www.python.org/downloads/ e marque a opcao
    echo         "Add python.exe to PATH" no instalador. Depois rode este arquivo de novo.
    goto :falha
)
for /f "delims=" %%V in ('!PY! --version 2^>^&1') do echo        OK: %%V ^(comando: !PY!^)

rem --- 2. Ambiente virtual -----------------------------------------------------
echo [2/4] Preparando o ambiente virtual (.venv)...
if not exist "%VENV_PY%" (
    !PY! -m venv .venv
    if errorlevel 1 (
        echo  [ERRO] Nao foi possivel criar o ambiente virtual em .venv
        goto :falha
    )
    echo        Ambiente virtual criado.
) else (
    echo        Ambiente virtual ja existe.
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo  [ERRO] Nao foi possivel ativar o ambiente virtual. Apague a pasta .venv e tente de novo.
    goto :falha
)

rem --- 3. Bibliotecas ----------------------------------------------------------
echo [3/4] Instalando as bibliotecas do requirements.txt...
rem Reinstala se o requirements.txt mudou desde a ultima instalacao ou se algum pacote sumiu.
"%VENV_PY%" -c "import pathlib, sys; r = pathlib.Path('requirements.txt').read_bytes(); m = pathlib.Path('.venv/requirements.instalado'); sys.exit(0 if m.is_file() and m.read_bytes() == r else 1)" >nul 2>&1
if not errorlevel 1 "%VENV_PY%" -c "import flask, openpyxl, fpdf, segno" >nul 2>&1
if errorlevel 1 (
    "%VENV_PY%" -m pip install --disable-pip-version-check --quiet -r requirements.txt
    if errorlevel 1 (
        echo  [ERRO] Falha ao instalar as bibliotecas. Verifique a conexao com a internet
        echo         ^(ou o proxy da rede^) e rode este arquivo de novo.
        goto :falha
    )
    copy /y requirements.txt ".venv\requirements.instalado" >nul
    echo        Bibliotecas instaladas.
) else (
    echo        Bibliotecas ja instaladas e atualizadas.
)

rem --- 4. API + navegador ------------------------------------------------------
echo [4/4] Iniciando a API e abrindo a interface...
call :saude
if not errorlevel 1 (
    echo        A aplicacao ja estava rodando em %URL%
    goto :abrir
)
start "Schulz - API em %URL% (feche esta janela para encerrar)" "%VENV_PY%" app.py %*
set /a TENTATIVAS=0
:esperar
call :saude
if not errorlevel 1 goto :abrir
set /a TENTATIVAS+=1
if !TENTATIVAS! geq 40 (
    echo  [ERRO] A API nao respondeu em %URL% depois de 40 segundos.
    echo         Veja a mensagem na janela "Schulz - API". Se a porta %SCHULZ_PORTA% estiver ocupada,
    echo         rode: set SCHULZ_PORTA=5050 ^&^& iniciar_aplicacao_schulz.bat
    goto :falha
)
rem ping como espera de 1 s: funciona mesmo sem console interativo (o timeout nao).
ping -n 2 127.0.0.1 >nul
goto :esperar

:abrir
start "" "%URL%"
echo.
echo  Pronto: interface aberta em %URL%
echo  - Planilhas de teste: aba "Planilhas de exemplo" (ou nucleo\src\test\resources\planilhas)
echo  - Certificados e banco local: pasta dados\
echo  - Para encerrar, feche a janela "Schulz - API".
echo.
endlocal
exit /b 0

:falha
echo.
pause
endlocal
exit /b 1

rem --- sub-rotinas -------------------------------------------------------------
:testar_python
rem Roda o comando e exige versao 3.10+. O atalho "python" da Microsoft Store (que so abre a
rem loja) falha aqui e e ignorado.
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%*"
exit /b 0

:saude
rem 0 = a API respondeu em /api/saude. Sem proxy: o pedido e para a propria maquina.
"%VENV_PY%" -c "import urllib.request as u; u.build_opener(u.ProxyHandler({})).open('http://127.0.0.1:%SCHULZ_PORTA%/api/saude', timeout=1)" >nul 2>&1
exit /b %errorlevel%
