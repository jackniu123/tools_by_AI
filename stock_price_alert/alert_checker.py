# -*- coding: utf-8 -*-
"""
股价提醒检查模块，独立于UI运行。
提供 start_checker() 函数启动后台定时检查（每5分钟）。
配置文件路径：C:/Users/Administrator/stock_price_alert/alerts_config.json
"""
import time
import threading
import json
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import schedule
import akshare as ak
import pandas as pd
import tkinter as tk
from tkinter import messagebox

# ==================== 日志配置 ====================
LOG_DIR = r"C:\Users\Administrator\stock_price_alert"
LOG_FILE = os.path.join(LOG_DIR, "alert_checker.log")

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==================== 全局变量 ====================
CONFIG_DIR = r"C:\Users\Administrator\stock_price_alert"
CONFIG_FILE = os.path.join(CONFIG_DIR, "alerts_config.json")
PRICE_ALERTS = {}  # 格式: {symbol: {"name": str, "high": float, "low": float}}
VOLATILITY_ALERTS = {}  # 格式: {symbol: {"name": str, "threshold": float}}
last_prices = {}  # 存储上一次价格，用于波动计算
_market_cache = {}  # 市场数据缓存

# 今日屏蔽记录
_blocked_today = set()          # 存储当天已屏蔽的提醒键
_blocked_date = datetime.now().date()  # 记录当前日期，用于每天重置
_blocked_lock = threading.Lock()       # 保护屏蔽集合的线程锁


# ==================== 配置加载 ====================
def load_config():
    """从配置文件加载提醒设置到全局变量"""
    global PRICE_ALERTS, VOLATILITY_ALERTS
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 到价提醒
            price_list = data.get('price_alerts', [])
            new_price = {}
            for item in price_list:
                symbol = item.get('symbol')
                if not symbol:
                    continue
                symbol = str(symbol)
                name = item.get('name', '')
                thresholds = {}
                if item.get('high') is not None:
                    thresholds['high'] = float(item['high'])
                if item.get('low') is not None:
                    thresholds['low'] = float(item['low'])
                if thresholds:
                    new_price[symbol] = {'name': name, **thresholds}
            PRICE_ALERTS = new_price

            # 波动提醒
            vol_list = data.get('volatility_alerts', [])
            new_vol = {}
            for item in vol_list:
                symbol = item.get('symbol')
                if not symbol:
                    continue
                symbol = str(symbol)
                name = item.get('name', '')
                threshold = item.get('threshold')
                if threshold is not None:
                    new_vol[symbol] = {'name': name, 'threshold': float(threshold)}
            VOLATILITY_ALERTS = new_vol

            logger.info(f"重新加载配置：到价提醒 {len(PRICE_ALERTS)} 条，波动提醒 {len(VOLATILITY_ALERTS)} 条")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    else:
        PRICE_ALERTS = {}
        VOLATILITY_ALERTS = {}
        logger.info("配置文件不存在，使用空配置")


def save_config():
    """保存配置到JSON文件（供UI调用，检查器中也可保留）"""
    price_list = []
    for symbol, info in PRICE_ALERTS.items():
        item = {'symbol': str(symbol), 'name': info.get('name', '')}
        if 'high' in info:
            item['high'] = info['high']
        if 'low' in info:
            item['low'] = info['low']
        price_list.append(item)

    vol_list = []
    for symbol, info in VOLATILITY_ALERTS.items():
        vol_list.append({
            'symbol': str(symbol),
            'name': info.get('name', ''),
            'threshold': info['threshold']
        })

    data = {
        'price_alerts': price_list,
        'volatility_alerts': vol_list
    }
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"配置已保存到 {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")


