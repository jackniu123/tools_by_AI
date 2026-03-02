# -*- coding: utf-8 -*-
"""
股价提醒设置界面，独立于检查逻辑。
通过配置文件与 alert_checker 共享数据。
波动提醒与到价提醒独立配置，但波动提醒默认包含到价提醒的股票（UI上可单独管理）。
配置文件路径：C:/Users/Administrator/stock_price_alert/alerts_config.json
"""
import time
import threading
import json
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import akshare as ak
import pandas as pd
import alert_checker  # 导入检查模块，用于启动后台服务

# ==================== 日志配置 ====================
LOG_DIR = r"C:\Users\Administrator\stock_price_alert"
LOG_FILE = os.path.join(LOG_DIR, "ui.log")

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==================== 全局变量 ====================
CONFIG_DIR = r"C:\Users\Administrator\stock_price_alert"
CONFIG_FILE = os.path.join(CONFIG_DIR, "alerts_config.json")
PRICE_ALERTS = {}      # 格式: {symbol: {"name": str, "high": float, "low": float}}
VOLATILITY_ALERTS = {} # 格式: {symbol: {"name": str, "threshold": float}}
_market_cache = {}     # 市场数据缓存，用于名称查询

# ==================== 市场数据缓存（用于名称查询）====================
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

def get_stock_name(symbol):
    """
    根据股票代码获取股票名称（从缓存的市场数据中提取）
    返回名称字符串，若失败返回空字符串
    """
    try:
        if symbol.endswith('.HK'):
            market = 'HK'
            code = symbol.replace('.HK', '').zfill(5)
            df = get_market_data(market)
            if df is None:
                return ""
            # 港股名称列可能是 '名称' 或 'name'
            name_col = '名称' if '名称' in df.columns else 'name'
            row = df[df['代码'] == code]
            if not row.empty:
                return str(row[name_col].iloc[0])
        elif symbol.endswith('.US'):
            market = 'US'
            code = symbol.replace('.US', '')
            df = get_market_data(market)
            if df is None:
                return ""
            # 美股名称列可能是 '名称' 或 'name'
            if '名称' in df.columns:
                name_col = '名称'
                # 美股通常有 'symbol' 列
                row = df[df['symbol'] == code] if 'symbol' in df.columns else None
            else:
                name_col = 'name'
                row = df[df['symbol'] == code] if 'symbol' in df.columns else None
            if row is not None and not row.empty:
                return str(row[name_col].iloc[0])
        else:
            # A股
            market = 'A'
            code = symbol
            df = get_market_data(market)
            if df is None:
                return ""
            # A股名称列可能是 '名称' 或 'name'
            name_col = '名称' if '名称' in df.columns else 'name'
            row = df[df['代码'] == code]
            if not row.empty:
                return str(row[name_col].iloc[0])
    except Exception as e:
        logger.error(f"获取 {symbol} 名称失败: {e}")
    return ""

# ==================== 配置加载/保存 ====================
def load_config():
    """从JSON文件加载配置到UI全局变量"""
    global PRICE_ALERTS, VOLATILITY_ALERTS
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 到价提醒
            price_list = data.get('price_alerts', [])
            PRICE_ALERTS = {}
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
                    PRICE_ALERTS[symbol] = {'name': name, **thresholds}
            # 波动提醒
            vol_list = data.get('volatility_alerts', [])
            VOLATILITY_ALERTS = {}
            for item in vol_list:
                symbol = item.get('symbol')
                if not symbol:
                    continue
                symbol = str(symbol)
                name = item.get('name', '')
                threshold = item.get('threshold')
                if threshold is not None:
                    VOLATILITY_ALERTS[symbol] = {'name': name, 'threshold': float(threshold)}
            logger.info(f"从 {CONFIG_FILE} 加载配置：到价 {len(PRICE_ALERTS)} 条，波动 {len(VOLATILITY_ALERTS)} 条")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    else:
        PRICE_ALERTS = {}
        VOLATILITY_ALERTS = {}
        logger.info("配置文件不存在，使用默认空配置")

def save_config():
    """将UI全局变量保存到JSON文件"""
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

