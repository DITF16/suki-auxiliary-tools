#!/bin/bash

# ================= 配置区域 =================
# 获取脚本所在目录，确保无论在哪里运行脚本，都能找到 app.py
BASE_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$BASE_DIR"

# 定义文件名
APP_NAME="app.py"
PID_FILE="run.pid"  # 用来存进程号
LOG_FILE="run.log"  # 用来存运行日志

# 如果你使用了虚拟环境，请取消下面这行的注释，并修改为你的环境路径
# source ./venv/Scripts/activate
# ===========================================

# --- 检查程序状态 ---
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 1 # 正在运行
        else
            return 0 # PID文件存在但进程没了（异常停止）
        fi
    else
        return 0 # 未运行
    fi
}

# --- 启动程序 ---
start_app() {
    check_status
    if [ $? -eq 1 ]; then
        PID=$(cat "$PID_FILE")
        echo "⚠️  程序已经在运行中 (PID: $PID)"
    else
        echo "🚀 正在启动 Streamlit..."
        # nohup: 后台运行
        # > $LOG_FILE: 把输出写入日志
        # 2>&1: 把报错也写入日志
        # &: 放入后台
        nohup streamlit run "$APP_NAME" > "$LOG_FILE" 2>&1 &
        
        # 获取刚才启动的进程号并保存
        echo $! > "$PID_FILE"
        echo "✅ 启动成功！日志文件: $LOG_FILE"
        echo "🌐 请访问浏览器查看应用。"
    fi
}

# --- 停止程序 ---
stop_app() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        echo "🛑 正在停止程序 (PID: $PID)..."
        kill "$PID"
        
        # 等待确认停止
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️  停止失败，尝试强制停止..."
            kill -9 "$PID"
        fi
        
        rm "$PID_FILE"
        echo "✅ 程序已终止。"
    else
        echo "⚠️  程序没有运行（找不到 PID 文件）。"
    fi
}

# --- 查看状态 ---
show_status() {
    check_status
    if [ $? -eq 1 ]; then
        PID=$(cat "$PID_FILE")
        echo "🟢 程序正在运行 (PID: $PID)"
        echo "--- 最新日志 (最后5行) ---"
        tail -n 5 "$LOG_FILE"
    else
        echo "⚪ 程序未运行"
    fi
}

# ================= 主菜单逻辑 =================
echo "=================================="
echo "   🍳 游戏配方助手 控制面板"
echo "=================================="
echo " 1. 启动程序 (Start)"
echo " 2. 停止程序 (Stop)"
echo " 3. 重启程序 (Restart)"
echo " 4. 查看状态 (Status)"
echo " 0. 退出 (Exit)"
echo "=================================="
read -p "请输入选项 [0-4]: " choice

case $choice in
    1)
        start_app
        ;;
    2)
        stop_app
        ;;
    3)
        stop_app
        sleep 1
        start_app
        ;;
    4)
        show_status
        ;;
    0)
        exit 0
        ;;
    *)
        echo "无效选项"
        ;;
esac