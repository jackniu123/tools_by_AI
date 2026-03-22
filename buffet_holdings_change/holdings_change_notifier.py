#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
伯克希尔持仓变动监控脚本
功能：定期获取伯克希尔·哈撒韦（BRK.B）最新的13F持仓报告，与上次缓存对比，
     若发现新增、清仓或持股变化超过1%，则通过弹窗通知用户（可配置）。
支持开机自启后台运行，日志自动轮转，配置文件分离。
"""

import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime
from tkinter import messagebox, Tk

from edgar import Company, set_identity

# 配置文件路径（与脚本同目录下的 config.json）
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# 默认配置（若配置文件缺失时使用）
DEFAULT_CONFIG = {
    "identity_email": "706495596@qq.com",  # 需用户自行修改
    "enable_notification": True,
    "log_dir": r"C:/Users/Administrator/._my_python_tools/holdings_change_notifier",
    "cache_file": "buffett_holdings_cache.json"
}


def load_config():
    """加载配置文件，若不存在则创建默认配置并提示"""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print(f"配置文件不存在，已创建默认配置：{CONFIG_FILE}")
        print("请修改其中的 identity_email 为您的邮箱后重新运行。")
        sys.exit(1)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    # 补充缺失的默认值
    for key, val in DEFAULT_CONFIG.items():
        config.setdefault(key, val)
    return config


def setup_logging(log_dir):
    """配置日志：同时输出到控制台和文件，文件轮转（单文件10MB，保留5个备份）"""
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "holdings_change.log")

    # 根日志器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除已有处理器（避免重复）
    if logger.hasHandlers():
        logger.handlers.clear()

    # 文件处理器（轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_cache_path(log_dir, cache_filename):
    """返回缓存文件的完整路径"""
    return os.path.join(log_dir, cache_filename)


def get_latest_holdings():
    """获取伯克希尔最新的13F持仓数据"""
    # 通过股票代码查找公司
    company = Company("BRK.B")
    # 获取最新的13F-HR文件
    filings = company.get_filings(form="13F-HR")
    latest_filing = filings.latest(1)

    if latest_filing is None:
        raise Exception("未找到13F文件")

    # 解析为13F报告对象
    report = latest_filing.obj()
    # 持仓数据（DataFrame）
    holdings_df = report.holdings

    # 转换为字典列表便于缓存
    holdings_list = []
    for _, row in holdings_df.iterrows():
        holdings_list.append({
            "cusip": row.get("Cusip", ""),
            "name": row.get("Issuer", ""),
            "ticker": row.get("Ticker", ""),
            "value": row.get("Value", 0),      # 单位：千美元
            "shares": row.get("SharesPrnAmount", 0)
        })

    return holdings_list, report.report_period


def load_cache(cache_path):
    """加载上次的持仓缓存"""
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache_path, holdings, report_period):
    """保存当前持仓到缓存"""
    cache_data = {
        "report_period": report_period,
        "holdings": {h["cusip"]: h for h in holdings}
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


def compare_holdings(old_cache, new_holdings):
    """
    对比新旧持仓，返回变化列表
    old_cache: {'report_period': '...', 'holdings': {cusip: {...}}}
    new_holdings: 列表格式
    """
    old_holdings = old_cache.get("holdings", {})
    new_dict = {h["cusip"]: h for h in new_holdings}

    changes = []
    old_cusips = set(old_holdings.keys())
    new_cusips = set(new_dict.keys())

    # 新增
    for cusip in new_cusips - old_cusips:
        h = new_dict[cusip]
        if h["name"]:  # 跳过无名称的占位记录
            changes.append({
                "type": "新增",
                "name": h["name"],
                "ticker": h.get("ticker", ""),
                "cusip": cusip,
                "shares": h["shares"],
                "value": h["value"]
            })

    # 清仓
    for cusip in old_cusips - new_cusips:
        h = old_holdings[cusip]
        if h.get("name"):
            changes.append({
                "type": "清仓",
                "name": h["name"],
                "ticker": h.get("ticker", ""),
                "cusip": cusip,
                "shares": h["shares"],
                "value": h["value"]
            })

    # 增减持（股数变化超过1%）
    for cusip in old_cusips & new_cusips:
        old_h = old_holdings[cusip]
        new_h = new_dict[cusip]
        old_shares = old_h["shares"]
        new_shares = new_h["shares"]

        if new_shares == 0 and old_shares > 0:
            changes.append({
                "type": "清仓",
                "name": new_h["name"],
                "ticker": new_h.get("ticker", ""),
                "cusip": cusip,
                "old_shares": old_shares,
                "new_shares": 0
            })
        elif new_shares > old_shares:
            pct_change = (new_shares - old_shares) / old_shares * 100
            if pct_change >= 1:
                changes.append({
                    "type": "增持",
                    "name": new_h["name"],
                    "ticker": new_h.get("ticker", ""),
                    "cusip": cusip,
                    "old_shares": old_shares,
                    "new_shares": new_shares,
                    "change_pct": pct_change
                })
        elif new_shares < old_shares:
            pct_change = (old_shares - new_shares) / old_shares * 100
            if pct_change >= 1:
                changes.append({
                    "type": "减持",
                    "name": new_h["name"],
                    "ticker": new_h.get("ticker", ""),
                    "cusip": cusip,
                    "old_shares": old_shares,
                    "new_shares": new_shares,
                    "change_pct": pct_change
                })

    return changes


def show_notification(changes, report_period, enable_gui=True):
    """构建通知消息，并可选地弹出GUI窗口"""
    if not changes:
        return

    # 构建消息文本
    lines = [
        f"📊 伯克希尔持仓变动通知",
        f"📅 报告期: {report_period}",
        f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"{'=' * 40}\n"
    ]

    for c in changes:
        if c["type"] == "新增":
            ticker_info = f" ({c['ticker']})" if c.get("ticker") else ""
            lines.append(
                f"➕ 新增 {c['name']}{ticker_info}\n"
                f"   CUSIP: {c['cusip']} | 持股: {c['shares']:,}股\n"
                f"   市值: ${c['value']/1000:.1f}M"
            )
        elif c["type"] == "清仓":
            ticker_info = f" ({c.get('ticker', '')})" if c.get("ticker") else ""
            shares = c.get("old_shares", c.get("shares", 0))
            lines.append(
                f"➖ 清仓 {c['name']}{ticker_info}\n"
                f"   CUSIP: {c['cusip']} | 原持股: {shares:,}股"
            )
        elif c["type"] in ["增持", "减持"]:
            ticker_info = f" ({c.get('ticker', '')})" if c.get("ticker") else ""
            arrow = "📈" if c["type"] == "增持" else "📉"
            lines.append(
                f"{arrow} {c['type']} {c['name']}{ticker_info}\n"
                f"   {c['old_shares']:,} → {c['new_shares']:,}股 "
                f"({c['change_pct']:+.1f}%)"
            )
        lines.append("")  # 空行分隔

    msg = "\n".join(lines)

    # 始终输出到日志（控制台和文件）
    logging.info(msg)

    # GUI弹窗
    if enable_gui:
        try:
            root = Tk()
            root.withdraw()
            messagebox.showinfo("伯克希尔持仓变动", msg)
            root.destroy()
        except Exception as e:
            logging.error(f"GUI弹窗失败: {e}")


def main():
    # 加载配置
    config = load_config()
    # 设置日志
    logger = setup_logging(config["log_dir"])
    # 设置EDGAR身份
    set_identity(config["identity_email"])

    cache_path = get_cache_path(config["log_dir"], config["cache_file"])

    try:
        logging.info("正在获取伯克希尔最新13F文件...")

        # 获取最新持仓
        holdings, report_period = get_latest_holdings()
        logging.info(f"获取成功 | 报告期: {report_period} | 持仓数: {len(holdings)}")

        # 加载缓存
        old_cache = load_cache(cache_path)

        # 首次运行，只保存缓存
        if not old_cache:
            logging.info("首次运行，已保存缓存，下次运行将检测变化")
            save_cache(cache_path, holdings, report_period)
            return

        # 检查报告期是否变化
        old_period = old_cache.get("report_period")
        if old_period == report_period:
            logging.info(f"报告期 {report_period} 无变化，跳过检测")
            return

        # 对比变化
        changes = compare_holdings(old_cache, holdings)

        if changes:
            logging.info(f"检测到 {len(changes)} 处变化")
            show_notification(changes, report_period, config["enable_notification"])
            # 更新缓存
            save_cache(cache_path, holdings, report_period)
        else:
            logging.info("持仓无显著变化")

    except Exception as e:
        logging.exception(f"监测失败: {e}")  # 记录异常堆栈
        # 若启用通知，则弹出错误消息（使用GUI）
        if config["enable_notification"]:
            try:
                root = Tk()
                root.withdraw()
                messagebox.showerror("错误", f"持仓监控失败：{e}")
                root.destroy()
            except:
                pass


if __name__ == "__main__":
    main()