# ==================== UI界面 ====================
class AlertSettingsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("股价提醒设置")
        self.root.geometry("900x550")  # 适当加宽

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # 到价提醒选项卡
        self.price_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.price_frame, text="到价提醒")
        self.create_price_tab()

        # 波动提醒选项卡
        self.vol_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.vol_frame, text="波动提醒")
        self.create_vol_tab()

        # 底部按钮
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="刷新显示", command=self.refresh_displays).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="保存配置", command=self.save_and_refresh).pack(side='left', padx=5)

        # 初始化显示
        load_config()
        self.refresh_displays()

        # 启动后台检查器
        alert_checker.start_checker()

    # ---------- 到价提醒选项卡 ----------
    def create_price_tab(self):
        columns = ('symbol', 'name', 'high', 'low')
        self.price_tree = ttk.Treeview(self.price_frame, columns=columns, show='headings')
        self.price_tree.heading('symbol', text='股票代码')
        self.price_tree.heading('name', text='股票名称')
        self.price_tree.heading('high', text='高阈值')
        self.price_tree.heading('low', text='低阈值')
        self.price_tree.column('symbol', width=120)
        self.price_tree.column('name', width=180)
        self.price_tree.column('high', width=100)
        self.price_tree.column('low', width=100)
        self.price_tree.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(self.price_frame, orient='vertical', command=self.price_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.price_tree.configure(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(self.price_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="添加", command=self.add_price_alert).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="编辑", command=self.edit_price_alert).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="删除", command=self.delete_price_alert).pack(side='left', padx=5)

    def add_price_alert(self):
        dialog = PriceAlertDialog(self.root, title="添加到价提醒")
        if dialog.result:
            symbol, name, high, low = dialog.result
            if symbol in PRICE_ALERTS:
                messagebox.showerror("错误", "该股票已存在到价提醒")
                return
            info = {'name': name}
            if high is not None:
                info['high'] = high
            if low is not None:
                info['low'] = low
            PRICE_ALERTS[symbol] = info
            self.save_and_refresh()
            logger.info(f"UI添加到价提醒: {symbol} {name} high={high} low={low}")

    def edit_price_alert(self):
        selected = self.price_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要编辑的条目")
            return
        item = self.price_tree.item(selected[0])
        symbol = str(item['values'][0])
        current = PRICE_ALERTS.get(symbol, {})
        name = current.get('name', '')
        high = current.get('high')
        low = current.get('low')
        dialog = PriceAlertDialog(self.root, title="编辑到价提醒", symbol=symbol, name=name, high=high, low=low)
        if dialog.result:
            new_symbol, new_name, new_high, new_low = dialog.result
            if new_symbol != symbol:
                if new_symbol in PRICE_ALERTS:
                    messagebox.showerror("错误", "新股票代码已存在到价提醒")
                    return
                del PRICE_ALERTS[symbol]
            info = {'name': new_name}
            if new_high is not None:
                info['high'] = new_high
            if new_low is not None:
                info['low'] = new_low
            PRICE_ALERTS[new_symbol] = info
            self.save_and_refresh()
            logger.info(f"UI编辑到价提醒: {symbol} -> {new_symbol} {new_name} high={new_high} low={new_low}")

    def delete_price_alert(self):
        selected = self.price_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的条目")
            return
        if messagebox.askyesno("确认", "确定删除选中的到价提醒吗？"):
            for item in selected:
                symbol = str(self.price_tree.item(item)['values'][0])
                if symbol in PRICE_ALERTS:
                    del PRICE_ALERTS[symbol]
                    logger.info(f"UI删除到价提醒: {symbol}")
            self.save_and_refresh()

    # ---------- 波动提醒选项卡 ----------
    def create_vol_tab(self):
        # 说明标签
        info_label = ttk.Label(self.vol_frame, text="波动提醒默认监控到价提醒中的所有股票（阈值9%），您也可在此独立添加其他股票并自定义阈值。", foreground='blue')
        info_label.pack(pady=5)

        columns = ('symbol', 'name', 'threshold')
        self.vol_tree = ttk.Treeview(self.vol_frame, columns=columns, show='headings')
        self.vol_tree.heading('symbol', text='股票代码')
        self.vol_tree.heading('name', text='股票名称')
        self.vol_tree.heading('threshold', text='波动阈值 (%)')
        self.vol_tree.column('symbol', width=120)
        self.vol_tree.column('name', width=200)
        self.vol_tree.column('threshold', width=100)
        self.vol_tree.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(self.vol_frame, orient='vertical', command=self.vol_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.vol_tree.configure(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(self.vol_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="添加", command=self.add_vol_alert).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="编辑", command=self.edit_vol_alert).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="删除", command=self.delete_vol_alert).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="从到价提醒同步", command=self.sync_from_price).pack(side='left', padx=5)

    def add_vol_alert(self):
        dialog = VolatilityAlertDialog(self.root, title="添加波动提醒")
        if dialog.result:
            symbol, name, threshold = dialog.result
            if symbol in VOLATILITY_ALERTS:
                messagebox.showerror("错误", "该股票已存在波动提醒")
                return
            VOLATILITY_ALERTS[symbol] = {'name': name, 'threshold': threshold}
            self.save_and_refresh()
            logger.info(f"UI添加波动提醒: {symbol} {name} threshold={threshold}%")

    def edit_vol_alert(self):
        selected = self.vol_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要编辑的条目")
            return
        item = self.vol_tree.item(selected[0])
        symbol = str(item['values'][0])
        current = VOLATILITY_ALERTS.get(symbol, {})
        name = current.get('name', '')
        threshold = current.get('threshold')
        dialog = VolatilityAlertDialog(self.root, title="编辑波动提醒", symbol=symbol, name=name, threshold=threshold)
        if dialog.result:
            new_symbol, new_name, new_threshold = dialog.result
            if new_symbol != symbol:
                if new_symbol in VOLATILITY_ALERTS:
                    messagebox.showerror("错误", "新股票代码已存在波动提醒")
                    return
                del VOLATILITY_ALERTS[symbol]
            VOLATILITY_ALERTS[new_symbol] = {'name': new_name, 'threshold': new_threshold}
            self.save_and_refresh()
            logger.info(f"UI编辑波动提醒: {symbol} -> {new_symbol} {new_name} threshold={new_threshold}%")

    def delete_vol_alert(self):
        selected = self.vol_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的条目")
            return
        if messagebox.askyesno("确认", "确定删除选中的波动提醒吗？"):
            for item in selected:
                symbol = str(self.vol_tree.item(item)['values'][0])
                if symbol in VOLATILITY_ALERTS:
                    del VOLATILITY_ALERTS[symbol]
                    logger.info(f"UI删除波动提醒: {symbol}")
            self.save_and_refresh()

    def sync_from_price(self):
        """将到价提醒中的所有股票添加到波动提醒（如果不存在），阈值设为9%"""
        added = 0
        for symbol, info in PRICE_ALERTS.items():
            if symbol not in VOLATILITY_ALERTS:
                VOLATILITY_ALERTS[symbol] = {'name': info.get('name', ''), 'threshold': 9.0}
                added += 1
        if added > 0:
            self.save_and_refresh()
            messagebox.showinfo("完成", f"已添加 {added} 条波动提醒（阈值9%）")
        else:
            messagebox.showinfo("提示", "所有到价提醒股票已存在于波动提醒中")

    # ---------- 通用 ----------
    def refresh_displays(self):
        """刷新两个列表显示"""
        # 刷新到价提醒
        for row in self.price_tree.get_children():
            self.price_tree.delete(row)
        for symbol, info in PRICE_ALERTS.items():
            name = info.get('name', '')
            high = info.get('high', '')
            low = info.get('low', '')
            self.price_tree.insert('', 'end', values=(symbol, name, high, low))

        # 刷新波动提醒
        for row in self.vol_tree.get_children():
            self.vol_tree.delete(row)
        for symbol, info in VOLATILITY_ALERTS.items():
            name = info.get('name', '')
            threshold = info.get('threshold', '')
            self.vol_tree.insert('', 'end', values=(symbol, name, threshold))

    def save_and_refresh(self):
        save_config()
        self.refresh_displays()