# ==================== 数据获取与缓存 ====================
def get_market_data(market):
    """获取指定市场的全市场实时行情数据，使用缓存（5分钟有效期）"""
    global _market_cache
    now = datetime.now()
    if market in _market_cache:
        cache_entry = _market_cache[market]
        if now - cache_entry['timestamp'] < timedelta(minutes=5):
            logger.debug(f"缓存命中 {market} 市场数据")
            return cache_entry['data']
        else:
            logger.debug(f"{market} 市场数据缓存过期")

    logger.info(f"正在请求 {market} 市场数据...")
    try:
        if market == 'A':
            df = ak.stock_zh_a_spot()
        elif market == 'HK':
            df = ak.stock_hk_spot()
        elif market == 'US':
            df = ak.stock_us_spot()
        else:
            logger.error(f"未知市场类型: {market}")
            return None
        _market_cache[market] = {'data': df, 'timestamp': now}
        logger.info(f"{market} 市场数据获取成功，行数: {len(df)}")
        return df
    except Exception as e:
        logger.error(f"获取 {market} 市场数据失败: {e}")
        if market in _market_cache:
            logger.warning(f"使用过期缓存 {market} 市场数据")
            return _market_cache[market]['data']
        return None


def get_stock_price(symbol):
    """
    从缓存的市场数据中提取股票实时价格
    规则：
      - 以 .HK 结尾 -> 港股
      - 以 .US 结尾 -> 美股
      - 否则视为A股（必须为6位数字代码）
    """
    try:
        if symbol.endswith('.HK'):
            market = 'HK'
            code = symbol.replace('.HK', '').zfill(5)
            df = get_market_data(market)
            if df is None:
                return None
            row = df[df['代码'] == code]
            if not row.empty:
                price = float(row['最新价'].iloc[0])
                logger.debug(f"提取 {symbol} 价格成功: {price}")
                return price
            else:
                logger.warning(f"未找到港股代码 {code}")
                return None
        elif symbol.endswith('.US'):
            market = 'US'
            code = symbol.replace('.US', '')
            df = get_market_data(market)
            if df is None:
                return None
            # 尝试不同列名
            if 'symbol' in df.columns:
                row = df[df['symbol'] == code]
            elif '代码' in df.columns:
                row = df[df['代码'] == code]
            else:
                logger.error(f"美股数据无合适列名: {df.columns.tolist()}")
                return None
            if not row.empty:
                if '最新价' in row.columns:
                    price = float(row['最新价'].iloc[0])
                elif 'price' in row.columns:
                    price = float(row['price'].iloc[0])
                else:
                    logger.error(f"美股数据无价格列: {row.columns.tolist()}")
                    return None
                logger.debug(f"提取 {symbol} 价格成功: {price}")
                return price
            else:
                logger.warning(f"未找到美股代码 {code}")
                return None
        else:
            # A股
            market = 'A'
            code = symbol
            df = get_market_data(market)
            if df is None:
                return None
            row = df[df['代码'].str[2:] == code]
            if not row.empty:
                price = float(row['最新价'].iloc[0])
                logger.debug(f"提取 {symbol} 价格成功: {price}")
                return price
            else:
                logger.warning(f"未找到A股代码 {code}")
                return None
    except Exception as e:
        logger.error(f"提取 {symbol} 价格失败: {e}")
        return None


def get_top_losers(market):
    """从缓存的市场数据中获取跌幅超过90%的股票列表"""
    losers = []
    try:
        df = get_market_data(market)
        if df is None:
            return losers
        if market == 'HK':
            if '涨跌幅' in df.columns:
                df_filtered = df[df['涨跌幅'] <= -90]
                for _, row in df_filtered.iterrows():
                    losers.append((row['代码'], row['涨跌幅']))
                logger.info(f"港股跌幅榜筛选出 {len(losers)} 只跌幅>90%股票")
            else:
                logger.error(f"港股数据无涨跌幅列: {df.columns.tolist()}")
        elif market == 'US':
            pct_col = '涨跌幅' if '涨跌幅' in df.columns else 'percent'
            if pct_col in df.columns:
                df_filtered = df[df[pct_col] <= -90]
                for _, row in df_filtered.iterrows():
                    losers.append((row['symbol'], row[pct_col]))
                logger.info(f"美股跌幅榜筛选出 {len(losers)} 只跌幅>90%股票")
            else:
                logger.error(f"美股数据无涨跌幅列: {df.columns.tolist()}")
    except Exception as e:
        logger.error(f"获取 {market} 跌幅榜失败: {e}")
    return losers


# ==================== 交易时间判断 ====================
def get_current_time():
    return datetime.now()


