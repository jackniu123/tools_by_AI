# -*- coding: utf-8 -*-
"""
股票助手 - 打新日历提醒工具
功能：
- 每日强提醒：若未来一周内有新股新债，则展示所有未来可申购的股票，并显示剩余天数
- 每周预告：每周五提醒下周所有工作日新股新债
- 多源数据获取（东方财富JSON/同花顺JSON+API/新浪网/东方财富日历数据/缓存）
- 汇总所有成功数据源的结果，去重后展示
- 弹窗中新股和新债分组显示，每组按申购日期排序
- 今日申购的条目用红色高亮，每条记录显示剩余天数
- 弹窗底部显示各数据源获取状态
- 含一键打开东方财富/国泰海通证券（手动）
- 自动添加开机启动
- 详细日志记录
"""

import os
import json
import datetime
import subprocess
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import logging
import traceback
import re
from pathlib import Path

import requests
import pandas as pd

# ==================== 配置 ====================
CONFIG_DIR = os.path.join(os.environ['USERPROFILE'], '.stock_assistant')
STATE_FILE = os.path.join(CONFIG_DIR, 'state.json')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
CACHE_FILE = os.path.join(CONFIG_DIR, 'new_issues_cache.json')
LOG_FILE = os.path.join(CONFIG_DIR, 'app.log')
CACHE_EXPIRE_DAYS = 1  # 缓存有效期（天）

# 北交所股票代码前缀（用于排除新股）
BEIJING_PREFIXES = ('8', '43', '83', '87', '88', '920')

# 每周提醒日（0=周一，4=周五）
WEEKLY_REMINDER_WEEKDAY = 0

# 证券软件常见安装路径（备选）
SOFTWARE_PATHS = {
    '东方财富': [
        r'C:\Program Files\东方财富\dfzq\dfzq.exe',
        r'C:\Program Files (x86)\东方财富\dfzq\dfzq.exe',
    ],
    '国泰海通': [
        r'C:\Program Files\国泰海通\gtja.exe',
        r'C:\Program Files (x86)\国泰海通\gtja.exe',
        r'C:\Program Files\国泰君安\gtja.exe',
        r'C:\Program Files (x86)\国泰君安\gtja.exe',
    ]
}

# 通用请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# ==================== 日志配置 ====================
def setup_logging():
    """配置日志输出到文件和控制台"""
    ensure_config_dir()
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 文件处理器
    fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
    fh.setLevel(logging.INFO)

    # 控制台处理器
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # 格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

# ==================== 工具函数 ====================
def ensure_config_dir():
    """确保配置目录存在"""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        logging.info(f"创建配置目录: {CONFIG_DIR}")

def load_state():
    """加载状态文件"""
    ensure_config_dir()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                logging.info("状态加载成功")
                return state
        except Exception as e:
            logging.error(f"加载状态文件失败: {e}")
            return {}
    logging.info("状态文件不存在，使用初始状态")
    return {'daily_reminder_date': None, 'weekly_reminder_week': None}

def save_state(state):
    """保存状态"""
    ensure_config_dir()
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
        logging.info("状态保存成功")
    except Exception as e:
        logging.error(f"保存状态失败: {e}")

def load_config():
    """加载软件配置"""
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logging.info("配置加载成功")
                return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return {}
    return {}

def save_config(config):
    """保存软件配置"""
    ensure_config_dir()
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f)
        logging.info("配置保存成功")
    except Exception as e:
        logging.error(f"保存配置失败: {e}")

def is_workday(date):
    """判断是否为工作日（仅跳过周六日）"""
    return date.weekday() < 5

def get_next_workdays(start_date, num_days):
    """
    获取从 start_date 开始（包含当天）往后 num_days 个工作日的日期列表
    """
    dates = []
    current = start_date
    while len(dates) < num_days:
        if is_workday(current):
            dates.append(current)
        current += datetime.timedelta(days=1)
    logging.debug(f"计算得到的下 {num_days} 个工作日: {[d.isoformat() for d in dates]}")
    return dates