# 自定义对话框：到价提醒
class PriceAlertDialog(simpledialog.Dialog):
    def __init__(self, parent, title, symbol=None, name=None, high=None, low=None):
        self.symbol = str(symbol) if symbol is not None else None
        self.name = str(name) if name is not None else None
        self.high = high
        self.low = low
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="股票代码:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.symbol_entry = ttk.Entry(master, width=15)
        self.symbol_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        if self.symbol is not None:
            self.symbol_entry.insert(0, self.symbol)

        ttk.Button(master, text="查询名称", command=self.fetch_name).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(master, text="股票名称:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.name_entry = ttk.Entry(master, width=25)
        self.name_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky='w')
        if self.name is not None:
            self.name_entry.insert(0, self.name)

        ttk.Label(master, text="高阈值 (可选):").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.high_entry = ttk.Entry(master, width=15)
        self.high_entry.grid(row=2, column=1, padx=5, pady=5, sticky='w')
        if self.high is not None:
            self.high_entry.insert(0, str(self.high))

        ttk.Label(master, text="低阈值 (可选):").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.low_entry = ttk.Entry(master, width=15)
        self.low_entry.grid(row=3, column=1, padx=5, pady=5, sticky='w')
        if self.low is not None:
            self.low_entry.insert(0, str(self.low))

        hint = "格式：A股6位数字（如600519），港股加.HK（如00700.HK），美股加.US（如AAPL.US）"
        ttk.Label(master, text=hint, foreground='gray').grid(row=4, column=0, columnspan=3, pady=5)
        return self.symbol_entry

    def fetch_name(self):
        symbol = self.symbol_entry.get().strip()
        if not symbol:
            messagebox.showerror("错误", "请先输入股票代码")
            return
        def _fetch():
            name = get_stock_name(symbol)
            if name:
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, name)
            else:
                messagebox.showwarning("警告", f"未找到股票 {symbol} 的名称，请手动输入")
        threading.Thread(target=_fetch, daemon=True).start()

    def apply(self):
        symbol = self.symbol_entry.get().strip()
        if not symbol:
            messagebox.showerror("错误", "股票代码不能为空")
            return
        name = self.name_entry.get().strip()
        high_str = self.high_entry.get().strip()
        low_str = self.low_entry.get().strip()
        high = float(high_str) if high_str else None
        low = float(low_str) if low_str else None
        if high is None and low is None:
            messagebox.showerror("错误", "至少填写一个阈值")
            return
        self.result = (symbol, name, high, low)

