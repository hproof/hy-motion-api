#!/bin/bash
# HY-Motion API 服务管理脚本

set -e

SERVICE_NAME="hy-motion-api"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
CONFIG_FILE="${PROJECT_DIR}/config.toml"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 从 config.toml 读取 HY_MOTION_PATH
get_hy_motion_path() {
    if [[ -f "$CONFIG_FILE" ]]; then
        grep "^path" "$CONFIG_FILE" | head -1 | sed 's/path = "//' | sed 's/"//' | tr -d ' '
    fi
}

get_venv_dir() {
    local hy_path="$1"
    echo "${hy_path}/.venv"
}

get_uvicorn_bin() {
    local venv_dir="$1"
    echo "${venv_dir}/bin/uvicorn"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "请使用 sudo 运行此脚本"
        exit 1
    fi
}

check_systemd() {
    if ! command -v systemctl &> /dev/null; then
        error "systemd 不可用"
        exit 1
    fi
}

# 安装 Python 依赖
install() {
    local hy_path=$(get_hy_motion_path)
    local venv_dir=$(get_venv_dir "$hy_path")

    if [[ -z "$hy_path" ]]; then
        error "无法从 config.toml 读取 hy_motion.path"
        exit 1
    fi

    if [[ ! -d "$venv_dir" ]]; then
        error "HY-Motion-1.0 虚拟环境不存在: $venv_dir"
        exit 1
    fi

    info "使用 HY-Motion-1.0 虚拟环境: $venv_dir"
    info "安装 Python 依赖到 HY-Motion-1.0..."
    "$venv_dir/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"
    info "安装完成"
}

# 初始化 systemd 服务（开机自启）
enable() {
    check_root
    check_systemd

    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "config.toml 不存在，请先配置"
        exit 1
    fi

    local hy_path=$(get_hy_motion_path)
    local venv_dir=$(get_venv_dir "$hy_path")
    local uvicorn_bin=$(get_uvicorn_bin "$venv_dir")

    if [[ -z "$hy_path" ]]; then
        error "无法从 config.toml 读取 hy_motion.path"
        exit 1
    fi

    if [[ ! -d "$venv_dir" ]]; then
        error "HY-Motion-1.0 虚拟环境不存在: $venv_dir"
        exit 1
    fi

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=HY-Motion API
After=network.target

[Service]
Type=simple
User=${SUDO_USER:-$(whoami)}
WorkingDirectory=${PROJECT_DIR}
Environment="PYTHONPATH=${hy_path}"
ExecStart=${uvicorn_bin} src.hy_motion_api.main:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    info "已开启开机自启"
}

# 关闭开机自启
disable() {
    check_root
    check_systemd

    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        warn "服务正在运行，正在停止..."
        systemctl stop "$SERVICE_NAME"
    fi
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
    info "已关闭开机自启"
}

# 启动服务
start() {
    check_systemd
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        info "服务已在运行"
        return
    fi
    systemctl start "$SERVICE_NAME"
    info "服务已启动"
}

# 停止服务
stop() {
    check_systemd
    if ! systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        info "服务已停止"
        return
    fi
    systemctl stop "$SERVICE_NAME"
    info "服务已停止"
}

# 重启服务
restart() {
    check_systemd
    systemctl restart "$SERVICE_NAME"
    info "服务已重启"
}

# 重载配置
reload() {
    check_systemd
    systemctl restart "$SERVICE_NAME"
    info "配置已重载"
}

# 查看状态
status() {
    check_systemd
    systemctl status "$SERVICE_NAME" --no-pager
}

# 查看日志
logs() {
    check_systemd
    journalctl -u "$SERVICE_NAME" -f --no-pager
}

help() {
    echo "HY-Motion API 服务管理脚本"
    echo ""
    echo "用法: ./hy-motion.sh <command>"
    echo ""
    echo "Commands:"
    echo "  install   安装 Python 依赖 (到 HY-Motion-1.0 venv)"
    echo "  enable   开启开机自启 (需 root)"
    echo "  disable  关闭开机自启 (需 root)"
    echo "  start    启动服务"
    echo "  stop     停止服务"
    echo "  restart  重启服务"
    echo "  reload   重载配置"
    echo "  status   查看状态"
    echo "  logs     查看日志"
    echo "  help     显示帮助"
}

case "$1" in
    install)  install ;;
    enable)   enable ;;
    disable)  disable ;;
    start)    start ;;
    stop)     stop ;;
    restart)  restart ;;
    reload)   reload ;;
    status)   status ;;
    logs)     logs ;;
    help|--help|-h) help ;;
    *)        help ;;
esac