def get_next_week_workdays(today):
    """获取下周所有工作日（周一至周五）"""
    days_to_monday = (7 - today.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    next_monday = today + datetime.timedelta(days=days_to_monday)
    next_week = [next_monday + datetime.timedelta(days=i) for i in range(5)]
    logging.debug(f"下周工作日: {[d.isoformat() for d in next_week]}")
    return next_week

# ==================== 数据源函数 ====================

def fetch_from_10jqka_stock_json():
    """
    从同花顺新股页面提取隐藏的 jsondata 数据
    返回 DataFrame，包含 名称、代码、日期、类型，失败返回 None
    """
    try:
        url = 'https://data.10jqka.com.cn/ipo/xgsgyzq/'
        logging.info("尝试从同花顺新股JSON提取数据...")
        headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Referer': 'https://data.10jqka.com.cn/ipo/xgsgyzq/'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        html = resp.text

        pattern = r'<div\s+style="display:none"\s+id="jsondatas">(.*?)</div>'
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            logging.warning("未找到jsondatas数据")
            return None

        json_str = match.group(1)
        data = json.loads(json_str)

        stock_list = data.get('data', [])
        if not stock_list:
            logging.warning("jsondata中无data数组")
            return None

        records = []
        for item in stock_list:
            stock_name = item.get('STOCKNAME', '')
            stock_code = item.get('STOCKCODE', '')
            sg_date = item.get('SGDATE', '')

            if stock_name and '\\u' in repr(stock_name):
                try:
                    stock_name = stock_name.encode('utf-8').decode('unicode_escape')
                except:
                    pass

            if stock_name and stock_code and sg_date and sg_date != '0000-00-00':
                records.append({
                    '名称': stock_name,
                    '代码': stock_code,
                    '日期': sg_date,
                    '类型': '新股'
                })

        if not records:
            logging.warning("解析后无有效新股记录")
            return None

        df = pd.DataFrame(records)

        # 处理日期列：先标准化为 YYYY-MM-DD
        def normalize_date(date_str):
            # 如果已经是 YYYY-MM-DD 格式，直接返回
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return date_str
            # 尝试匹配 MM-DD 格式（可能后面有中文星期）
            match = re.match(r'(\d{2})-(\d{2})', date_str)
            if match:
                month, day = match.groups()
                year = datetime.datetime.now().year  # 假设是当前年份
                return f"{year}-{month}-{day}"
            # 无法解析则返回 None
            return None

        df['日期'] = df['日期'].apply(normalize_date)
        # 过滤掉无法解析的日期
        df = df.dropna(subset=['日期'])

        before = len(df)
        df = df[~df['代码'].astype(str).str.startswith(BEIJING_PREFIXES)]
        df['日期'] = pd.to_datetime(df['日期']).dt.date
        logging.info(f"同花顺新股JSON获取成功，原始 {before} 条，过滤北交所后 {len(df)} 条")
        return df

    except Exception as e:
        logging.error(f"同花顺新股JSON抓取失败: {e}\n{traceback.format_exc()}")
        return None


def fetch_from_10jqka_stock():
    """
    从同花顺抓取新股数据（HTML备选，支持列索引回退）
    返回 DataFrame 或 None
    """
    try:
        url = 'https://data.10jqka.com.cn/ipo/xgsgyzq/'
        logging.info("尝试从同花顺抓取新股（HTML备选）...")
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        tables = pd.read_html(resp.text, header=0, encoding=resp.encoding)
        if not tables:
            logging.warning("同花顺新股页面无表格")
            return None

        df = tables[0].copy()
        df.columns = [str(col).replace('\n', '').strip() for col in df.columns]
        logging.info(f"同花顺新股原始列名: {list(df.columns)}")

        name_col = None
        code_col = None
        date_col = None
        for col in df.columns:
            col_lower = col.lower()
            if '简称' in col_lower or '名称' in col_lower:
                name_col = col
            if '代码' in col_lower:
                code_col = col
            if '申购日期' in col_lower or '发行日期' in col_lower:
                date_col = col

        if not (name_col and code_col and date_col):
            logging.warning("新股列名匹配失败，尝试按列索引回退")
            if len(df.columns) >= 3:
                sample = df.iloc[0]
                if str(sample[0]).isdigit() and len(str(sample[0])) == 6:
                    code_col = df.columns[0]
                    name_col = df.columns[1]
                    date_col = df.columns[2]
                else:
                    code_col = df.columns[1]
                    name_col = df.columns[0]
                    date_col = df.columns[2]
                logging.info(f"回退使用列索引: 代码列={code_col}, 名称列={name_col}, 日期列={date_col}")
            else:
                logging.error("新股表格列数不足，无法回退")
                return None

        if name_col and code_col and date_col:
            df = df[[name_col, code_col, date_col]].copy()
            df.rename(columns={name_col: '名称', code_col: '代码', date_col: '日期'}, inplace=True)
            df['类型'] = '新股'
            before = len(df)
            df = df[~df['代码'].astype(str).str.startswith(BEIJING_PREFIXES)]
            logging.info(f"新股原始 {before} 条，过滤北交所后 {len(df)} 条")
            df['日期'] = pd.to_datetime(df['日期'], errors='coerce').dt.date
            df = df.dropna(subset=['日期'])
            logging.info(f"同花顺新股HTML抓取成功，共 {len(df)} 条")
            return df
        else:
            logging.warning("同花顺新股缺少必要列")
            return None

    except Exception as e:
        logging.error(f"同花顺新股HTML抓取失败: {e}\n{traceback.format_exc()}")
        return None


def fetch_from_10jqka_kzz_api():
    """
    从同花顺可转债API接口获取数据
    返回 DataFrame，包含 名称、代码、日期、类型，失败返回 None
    """
    try:
        url = 'https://data.10jqka.com.cn/ipo/kzz/'
        logging.info("尝试从同花顺可转债API获取数据...")
        headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Referer': 'https://data.10jqka.com.cn/ipo/kzz/'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        data = resp.json()

        if data.get('status_code') != 0:
            logging.warning(f"同花顺API返回非成功状态: {data.get('status_msg')}")
            return None

        bond_list = data.get('list', [])
        if not bond_list:
            logging.warning("同花顺API返回空列表")
            return None

        records = []
        for item in bond_list:
            bond_name = item.get('bond_name', '')
            bond_code = item.get('bond_code', '')
            sub_date = item.get('sub_date', '')

            if bond_name and '\\u' in repr(bond_name):
                try:
                    bond_name = bond_name.encode('utf-8').decode('unicode_escape')
                except:
                    pass

            if bond_name and bond_code and sub_date:
                records.append({
                    '名称': bond_name,
                    '代码': bond_code,
                    '日期': sub_date,
                    '类型': '新债'
                })

        if not records:
            logging.warning("同花顺API解析后无有效记录")
            return None

        df = pd.DataFrame(records)
        df['日期'] = pd.to_datetime(df['日期']).dt.date
        logging.info(f"同花顺可转债API获取成功，共 {len(df)} 条")
        return df

    except Exception as e:
        logging.error(f"同花顺可转债API抓取失败: {e}\n{traceback.format_exc()}")
        return None


def fetch_from_10jqka_bond():
    """
    从同花顺抓取可转债数据（HTML备选，支持列索引回退）
    返回 DataFrame 或 None
    """
    try:
        url = 'https://data.10jqka.com.cn/ipo/bond/'
        logging.info("尝试从同花顺抓取可转债（HTML备选）...")
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        tables = pd.read_html(resp.text, header=0, encoding=resp.encoding)
        if not tables:
            logging.warning("同花顺可转债页面无表格")
            return None

        df = tables[0].copy()
        df.columns = [str(col).replace('\n', '').strip() for col in df.columns]
        logging.info(f"同花顺可转债原始列名: {list(df.columns)}")

        name_col = None
        code_col = None
        date_col = None
        for col in df.columns:
            col_lower = col.lower()
            if '债券简称' in col_lower or '简称' in col_lower:
                name_col = col
            if '债券代码' in col_lower or '代码' in col_lower:
                code_col = col
            if '申购日期' in col_lower or '发行日期' in col_lower:
                date_col = col

        if not (name_col and code_col and date_col):
            logging.warning("可转债列名匹配失败，尝试按列索引回退")
            if len(df.columns) >= 3:
                sample = df.iloc[0]
                if str(sample[0]).replace('-', '').isalnum() and len(str(sample[0])) <= 10:
                    code_col = df.columns[0]
                    name_col = df.columns[1]
                    date_col = df.columns[2]
                else:
                    code_col = df.columns[1]
                    name_col = df.columns[0]
                    date_col = df.columns[2]
                logging.info(f"回退使用列索引: 代码列={code_col}, 名称列={name_col}, 日期列={date_col}")
            else:
                logging.error("可转债表格列数不足，无法回退")
                return None

        if name_col and code_col and date_col:
            df = df[[name_col, code_col, date_col]].copy()
            df.rename(columns={name_col: '名称', code_col: '代码', date_col: '日期'}, inplace=True)
            df['类型'] = '新债'
            df['日期'] = pd.to_datetime(df['日期'], errors='coerce').dt.date
            df = df.dropna(subset=['日期'])
            logging.info(f"同花顺可转债HTML抓取成功，共 {len(df)} 条")
            return df
        else:
            logging.warning("同花顺可转债缺少必要列")
            return None

    except Exception as e:
        logging.error(f"同花顺可转债HTML抓取失败: {e}\n{traceback.format_exc()}")
        return None


def fetch_from_sina_stock():
    """
    从新浪网抓取新股数据（支持分页）
    返回 DataFrame，包含 名称、代码、日期、类型，失败返回 None
    """
    try:
        base_url = 'https://vip.stock.finance.sina.com.cn/corp/go.php/vRPD_NewStockIssue/page/{}.phtml'
        page = 1
        all_records = []
        headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Referer': 'https://vip.stock.finance.sina.com.cn/'
        }

        while True:
            url = base_url.format(page)
            logging.info(f"尝试从新浪网抓取新股，第 {page} 页...")
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'gb2312'
            tables = pd.read_html(resp.text, header=0, encoding='gb2312')

            if not tables:
                logging.warning(f"新浪网第 {page} 页无表格")
                break

            df = tables[0].copy()
            df = df.iloc[:, :-1]
            df = df[1:]
            df.columns = df.iloc[0].values

            # 删除原来的第二行（索引为1）
            df = df.drop(index=1).reset_index(drop=True)

            # 清理列名中的HTML标签和换行
            df.columns = [str(col).replace('\n', '').replace('<br>', '').strip() for col in df.columns]
            logging.info(f"新浪网第 {page} 页原始列名: {list(df.columns)}")

            # 查找所需列
            name_col = None
            code_col = None
            date_col = None
            for col in df.columns:
                col_lower = col.lower()
                if '证券简称' in col or '简称' in col_lower:
                    name_col = col
                if '证券代码' in col or '代码' in col_lower:
                    code_col = col
                if '上网发行' in col and '日期' in col_lower:
                    date_col = col

            if name_col and code_col and date_col:
                page_records = df[[name_col, code_col, date_col]].copy()
                page_records.rename(columns={name_col: '名称', code_col: '代码', date_col: '日期'}, inplace=True)
                page_records['类型'] = '新股'
                # 过滤无效日期
                page_records = page_records[page_records['日期'] != '0']
                all_records.append(page_records)
                logging.info(f"新浪网第 {page} 页抓取到 {len(page_records)} 条记录")
            else:
                logging.warning(f"新浪网第 {page} 页缺少必要列，当前列: {list(df.columns)}")
                break

            # 检查是否有下一页
            if '下一页' not in resp.text or 'disabled' in resp.text:
                break
            page += 1
            break

        if not all_records:
            logging.warning("新浪网未抓取到任何数据")
            return None

        df_result = pd.concat(all_records, ignore_index=True)
        before = len(df_result)
        df_result = df_result[~df_result['代码'].astype(str).str.startswith(BEIJING_PREFIXES)]
        df_result['日期'] = pd.to_datetime(df_result['日期'], errors='coerce').dt.date
        df_result = df_result.dropna(subset=['日期'])
        logging.info(f"新浪网新股抓取完成，原始 {before} 条，过滤北交所后 {len(df_result)} 条")
        return df_result

    except Exception as e:
        logging.error(f"新浪网新股抓取失败: {e}\n{traceback.format_exc()}")
        return None


