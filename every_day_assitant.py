# -*- coding: utf-8 -*-
import threading
import sys

def run_proxy_finder():
    """运行 proxy_finder 模块的 main 函数"""
    try:
        import proxy_finder.proxy_finder
        proxy_finder.proxy_finder.main()
    except Exception as e:
        print(f"❌ proxy_finder 运行出错: {e}", file=sys.stderr)

def run_new_stock_monitor():
    """运行 new_stock_monitor 模块的 main 函数"""
    try:
        import new_stock_monitor.new_stock_monitor
        new_stock_monitor.new_stock_monitor.main()
    except Exception as e:
        print(f"❌ new_stock_monitor 运行出错: {e}", file=sys.stderr)

# if __name__ == '__main__':
#     # 创建两个线程
#     t1 = threading.Thread(target=run_proxy_finder)
#     t2 = threading.Thread(target=run_new_stock_monitor)
#
#     # 启动线程
#     t1.start()
#     t2.start()
#
#     # 等待两个线程执行完毕
#     t1.join()
#     t2.join()
#
#     print("✅ 所有任务执行完成")

if __name__ == '__main__':
    import proxy_finder.proxy_finder
    proxy_finder.proxy_finder.main()
    import new_stock_monitor.new_stock_monitor
    new_stock_monitor.new_stock_monitor.main()
