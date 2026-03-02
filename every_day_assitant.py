# -*- coding: utf-8 -*-
import threading
import time
import signal
import sys

def run_proxy_finder():
    """在独立线程中运行代理查找程序"""
    try:
        import proxy_finder.proxy_finder
        # proxy_finder.proxy_finder.main()
    except Exception as e:
        print(f"代理查找程序异常退出: {e}")

def run_new_stock_monitor():
    """在独立线程中运行新股监控程序"""
    try:
        import new_stock_monitor.new_stock_monitor
        # new_stock_monitor.new_stock_monitor.main()
    except Exception as e:
        print(f"新股监控程序异常退出: {e}")

def run_price_alert_checker():
    """在独立线程中运行股价提醒检查器（该函数内部已创建独立线程）"""
    try:
        import stock_price_alert.alert_checker
        stock_price_alert.alert_checker.start_checker()
    except Exception as e:
        print(f"股价提醒检查器启动失败: {e}")

if __name__ == '__main__':
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