def fetch_from_eastmoney_calendar():
    """
    从东方财富新股日历页面提取 pagedata 变量中的 calendardata 数据
    返回 DataFrame，包含所有新股/可转债申购信息，失败返回 None
    """
    try:
        url = 'https://data.eastmoney.com/xg/xg/calendar.html'
        logging.info("尝试从东方财富 pagedata 获取数据...")
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = 'utf-8'
        html = resp.text

        pattern = r'var\s+pagedata\s*=\s*(\{.*?\});'
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            logging.warning("未找到 pagedata 变量")
            logging.debug(f"html前500字符: {html[:500]}")
            return None

        json_str = match.group(1)
        data = json.loads(json_str)

        calendardata = data.get('calendardata', {})
        if not calendardata:
            logging.warning("pagedata 中无 calendardata 字段")
            return None

        result_data = calendardata.get('result', {}).get('data', [])
        if not result_data:
            logging.warning("calendardata.result.data 为空")
            return None

        records = []
        for item in result_data:
            if item.get('DATE_TYPE') != '申购':
                continue
            sec_type = item.get('SECURITY_TYPE')
            if sec_type not in ('0', '1'):
                continue

            name = item.get('SECURITY_NAME_ABBR', '')
            code = item.get('SECURITY_CODE', '')
            date_str = item.get('TRADE_DATE', '')[:10]

            if name and code and date_str:
                records.append({
                    '名称': name,
                    '代码': code,
                    '日期': date_str,
                    '类型': '新股' if sec_type == '0' else '新债'
                })

        if not records:
            logging.warning("解析后无有效申购记录")
            return None

        df = pd.DataFrame(records)
        before = len(df)
        df = df[~((df['类型'] == '新股') & (df['代码'].astype(str).str.startswith(BEIJING_PREFIXES)))]
        df['日期'] = pd.to_datetime(df['日期']).dt.date
        logging.info(f"东方财富 pagedata 获取成功，原始 {before} 条，过滤北交所后 {len(df)} 条")
        return df

    except Exception as e:
        logging.error(f"东方财富 pagedata 抓取失败: {e}\n{traceback.format_exc()}")
        return None