def is_a_trading_time(dt=None):
    """判断给定时间（北京时间）是否在A股交易时间内。A股交易时间：上午 9:30-11:30，下午 13:00-15:00"""
    if dt is None:
        dt = get_current_time()
    if dt.weekday() >= 5:  # 周六周日
        return False
    morning_start = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    morning_end = dt.replace(hour=11, minute=30, second=0, microsecond=0)
    afternoon_start = dt.replace(hour=13, minute=0, second=0, microsecond=0)
    afternoon_end = dt.replace(hour=15, minute=0, second=0, microsecond=0)
    return (morning_start <= dt <= morning_end) or (afternoon_start <= dt <= afternoon_end)


def is_hk_trading_time(dt=None):
    """判断给定时间（北京时间）是否在港股交易时间内"""
    if dt is None:
        dt = get_current_time()
    if dt.weekday() >= 5:
        return False
    morning_start = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    morning_end = dt.replace(hour=12, minute=0, second=0, microsecond=0)
    afternoon_start = dt.replace(hour=13, minute=0, second=0, microsecond=0)
    afternoon_end = dt.replace(hour=16, minute=0, second=0, microsecond=0)
    return (morning_start <= dt <= morning_end) or (afternoon_start <= dt <= afternoon_end)


def is_us_trading_time(dt=None):
    """判断给定时间（北京时间）是否在美股交易时间内（简化的夏令时判断）"""
    if dt is None:
        dt = get_current_time()
    if dt.weekday() >= 5:
        return False
    year = dt.year
    dst_start = datetime(year, 3, 8)
    dst_end = datetime(year, 11, 1)
    while dst_start.weekday() != 6:
        dst_start = dst_start.replace(day=dst_start.day + 1)
    while dst_end.weekday() != 6:
        dst_end = dst_end.replace(day=dst_end.day + 1)
    is_dst = dst_start <= dt <= dst_end

    if is_dst:
        us_open = dt.replace(hour=21, minute=30, second=0, microsecond=0)
        us_close = (dt + timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
    else:
        us_open = dt.replace(hour=22, minute=30, second=0, microsecond=0)
        us_close = (dt + timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0)

    return us_open <= dt <= us_close


# ==================== 弹窗提醒（支持今日不再提醒）====================
def show_alert(message, key):
    """
    显示自定义提醒弹窗，包含“今日不再提醒”按钮。
    :param message: 要显示的消息文本
    :param key: 唯一标识该提醒的键，用于日内屏蔽
    """
    global _blocked_today, _blocked_date, _blocked_lock

    # 检查当前日期，若已过午夜则清空屏蔽记录
    with _blocked_lock:
        today = datetime.now().date()
        if today != _blocked_date:
            _blocked_today.clear()
            _blocked_date = today
            logger.info("日期变化，清空今日屏蔽记录")

        if key in _blocked_today:
            logger.info(f"提醒已被用户屏蔽今日不再弹: {key}")
            return

    logger.info(f"触发弹窗提醒 (key={key}): {message}")

    def _alert():
        # 在子线程中创建弹窗
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        top = tk.Toplevel(root)
        top.title("股价提醒")
        top.geometry("400x150")
        top.attributes('-topmost', True)  # 置顶
        top.focus_force()  # 获取焦点

        # 消息标签
        msg_label = tk.Label(top, text=message, wraplength=380, justify='left')
        msg_label.pack(pady=10, padx=10)

        # 按钮框架
        btn_frame = tk.Frame(top)
        btn_frame.pack(pady=10)

        def on_close():
            top.destroy()
            root.destroy()

        def on_snooze():
            # 用户选择“今日不再提醒”，将该键加入屏蔽集合
            with _blocked_lock:
                _blocked_today.add(key)
                logger.info(f"用户屏蔽今日提醒: {key}")
            top.destroy()
            root.destroy()

        btn_close = tk.Button(btn_frame, text="关闭", command=on_close, width=12)
        btn_close.pack(side=tk.LEFT, padx=5)

        btn_snooze = tk.Button(btn_frame, text="今日不再提醒", command=on_snooze, width=15)
        btn_snooze.pack(side=tk.LEFT, padx=5)

        top.protocol("WM_DELETE_WINDOW", on_close)  # 点击X时也执行关闭

        root.mainloop()

    threading.Thread(target=_alert, daemon=True).start()


# ==================== 提醒检查函数 ====================
def check_price_alerts():
    """检查到价提醒"""
    global last_prices
    alerts = PRICE_ALERTS.copy()
    if not alerts:
        logger.debug("到价提醒列表为空，跳过")
        return
    logger.info(f"开始检查到价提醒，监控 {len(alerts)} 只股票")

    # 按市场分组
    market_groups = {'A': [], 'HK': [], 'US': []}
    for symbol in alerts.keys():
        if symbol.endswith('.HK'):
            market_groups['HK'].append(symbol)
        elif symbol.endswith('.US'):
            market_groups['US'].append(symbol)
        else:
            market_groups['A'].append(symbol)

    now = get_current_time()
    for market, symbols in market_groups.items():
        if not symbols:
            continue

        # 判断交易时间
        if market == 'A' and not is_a_trading_time(now):
            logger.info(f"A股非交易时间，跳过该市场 {len(symbols)} 只股票的到价检查")
            continue
        if market == 'HK' and not is_hk_trading_time(now):
            logger.info(f"港股非交易时间，跳过该市场 {len(symbols)} 只股票的到价检查")
            continue
        if market == 'US' and not is_us_trading_time(now):
            logger.info(f"美股非交易时间，跳过该市场 {len(symbols)} 只股票的到价检查")
            continue

        # 获取该市场数据
        df = get_market_data(market)
        if df is None:
            logger.warning(f"获取{market}市场数据失败，跳过该市场股票检查")
            continue

        # 对该市场中的每只股票进行检查
        for symbol in symbols:
            price = get_stock_price(symbol)
            if price is None:
                logger.warning(f"{symbol} 价格获取失败，跳过")
                continue
            logger.debug(f"{symbol} 当前价: {price}")
            last_prices[symbol] = price
            thresholds = alerts[symbol]
            name = thresholds.get('name', '')

            # --- 新增日志：打印目标价格和当前价格（无论是否触发） ---
            high = thresholds.get('high')
            low = thresholds.get('low')
            log_msg = f"股票 {symbol} ({name}) 当前价格: {price}"
            if high is not None:
                log_msg += f", 高阈值: {high}"
            if low is not None:
                log_msg += f", 低阈值: {low}"
            logger.info(log_msg)

            if high is not None and price >= high:
                logger.info(f"{symbol} 触发高阈值提醒: {price} >= {high}")
                key = f"price_high:{symbol}:{high}"
                show_alert(f"到价提醒：{symbol} 当前价 {price} >= 目标高 {high}", key)
            if low is not None and price <= low:
                logger.info(f"{symbol} 触发低阈值提醒: {price} <= {low}")
                key = f"price_low:{symbol}:{low}"
                show_alert(f"到价提醒：{symbol} 当前价 {price} <= 目标低 {low}", key)
    logger.info("到价提醒检查完成")


def check_volatility_alerts():
    """
    检查波动提醒
    监控范围：所有到价提醒的股票 + 所有波动提醒中独立配置的股票
    波动阈值优先使用波动提醒中的设置，若不存在则使用默认 9%
    """
    global last_prices
    # 合并股票列表（去重）
    all_symbols = set(PRICE_ALERTS.keys()) | set(VOLATILITY_ALERTS.keys())
    if not all_symbols:
        logger.debug("波动提醒监控列表为空，跳过")
        return
    logger.info(f"开始检查波动提醒，监控 {len(all_symbols)} 只股票")

    # 按市场分组
    market_groups = {'A': [], 'HK': [], 'US': []}
    for symbol in all_symbols:
        if symbol.endswith('.HK'):
            market_groups['HK'].append(symbol)
        elif symbol.endswith('.US'):
            market_groups['US'].append(symbol)
        else:
            market_groups['A'].append(symbol)

    now = get_current_time()
    for market, symbols in market_groups.items():
        if not symbols:
            continue

        # 交易时间判断
        if market == 'A' and not is_a_trading_time(now):
            logger.info(f"A股非交易时间，跳过该市场 {len(symbols)} 只股票的波动检查")
            continue
        if market == 'HK' and not is_hk_trading_time(now):
            logger.info(f"港股非交易时间，跳过该市场 {len(symbols)} 只股票的波动检查")
            continue
        if market == 'US' and not is_us_trading_time(now):
            logger.info(f"美股非交易时间，跳过该市场 {len(symbols)} 只股票的波动检查")
            continue

        df = get_market_data(market)
        if df is None:
            logger.warning(f"获取{market}市场数据失败，跳过该市场股票检查")
            continue

        for symbol in symbols:
            current = get_stock_price(symbol)
            if current is None:
                logger.warning(f"{symbol} 价格获取失败，跳过")
                continue
            previous = last_prices.get(symbol)
            if previous is not None:
                change_pct = (current - previous) / previous * 100

                # 确定阈值：优先使用波动提醒独立配置，否则默认 9%
                if symbol in VOLATILITY_ALERTS:
                    threshold = VOLATILITY_ALERTS[symbol]['threshold']
                else:
                    threshold = 9.0  # 默认阈值

                logger.debug(f"{symbol} 当前 {current}，上次 {previous}，变化 {change_pct:.2f}% (阈值 {threshold}%)")
                if abs(change_pct) >= threshold:
                    direction = "上涨" if change_pct > 0 else "下跌"
                    logger.info(f"{symbol} 触发波动提醒: 变化 {abs(change_pct):.2f}% >= {threshold}%")
                    key = f"volatility:{symbol}"
                    show_alert(
                        f"波动提醒：{symbol} 当前价 {current}，较上次 {previous} {direction} {abs(change_pct):.2f}%",
                        key)
            last_prices[symbol] = current
    logger.info("波动提醒检查完成")


def check_daily_losers():
    """检查跌幅榜提醒"""
    now = get_current_time()
    logger.info("开始检查跌幅榜提醒")
    if is_hk_trading_time(now):
        losers_hk = get_top_losers('HK')
        for sym, pct in losers_hk:
            logger.info(f"港股跌幅榜触发提醒: {sym} 跌幅 {pct}%")
            key = f"loser:HK:{sym}"
            show_alert(f"港股跌幅榜提醒：{sym} 跌幅 {pct}% (超过90%)", key)
    if is_us_trading_time(now):
        losers_us = get_top_losers('US')
        for sym, pct in losers_us:
            logger.info(f"美股跌幅榜触发提醒: {sym} 跌幅 {pct}%")
            key = f"loser:US:{sym}"
            show_alert(f"美股跌幅榜提醒：{sym} 跌幅 {pct}% (超过90%)", key)
    logger.info("跌幅榜提醒检查完成")


def is_trading_day(dt=None):
    """判断给定时间（北京时间）是否为交易日（仅跳过周末）"""
    if dt is None:
        dt = get_current_time()
    return dt.weekday() < 5

def job():
    """定时任务：重新加载配置后执行检查"""
    if not is_trading_day():
        logger.info("今天是非交易日，跳过所有检查")
        return
    logger.info("========== 开始执行定时任务 ==========")
    load_config()  # 每次运行前重新加载配置，确保最新设置
    check_price_alerts()
    check_volatility_alerts()
    check_daily_losers()
    logger.info("========== 定时任务执行完成 ==========")


# ==================== 启动控制 ====================
_checker_thread = None
_stop_event = threading.Event()


def _run_schedule():
    """在单独线程中运行 schedule 循环"""
    schedule.every(5).minutes.do(job)
    # 立即执行一次，便于启动后快速检查
    job()
    while not _stop_event.is_set():
        schedule.run_pending()
        time.sleep(1)
    logger.info("检查器线程停止")


def start_checker():
    """启动后台提醒检查线程（如果未启动）"""
    global _checker_thread, _stop_event
    if _checker_thread is not None and _checker_thread.is_alive():
        logger.warning("检查器已在运行")
        return
    _stop_event.clear()
    _checker_thread = threading.Thread(target=_run_schedule, daemon=True)
    _checker_thread.start()
    logger.info("后台检查器已启动")


def stop_checker():
    """停止后台提醒检查线程"""
    global _stop_event
    _stop_event.set()
    logger.info("发送停止信号，等待检查器线程结束...")
    # 线程会在下一次 sleep 后退出


# 如果直接运行此模块，启动检查器（便于独立测试）
if __name__ == "__main__":
    start_checker()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_checker()