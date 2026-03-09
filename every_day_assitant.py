# -*- coding: utf-8 -*-
import threading
import time
import signal
import sys
import os
import winreg  # 用于操作 Windows 注册表
import stock_price_alert.alert_checker
import proxy_finder.proxy_finder
import new_stock_monitor.new_stock_monitor


def add_to_startup():
    """
    将当前程序添加到 Windows 开机启动项（使用 python.exe 以显示控制台）
    """
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as regkey:
            script_path = os.path.abspath(sys.argv[0])
            # 使用 python.exe 而不是 pythonw.exe，以便显示控制台窗口
            python_exe = sys.executable  # 通常是 python.exe 的路径
            command = f'"{python_exe}" "{script_path}"'
            winreg.SetValueEx(regkey, "EveryDayAssistant", 0, winreg.REG_SZ, command)
        print("已成功添加到开机启动项")
    except Exception as e:
        print(f"添加开机启动失败: {e}")


def create_desktop_shortcut():
    """
    在用户桌面上创建程序启动快捷方式（生成一个 .bat 文件）
    """
    try:
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        shortcut_name = "EveryDayAssistant.bat"
        shortcut_path = os.path.join(desktop, shortcut_name)

        # 获取 Python 解释器和脚本的绝对路径
        python_exe = sys.executable
        script_path = os.path.abspath(sys.argv[0])

        # 生成批处理文件内容
        # @echo off 可隐藏命令回显，如果不希望隐藏可以去掉
        bat_content = f'''@echo off
"{python_exe}" "{script_path}"
'''
        # 写入文件
        with open(shortcut_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)

        print(f"桌面快捷方式已创建: {shortcut_path}")
    except Exception as e:
        print(f"创建桌面快捷方式失败: {e}")


def run_proxy_finder():
    """在独立线程中运行代理查找程序"""
    try:
        proxy_finder.proxy_finder.main()
    except Exception as e:
        print(f"代理查找程序异常退出: {e}")


def run_new_stock_monitor():
    """在独立线程中运行新股监控程序"""
    try:
        new_stock_monitor.new_stock_monitor.main()
    except Exception as e:
        print(f"新股监控程序异常退出: {e}")


def run_price_alert_checker():
    """在独立线程中运行股价提醒检查器（该函数内部已创建独立线程）"""
    try:
        stock_price_alert.alert_checker.start_checker()
    except Exception as e:
        print(f"股价提醒检查器启动失败: {e}")


if __name__ == '__main__':
    # 添加开机启动
    add_to_startup()

    # 创建桌面快捷方式
    create_desktop_shortcut()

    # 创建并启动三个线程
    threads = []
    t1 = threading.Thread(target=run_proxy_finder, daemon=True)
    t2 = threading.Thread(target=run_new_stock_monitor, daemon=True)
    t3 = threading.Thread(target=run_price_alert_checker, daemon=True)

    threads.extend([t1, t2, t3])

    for t in threads:
        t.start()
        print(f"线程 {t.name} 已启动")

    print("所有服务已启动，按 Ctrl+C 停止...")


    # 定义信号处理函数，用于优雅退出
    def signal_handler(sig, frame):
        print("\n正在停止服务...")
        sys.exit(0)


    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 主线程保持运行，等待信号
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序终止")
        sys.exit(0)