def fetch_from_cache():
    """
    从本地缓存文件读取数据
    返回 DataFrame 或 None
    """
    if not os.path.exists(CACHE_FILE):
        logging.info("缓存文件不存在")
        return None

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        cache_date = cache.get('date')
        if cache_date:
            cache_date = datetime.datetime.strptime(cache_date, '%Y-%m-%d').date()
            if (datetime.date.today() - cache_date).days <= CACHE_EXPIRE_DAYS:
                df = pd.DataFrame(cache['data'])
                df['日期'] = pd.to_datetime(df['日期']).dt.date
                logging.info(f"从缓存读取 {len(df)} 条数据，日期 {cache_date}")
                return df
            else:
                logging.info("缓存已过期")
        else:
            logging.warning("缓存文件格式错误")
    except Exception as e:
        logging.error(f"读取缓存失败: {e}")
    return None


def save_to_cache(df):
    """
    将数据保存到本地缓存
    """
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        cache = {
            'date': datetime.date.today().isoformat(),
            'data': df.to_dict(orient='records')
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        logging.info(f"数据已缓存到 {CACHE_FILE}")
    except Exception as e:
        logging.error(f"保存缓存失败: {e}")


def fetch_from_10jqka_combined():
    """合并同花顺新股和可转债数据（优先使用JSON/API，回退HTML）"""
    df_stock = fetch_from_10jqka_stock_json()
    if df_stock is None or df_stock.empty:
        logging.info("同花顺新股JSON失败，尝试HTML抓取...")
        df_stock = fetch_from_10jqka_stock()

    df_bond = fetch_from_10jqka_kzz_api()
    if df_bond is None or df_bond.empty:
        logging.info("同花顺可转债API失败，尝试HTML抓取...")
        df_bond = fetch_from_10jqka_bond()

    if df_stock is None and df_bond is None:
        return None

    result = pd.DataFrame()
    if df_stock is not None and not df_stock.empty:
        result = pd.concat([result, df_stock], ignore_index=True)
    if df_bond is not None and not df_bond.empty:
        result = pd.concat([result, df_bond], ignore_index=True)

    return result if not result.empty else None


def get_new_issues():
    """
    多源获取新股新债数据，汇总所有成功的数据源，去重后返回
    返回 (DataFrame, logs列表)
    """
    sources = [
        ("同花顺", fetch_from_10jqka_combined),
        ("新浪网新股", fetch_from_sina_stock),
        ("东方财富日历数据", fetch_from_eastmoney_calendar),
        ("本地缓存", fetch_from_cache)
    ]

    logs = []                # 记录每个数据源的尝试结果
    all_dfs = []             # 存放成功获取的 DataFrame
    used_source_names = []   # 记录成功的数据源名称（用于日志）

    for name, func in sources:
        logging.info(f"尝试从 {name} 获取数据...")
        try:
            df = func()
            if df is not None and not df.empty:
                logs.append(f"✓ {name}: 成功 (获取 {len(df)} 条)")
                all_dfs.append(df)
                used_source_names.append(name)
            else:
                logs.append(f"✗ {name}: 无有效数据")
        except Exception as e:
            logs.append(f"✗ {name}: 异常 - {str(e)[:50]}")
            logging.error(f"{name} 执行异常: {e}")

    if not all_dfs:
        logs.append("✗ 所有数据源均失败")
        return pd.DataFrame(), logs

    # 合并所有成功的数据源
    combined = pd.concat(all_dfs, ignore_index=True)
    # 去重：基于 ['代码', '日期'] 保留第一条
    combined = combined.drop_duplicates(subset=['代码', '日期'], keep='first')
    logging.info(f"汇总成功源: {', '.join(used_source_names)}，共 {len(combined)} 条（去重后）")
    return combined, logs


# ==================== 弹窗与软件打开 ====================

def open_software(software_name):
    """打开证券软件，优先使用用户配置的路径，否则自动搜索常见位置"""
    config = load_config()
    path = config.get(software_name)

    if path and os.path.exists(path):
        try:
            subprocess.Popen(path)
            logging.info(f"打开软件 {software_name} 成功: {path}")
            return
        except Exception as e:
            logging.error(f"打开软件 {software_name} 失败 (配置路径): {e}")

    for p in SOFTWARE_PATHS.get(software_name, []):
        if os.path.exists(p):
            try:
                subprocess.Popen(p)
                config[software_name] = p
                save_config(config)
                logging.info(f"打开软件 {software_name} 成功 (自动搜索): {p}")
                return
            except Exception as e:
                logging.error(f"打开软件 {software_name} 失败 (自动搜索路径 {p}): {e}")
                continue

    logging.warning(f"未找到 {software_name}，请求用户手动选择")
    messagebox.showinfo("提示", f"未找到 {software_name}，请手动选择可执行文件")
    filepath = filedialog.askopenfilename(title=f"选择 {software_name} 程序")
    if filepath:
        config[software_name] = filepath
        save_config(config)
        try:
            subprocess.Popen(filepath)
            logging.info(f"打开软件 {software_name} 成功 (手动选择): {filepath}")
        except Exception as e:
            logging.error(f"无法打开 {software_name} (手动选择): {e}")
            messagebox.showerror("错误", f"无法打开 {software_name}:\n{e}")


def show_reminder(issues, title, logs, on_snooze=None):
    """
    显示提醒弹窗，按新股/新债分组，每组内按申购日期排序，并显示剩余天数
    """
    logging.info(f"显示提醒弹窗: {title}，包含 {len(issues)} 条记录")
    today = datetime.date.today()

    # 定义分组顺序
    type_order = ['新股', '新债']
    # 创建临时列用于排序：按类型在 type_order 中的索引，再按日期
    issues_sorted = issues.copy()
    issues_sorted['type_index'] = issues_sorted['类型'].map({t: i for i, t in enumerate(type_order)})
    issues_sorted = issues_sorted.sort_values(['type_index', '日期']).drop('type_index', axis=1)

    def on_open_dfz():
        open_software('东方财富')

    def on_open_gt():
        open_software('国泰海通')

    def on_snooze_click():
        if on_snooze:
            on_snooze()
        root.destroy()

    root = tk.Tk()
    root.title(title)
    root.geometry("700x550")
    root.attributes('-topmost', True)

    # 新股列表区域
    list_frame = tk.Frame(root)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,5))

    list_label = tk.Label(list_frame, text="新股新债列表", font=('微软雅黑', 10, 'bold'))
    list_label.pack(anchor='w')

    list_text = scrolledtext.ScrolledText(list_frame, wrap=tk.WORD, font=('微软雅黑', 10), height=12)
    list_text.pack(fill=tk.BOTH, expand=True)

    # 配置标签样式
    list_text.tag_config('red', foreground='red')
    list_text.tag_config('bold', font=('微软雅黑', 10, 'bold'))

    # 逐行插入，分组，并计算剩余天数
    current_type = None
    for _, row in issues_sorted.iterrows():
        if row['类型'] != current_type:
            current_type = row['类型']
            list_text.insert(tk.END, f"\n--- {current_type} ---\n", 'bold')

        # 计算剩余天数
        days_remaining = (row['日期'] - today).days
        if days_remaining == 0:
            days_str = "今日申购"
        elif days_remaining > 0:
            days_str = f"剩余{days_remaining}天"
        else:
            days_str = "已过期"  # 理论上不会出现，因为传入的应是未来数据，但以防万一

        line = f"{row['类型']}: {row['名称']} ({row['代码']}) 申购日: {row['日期']} ({days_str})\n"
        if row['日期'] == today:
            list_text.insert(tk.END, line, 'red')
        else:
            list_text.insert(tk.END, line)

    list_text.configure(state='disabled')

    # 数据源日志区域
    log_frame = tk.Frame(root)
    log_frame.pack(fill=tk.X, padx=10, pady=5)

    log_label = tk.Label(log_frame, text="数据源获取情况", font=('微软雅黑', 10, 'bold'))
    log_label.pack(anchor='w')

    log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=('微软雅黑', 9), height=5)
    log_text.pack(fill=tk.X)

    log_str = "\n".join(logs)
    log_text.insert(tk.END, log_str)
    log_text.configure(state='disabled')

    # 按钮区域
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)

    btn_dfz = tk.Button(btn_frame, text="打开东方财富证券", command=on_open_dfz, width=20)
    btn_dfz.pack(side=tk.LEFT, padx=10)

    btn_gt = tk.Button(btn_frame, text="打开国泰海通证券", command=on_open_gt, width=20)
    btn_gt.pack(side=tk.LEFT, padx=10)

    if on_snooze:
        btn_snooze = tk.Button(btn_frame, text="今日不再提醒", command=on_snooze_click, width=20)
        btn_snooze.pack(side=tk.LEFT, padx=10)

    btn_close = tk.Button(root, text="关闭", command=root.destroy)
    btn_close.pack(pady=5)

    root.mainloop()
    logging.info("提醒弹窗已关闭")


