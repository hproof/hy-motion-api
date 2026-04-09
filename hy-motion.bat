@echo off
:: HY-Motion API 服务管理脚本 (Windows)

setlocal enabledelayedexpansion

set "SERVICE_NAME=hy-motion-api"
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%"
set "CONFIG_FILE=%PROJECT_DIR%\config.toml"

echo HY-Motion API 服务管理脚本
echo =============================
echo.

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="-h" goto help
if "%1"=="--help" goto help

if "%1"=="install" goto install
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="reload" goto reload
if "%1"=="enable" goto enable
if "%1"=="disable" goto disable

:help
echo 用法: hy-motion.bat [command]
echo.
echo Commands:
echo   install   安装 Python 依赖 (到 HY-Motion-1.0 venv)
echo   enable    开启开机自启 (需管理员)
echo   disable   关闭开机自启 (需管理员)
echo   start     启动服务
echo   stop      停止服务
echo   restart   重启服务
echo   reload    重载配置
goto :eof

:: 从 config.toml 读取配置
:read_config
set "HY_PATH="
set "SERVER_HOST=0.0.0.0"
set "SERVER_PORT=8000"
set "SERVER_LOG_LEVEL="

for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /c:"path" /c:"host" /c:"port" /c:"log_level" "%CONFIG_FILE%"`) do (
    set "key=%%a"
    set "val=%%b"
    set "val=!val:"=!"
    set "val=!val: =!"

    if /i "!key!"=="path" set "HY_PATH=!val!"
    if /i "!key!"=="host" set "SERVER_HOST=!val!"
    if /i "!key!"=="port" set "SERVER_PORT=!val!"
    if /i "!key!"=="log_level" set "SERVER_LOG_LEVEL=!val!"
)
goto :eof

:install
call :read_config
if "%HY_PATH%"=="" (
    echo 无法从 config.toml 读取 hy_motion.path
    exit /b 1
)
set "VENV_DIR=%HY_PATH%\venv"
if not exist "%VENV_DIR%" (
    echo HY-Motion-1.0 虚拟环境不存在: %VENV_DIR%
    exit /b 1
)
echo 使用 HY-Motion-1.0 虚拟环境: %VENV_DIR%
echo 安装 Python 依赖到 HY-Motion-1.0...
"%VENV_DIR%\Scripts\pip.exe" install -r "%PROJECT_DIR%\requirements.txt"
echo 安装完成
goto :eof

:enable
call :read_config
if "%HY_PATH%"=="" (
    echo 无法从 config.toml 读取 hy_motion.path
    exit /b 1
)
set "VENV_DIR=%HY_PATH%\venv"
if not exist "%VENV_DIR%" (
    echo HY-Motion-1.0 虚拟环境不存在: %VENV_DIR%
    exit /b 1
)

set "UVICORN_CMD=%VENV_DIR%\Scripts\uvicorn.exe"
set "APP_CMD=src.hy_motion_api.main:app --app-dir \"%PROJECT_DIR%\" --host %SERVER_HOST% --port %SERVER_PORT%"
if defined SERVER_LOG_LEVEL set "APP_CMD=!APP_CMD! --log-level %SERVER_LOG_LEVEL%"

echo 开启开机自启...
schtasks /create /tn "%SERVICE_NAME%" /tr "\"%UVICORN_CMD%\" %APP_CMD%" /sc onlogon /rl limited /f
echo 已开启开机自启
goto :eof

:disable
echo 关闭开机自启...
schtasks /delete /tn "%SERVICE_NAME%" /f 2>nul
echo 已关闭开机自启
goto :eof

:start
call :read_config
if "%HY_PATH%"=="" (
    echo 无法从 config.toml 读取 hy_motion.path
    exit /b 1
)
set "VENV_DIR=%HY_PATH%\venv"

echo 启动服务...
schtasks /query /tn "%SERVICE_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    schtasks /run /tn "%SERVICE_NAME%"
) else (
    echo 服务未注册，直接启动...
    set "UVICORN_CMD=%VENV_DIR%\Scripts\uvicorn.exe"
    set "APP_CMD=src.hy_motion_api.main:app --app-dir \"%PROJECT_DIR%\" --host %SERVER_HOST% --port %SERVER_PORT%"
    if defined SERVER_LOG_LEVEL set "APP_CMD=!APP_CMD! --log-level %SERVER_LOG_LEVEL%"
    start /b cmd /c "\"!UVICORN_CMD:EXEC!=!\" !APP_CMD!"
)
goto :eof

:stop
echo 停止服务...
schtasks /end /tn "%SERVICE_NAME%" 2>nul
goto :eof

:restart
echo 重启服务...
schtasks /end /tn "%SERVICE_NAME%" 2>nul
schtasks /run /tn "%SERVICE_NAME%" 2>nul
echo 服务已重启
goto :eof

:reload
echo 重载配置 (重启服务)...
schtasks /end /tn "%SERVICE_NAME%" 2>nul
schtasks /run /tn "%SERVICE_NAME%" 2>nul
echo 配置已重载
goto :eof