# 自定义对话框：波动提醒
class VolatilityAlertDialog(simpledialog.Dialog):
    def __init__(self, parent, title, symbol=None, name=None, threshold=None):
        self.symbol = str(symbol) if symbol is not None else None
        self.name = str(name) if name is not None else None
        self.threshold = threshold
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="股票代码:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.symbol_entry = ttk.Entry(master, width=15)
        self.symbol_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        if self.symbol is not None:
            self.symbol_entry.insert(0, self.symbol)

        ttk.Button(master, text="查询名称", command=self.fetch_name).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(master, text="股票名称:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.name_entry = ttk.Entry(master, width=25)
        self.name_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky='w')
        if self.name is not None:
            self.name_entry.insert(0, self.name)

        ttk.Label(master, text="波动阈值 (%):").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.threshold_entry = ttk.Entry(master, width=15)
        self.threshold_entry.grid(row=2, column=1, padx=5, pady=5, sticky='w')
        if self.threshold is not None:
            self.threshold_entry.insert(0, str(self.threshold))

        hint = "格式：A股6位数字（如600519），港股加.HK（如00700.HK），美股加.US（如AAPL.US）"
        ttk.Label(master, text=hint, foreground='gray').grid(row=3, column=0, columnspan=3, pady=5)
        return self.symbol_entry

    def fetch_name(self):
        symbol = self.symbol_entry.get().strip()
        if not symbol:
            messagebox.showerror("错误", "请先输入股票代码")
            return
        def _fetch():
            name = get_stock_name(symbol)
            if name:
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, name)
            else:
                messagebox.showwarning("警告", f"未找到股票 {symbol} 的名称，请手动输入")
        threading.Thread(target=_fetch, daemon=True).start()

    def apply(self):
        symbol = self.symbol_entry.get().strip()
        if not symbol:
            messagebox.showerror("错误", "股票代码不能为空")
            return
        name = self.name_entry.get().strip()
        threshold_str = self.threshold_entry.get().strip()
        try:
            threshold = float(threshold_str)
        except ValueError:
            messagebox.showerror("错误", "阈值必须为数字")
            return
        self.result = (symbol, name, threshold)

# ==================== 主程序 ====================
def main():
    root = tk.Tk()
    app = AlertSettingsApp(root)
    logger.info("UI界面启动，后台检查器已运行")
    root.mainloop()

if __name__ == "__main__":
    main()