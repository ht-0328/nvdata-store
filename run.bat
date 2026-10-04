@echo off
goto :main
rem ===========================================================================
rem  nvdata-store - データ取得・管理画面の操作パネルを開く。
rem
rem    ダブルクリック                       : 操作パネルを開く。サーバーが止まっていれば
rem                                           起動して、ブラウザで画面を開く。
rem    run.bat --db D:\keiba\nvdata.duckdb --port 9001
rem
rem  サーバーの起動・開き直し・停止は操作パネルで行う。パネルを閉じてもサーバーは止まらない。
rem  パネルを使わないときは: uv run nvstore serve --open
rem
rem  このファイルの決まり:
rem    - 日本語は、上の goto :main と下の :main の間（このコメントの中）にだけ書く。
rem      cmd.exe は bat をコンソールのコードページ（日本語 Windows では 932）で読むので、
rem      実行される行に UTF-8 の日本語があると、行が途中で切れて誤動作する。
rem    - 文字コードは UTF-8（BOM なし）、改行は CRLF で保存する。
rem ===========================================================================
:main

cd /d "%~dp0"

where uv >nul 2>&1
if not errorlevel 1 set "UV=uv"
if not errorlevel 1 goto :run

set "UV=%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe"
if exist "%UV%" goto :run

echo [ERROR] uv was not found. Install uv or put it on PATH.
echo         Looked for: %UV%
goto :failed

:run
"%UV%" sync --quiet
if errorlevel 1 (
    echo [ERROR] "uv sync" failed.
    goto :failed
)

rem pythonw has no console window, so this window can close right away.
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m nvstore.cli panel %*
) else (
    "%UV%" run python -m nvstore.cli panel %*
    if errorlevel 1 goto :failed
)
exit /b 0

:failed
echo.
pause
exit /b 1
