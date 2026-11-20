@echo off
chcp 65001 > nul
echo [P2 快乐8服务] 正在停止端口 8000 服务...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a > nul 2>&1
    echo [P2 快乐8服务] 已终止进程 PID: %%a
)
echo [P2 快乐8服务] 停止操作完成。
