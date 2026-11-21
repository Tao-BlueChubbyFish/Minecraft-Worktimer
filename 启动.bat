@echo off
setlocal
cd /d "%~dp0"
title MC 工时牌启动器

set "PY="
set "PYW="

rem ===== 1) 优先用 py 启动器 =====
for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if defined PY goto :havepy

rem ===== 2) PATH 里的 python：能真正执行才算数（自动跳过微软商店的占位程序）=====
for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if defined PY goto :havepy

rem ===== 3) 常见安装位置兜底 =====
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if not defined PY if exist "%%~d\python.exe" set "PY=%%~d\python.exe"
for /d %%d in ("C:/Python3*") do if not defined PY if exist "%%~d\python.exe" set "PY=%%~d\python.exe"
for /d %%d in ("C:/Program Files/Python3*") do if not defined PY if exist "%%~d\python.exe" set "PY=%%~d\python.exe"
for /d %%d in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do if not defined PY if exist "%%~d\python.exe" set "PY=%%~d\python.exe"
if defined PY goto :havepy

echo.
echo   [X] 没找到可用的 Python。
echo.
echo       两条路任选一条：
echo       1) 装一个 Python 3.10 以上版本，安装时勾选 "Add python.exe to PATH"，然后重新双击本脚本；
echo       2) 免安装：直接双击 ..\exe启动版\MCWorkTimer_v1.1.exe
echo.
pause
exit /b 1

:havepy
set "PYW=%PY:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PY%"

rem ---- 依赖检查 ----
"%PY%" -c "import PySide6" >nul 2>nul
if not errorlevel 1 goto :run

echo.
echo   [首次运行] 正在安装依赖 PySide6，只需要装一次，请稍等……
echo.

"%PY%" -m pip --version >nul 2>nul
if errorlevel 1 "%PY%" -m ensurepip --upgrade >nul 2>nul

"%PY%" -m pip install --disable-pip-version-check --no-input -r "%~dp0requirements.txt"
if not errorlevel 1 goto :run

echo.
echo   官方源没装上，换成清华镜像再试一次……
echo.
"%PY%" -m pip install --disable-pip-version-check --no-input -r "%~dp0requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if not errorlevel 1 goto :run

echo.
echo   [X] 依赖安装失败。可以手动执行下面的命令看看报错：
echo       "%PY%" -m pip install PySide6 -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.
echo   或者直接双击免安装版：..\exe启动版\MCWorkTimer_v1.1.exe
echo.
pause
exit /b 1

:run
start "" "%PYW%" "%~dp0main.py"
exit /b 0