# ==================== 主逻辑 ====================
def main():
    setup_logging()
    logging.info("=" * 50)
    logging.info("股票助手启动")

    try:
        state = load_state()
        today = datetime.date.today()
        logging.info(f"当前日期: {today.isoformat()}")

        issues, source_logs = get_new_issues()
        if issues.empty:
            logging.warning("未获取到数据，程序退出")
            # 可考虑弹窗提示无数据？此处保持静默退出
            return

        # 每日强提醒：若未来一周内有新股新债，则展示所有未来可申购的（日期≥今天）
        next_week_dates = [today + datetime.timedelta(days=i) for i in range(7)]
        has_next_week = issues['日期'].isin(next_week_dates).any()
        if has_next_week:
            # 检查是否已设置今日不再提醒
            if state.get('daily_reminder_date') != today.isoformat():
                # 筛选所有未来可申购的记录（日期 >= 今天）
                future_issues = issues[issues['日期'] >= today].copy()
                if not future_issues.empty:
                    logging.info(f"触发每日提醒（未来一周有新股），展示所有未来 {len(future_issues)} 条记录")
                    def snooze_daily():
                        state['daily_reminder_date'] = today.isoformat()
                        save_state(state)
                        logging.info("用户点击今日不再提醒，状态已保存")
                    show_reminder(future_issues, "打新强提醒：未来可申购新股新债", source_logs, on_snooze=snooze_daily)
                else:
                    logging.info("无未来可申购记录，跳过每日提醒")
            else:
                logging.info("今日已设置不再提醒，跳过每日提醒")
        else:
            logging.info("今日无未来一周新股新债，不触发每日提醒")

        # 每周预告：若今天是指定提醒日，提示下周所有工作日
        if today.weekday() == WEEKLY_REMINDER_WEEKDAY:
            next_week_days = get_next_week_workdays(today)
            weekly_mask = issues['日期'].isin(next_week_days)
            weekly_issues = issues[weekly_mask]

            if not weekly_issues.empty:
                week_num = today.isocalendar()[1]
                if state.get('weekly_reminder_week') != week_num:
                    logging.info(f"触发每周提醒，共 {len(weekly_issues)} 条")
                    # 每周提醒不提供“今日不再提醒”按钮
                    show_reminder(weekly_issues, "下周新股新债预告", source_logs)
                    state['weekly_reminder_week'] = week_num
                    save_state(state)
                else:
                    logging.info("本周已提醒过，跳过每周提醒")
            else:
                logging.info("下周无新股新债")
        else:
            logging.info("今天不是每周提醒日")

    except Exception as e:
        logging.critical(f"程序运行出错: {e}\n{traceback.format_exc()}")
    finally:
        logging.info("股票助手运行结束")
        logging.info("=" * 50)


if __name__ == "__main__":
    main()