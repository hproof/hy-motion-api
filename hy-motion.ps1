Set-StrictMode -Version Latest

$ServiceName = "hy-motion-api"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigFile = Join-Path $ProjectDir "config.toml"

function Show-Help {
    Write-Host "用法: hy-motion.ps1 [command]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  install   安装 Python 依赖 (到 HY-Motion-1.0 venv)"
    Write-Host "  enable    开启开机自启 (需管理员)"
    Write-Host "  disable   关闭开机自启 (需管理员)"
    Write-Host "  start     启动服务"
    Write-Host "  stop      停止服务"
    Write-Host "  restart   重启服务"
    Write-Host "  reload    重载配置"
}

function Read-Config {
    if (-not (Test-Path $ConfigFile)) {
        throw "配置文件不存在: $ConfigFile"
    }

    $cfg = @{
        hy_path = ""
        host = "0.0.0.0"
        port = "8000"
        log_level = ""
        test_mode = "false"
    }

    $section = ""
    Get-Content $ConfigFile | ForEach-Object {
        $line = $_
        if ($line -match "#") {
            $line = $line.Split("#")[0]
        }
        $line = $line.Trim()
        if ($line -eq "") { return }
        if ($line -match "^\[(.+)\]$") {
            $section = $Matches[1]
            return
        }
        if ($line -match "^(path)\s*=\s*(.+)$") {
            if ($section -eq "hy_motion") {
                $val = $Matches[2].Trim().Trim('"')
                $cfg["hy_path"] = $val
            }
            return
        }
        if ($section -eq "server" -and $line -match "^(host|port|log_level|test_mode)\s*=\s*(.+)$") {
            $key = $Matches[1]
            $val = $Matches[2].Trim().Trim('"')
            $cfg[$key] = $val
        }
    }

    if ($cfg.hy_path -ne "") {
        if (-not ([System.IO.Path]::IsPathRooted($cfg.hy_path))) {
            $cfg.hy_path = Join-Path $ProjectDir $cfg.hy_path
        }
    }

    return $cfg
}

function Get-VenvDir([string]$hyPath) {
    return Join-Path $hyPath "venv"
}

function Get-UvicornCmd([string]$venvDir) {
    $uvicorn = Join-Path $venvDir "Scripts\uvicorn.exe"
    if (Test-Path $uvicorn) {
        return $uvicorn
    }
    return "python"
}

function Start-App {
    $cfg = Read-Config
    if ([string]::IsNullOrWhiteSpace($cfg.hy_path)) {
        throw "无法从 config.toml 读取 hy_motion.path"
    }

    $venvDir = Get-VenvDir $cfg.hy_path
    $uvicornCmd = Get-UvicornCmd $venvDir
    $appArgs = @(
        "src.hy_motion_api.main:app",
        "--app-dir", $ProjectDir,
        "--host", $cfg.host,
        "--port", $cfg.port
    )
    if ($cfg.log_level -ne "") {
        $appArgs += @("--log-level", $cfg.log_level)
    }

    Write-Host "启动服务..."
    schtasks /query /tn $ServiceName | Out-Null
    if ($LASTEXITCODE -eq 0) {
        schtasks /run /tn $ServiceName | Out-Null
        return
    }

    Write-Host "服务未注册，直接启动..."
    if ($uvicornCmd -eq "python") {
        Start-Process -NoNewWindow -FilePath "python" -ArgumentList @("-m", "uvicorn") + $appArgs
    } else {
        Start-Process -NoNewWindow -FilePath $uvicornCmd -ArgumentList $appArgs
    }
}

function Install-Dependencies {
    $cfg = Read-Config
    if ([string]::IsNullOrWhiteSpace($cfg.hy_path)) {
        throw "无法从 config.toml 读取 hy_motion.path"
    }
    $venvDir = Get-VenvDir $cfg.hy_path
    if (-not (Test-Path $venvDir)) {
        throw "HY-Motion-1.0 虚拟环境不存在: $venvDir"
    }
    $pip = Join-Path $venvDir "Scripts\pip.exe"
    & $pip install -r (Join-Path $ProjectDir "requirements.txt")
}

function Enable-Service {
    $cfg = Read-Config
    if ([string]::IsNullOrWhiteSpace($cfg.hy_path)) {
        throw "无法从 config.toml 读取 hy_motion.path"
    }
    $venvDir = Get-VenvDir $cfg.hy_path
    if (-not (Test-Path $venvDir)) {
        throw "HY-Motion-1.0 虚拟环境不存在: $venvDir"
    }

    $uvicornCmd = Join-Path $venvDir "Scripts\uvicorn.exe"
    $appCmd = "src.hy_motion_api.main:app --app-dir `"$ProjectDir`" --host $($cfg.host) --port $($cfg.port)"
    if ($cfg.log_level -ne "") {
        $appCmd += " --log-level $($cfg.log_level)"
    }

    schtasks /create /tn $ServiceName /tr "`"$uvicornCmd`" $appCmd" /sc onlogon /rl limited /f | Out-Null
    Write-Host "已开启开机自启"
}

function Disable-Service {
    schtasks /delete /tn $ServiceName /f 2>$null | Out-Null
    Write-Host "已关闭开机自启"
}

function Stop-ServiceTask {
    schtasks /end /tn $ServiceName 2>$null | Out-Null
}

function Restart-ServiceTask {
    schtasks /end /tn $ServiceName 2>$null | Out-Null
    schtasks /run /tn $ServiceName 2>$null | Out-Null
    Write-Host "服务已重启"
}

function Reload-ServiceTask {
    schtasks /end /tn $ServiceName 2>$null | Out-Null
    schtasks /run /tn $ServiceName 2>$null | Out-Null
    Write-Host "配置已重载"
}

Write-Host "HY-Motion API 服务管理脚本"
Write-Host "============================="
Write-Host ""

if (-not $args -or $args.Count -eq 0) {
    Show-Help
    exit 0
}

switch ($args[0]) {
    "help" { Show-Help }
    "-h" { Show-Help }
    "--help" { Show-Help }
    "install" { Install-Dependencies }
    "enable" { Enable-Service }
    "disable" { Disable-Service }
    "start" { Start-App }
    "stop" { Stop-ServiceTask }
    "restart" { Restart-ServiceTask }
    "reload" { Reload-ServiceTask }
    default { Show-Help }
}
