# -*- coding: utf-8 -*-
"""
海外免费代理自动搜索与验证脚本（完整整合增强版）
功能：从多个免费代理源抓取IP -> 验证对 protonvpn.com 的可用性 -> 测试速度 -> 筛选海外节点
改进：引导代理、协议识别、内容验证、失败源缓存、递归抓取
适用：Windows/Linux/Mac 需要Python3.6+
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import json
import os
import random
import urllib3

# ==================== 配置区域 ====================
TEST_URL = "https://protonvpn.com"           # 目标网站
TIMEOUT_CONNECT = 5                           # 连接超时（秒）
TIMEOUT_READ = 10                             # 读取超时（秒）
MAX_WORKERS = 300                             # 并发验证线程数
MIN_SPEED = 8000                              # 最小接受速度（毫秒），8秒
MAX_PROXIES_TO_TEST = 5000                    # 每次最多测试的代理数量（随机采样）
TEST_METHOD = 'get'                           # 始终使用 GET（HEAD 太容易被屏蔽）
VERIFY_CONTENT = True                         # 是否验证响应内容包含目标关键词
TARGET_KEYWORD = "Proton VPN"                 # 目标网站特征文本

# 输出目录：用户主目录下的 proxy_finder_results
USER_DIR = os.path.expanduser("~")
OUTPUT_DIR = os.path.join(USER_DIR, "proxy_finder_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "protonvpn_proxies.txt")
CACHE_FILE = os.path.join(OUTPUT_DIR, "last_valid_proxies.json")
DEAD_SOURCES_FILE = os.path.join(OUTPUT_DIR, "dead_sources.json")  # 记录失败源

# ==================== 代理源列表 ====================
PROXY_SOURCES = [
    {
        'name': 'ProxyScrape',
        'url': 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
        'type': 'plain',
        'timeout': 30
    },
    {
        'name': 'Geonode',
        'url': 'https://proxylist.geonode.com/api/proxy-list?limit=200&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps',
        'type': 'json',
        'timeout': 30
    },
    {
        'name': 'GitHub_HTTP',
        'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        'type': 'plain',
        'timeout': 30
    },
    {
        'name': 'GitHub_SOCKS4',
        'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt',
        'type': 'plain',
        'timeout': 30
    },
    {
        'name': 'GitHub_SOCKS5',
        'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt',
        'type': 'plain',
        'timeout': 30
    },
    {
        'name': 'GitHub_Mirror_HTTP',
        'url': 'https://ghproxy.net/https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        'type': 'plain',
        'timeout': 20
    },
    {
        'name': 'FreeProxyList',
        'url': 'https://free-proxy-list.net/',
        'type': 'html',
        'timeout': 30
    },
    {
        'name': 'IPRoyal',
        'url': 'https://iproyal.com/free-proxy-list/',
        'type': 'html',
        'timeout': 30
    },
    {
        'name': 'Zdaye',
        'url': 'http://open.zdaye.com/FreeProxy/Get/',
        'type': 'json',
        'timeout': 20
    },
    {
        'name': 'ProxyList',
        'url': 'https://www.proxy-list.download/api/v1/get?type=http',
        'type': 'plain',
        'timeout': 30
    },
    {
        'name': 'OpenProxyList',
        'url': 'https://raw.githubusercontent.com/rooster/open-proxy-list/master/online.txt',
        'type': 'plain',
        'timeout': 30
    },
    # 引导代理源（首先尝试用这些工作代理去抓取其他源，但此处作为普通备用源）
    {
        'name': 'Bootstrap_Proxy',
        'url': 'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt',
        'type': 'plain',
        'timeout': 15
    },
    # 内置备用代理（保底，请定期手动更新）
    {
        'name': 'Builtin_Backup',
        'type': 'builtin',
        'proxies': [
            '45.33.26.213:8080',
            '47.88.48.235:3128',
            '103.152.182.53:8080'
        ]
    }
]

# ==================== 失败源缓存管理 ====================
def load_dead_sources():
    if os.path.exists(DEAD_SOURCES_FILE):
        try:
            with open(DEAD_SOURCES_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_dead_sources(dead):
    with open(DEAD_SOURCES_FILE, 'w') as f:
        json.dump(dead, f, indent=2)

def is_source_dead(name):
    dead = load_dead_sources()
    if name in dead:
        until = dead[name].get('until')
        if until and datetime.now() < datetime.fromisoformat(until):
            return True
        else:
            # 过期则删除记录
            del dead[name]
            save_dead_sources(dead)
    return False

def mark_source_dead(name, hours=24):
    dead = load_dead_sources()
    dead[name] = {'until': (datetime.now() + timedelta(hours=hours)).isoformat()}
    save_dead_sources(dead)

# ==================== 缓存函数 ====================
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

def save_cache(proxies):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(proxies, f, indent=2)

# ==================== 代理格式规范化与协议识别 ====================
def normalize_proxy(proxy_str):
    """
    将原始代理字符串统一为带协议的格式：http://ip:port 或 socks5://ip:port
    若无法识别，默认 http
    """
    proxy_str = proxy_str.strip()
    if proxy_str.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
        return proxy_str
    # 默认按端口猜测
    parts = proxy_str.split(':')
    if len(parts) == 2 and parts[1].isdigit():
        port = int(parts[1])
        # 常见 socks 端口
        if port in (1080, 1081, 1085, 1086, 9050, 9051):
            return f'socks5://{proxy_str}'
    return f'http://{proxy_str}'

def extract_ip_port(proxy_str):
    """从标准代理字符串中提取 ip:port"""
    # 去掉协议头
    if '://' in proxy_str:
        proxy_str = proxy_str.split('://', 1)[1]
    return proxy_str

# ==================== 抓取代理（带错误处理和死源跳过）====================
def fetch_proxies_from_source(source):
    name = source['name']
    if is_source_dead(name):
        print(f"[跳过] 源 {name} 已被标记为失效，跳过本次运行")
        return []

    url = source.get('url')
    timeout = source.get('timeout', 30)

    if source.get('type') == 'builtin':
        print(f"[内置] 使用备用内置代理列表: {len(source['proxies'])} 个")
        return source['proxies']

    print(f"[网络] 正在从 {name} 抓取代理... (超时={timeout}s)")

    for attempt in range(3):
        try:
            session = requests.Session()
            retry = Retry(total=1, backoff_factor=0.5, status_forcelist=[500,502,503,504])
            adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive'
            }

            response = session.get(url, headers=headers, timeout=timeout)
            proxies = []

            if source['type'] == 'plain':
                for line in response.text.splitlines():
                    line = line.strip()
                    # 匹配 ip:port 格式
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', line):
                        proxies.append(line)

            elif source['type'] == 'json':
                try:
                    data = response.json()
                    if source['name'] == 'Zdaye':
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and 'ip' in item and 'port' in item:
                                    proxies.append(f"{item['ip']}:{item['port']}")
                                elif isinstance(item, str) and re.match(r'\d+\.\d+\.\d+\.\d+:\d+', item):
                                    proxies.append(item)
                        elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
                            for item in data['data']:
                                if isinstance(item, dict) and 'ip' in item and 'port' in item:
                                    proxies.append(f"{item['ip']}:{item['port']}")
                    elif source['name'] == 'Geonode':
                        for item in data.get('data', []):
                            if item.get('protocols') and ('http' in item.get('protocols', []) or 'https' in item.get('protocols', [])):
                                proxies.append(f"{item.get('ip')}:{item.get('port')}")
                    else:
                        # 通用 JSON 解析
                        items = data if isinstance(data, list) else data.get('data', []) if isinstance(data, dict) else []
                        for item in items:
                            if isinstance(item, dict):
                                ip = item.get('ip') or item.get('host')
                                port = item.get('port') or item.get('port_number')
                                if ip and port:
                                    proxies.append(f"{ip}:{port}")
                            elif isinstance(item, str) and re.match(r'\d+\.\d+\.\d+\.\d+:\d+', item):
                                proxies.append(item)
                except json.JSONDecodeError:
                    # fallback 到文本解析
                    for line in response.text.splitlines()[:200]:
                        if re.match(r'\d+\.\d+\.\d+\.\d+:\d+', line):
                            proxies.append(line.strip())

            elif source['type'] == 'html':
                # 增强 HTML 解析
                html = response.text
                # 尝试多种表格模式
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
                for row in rows[:80]:
                    cols = re.findall(r'<td[^>]*>(.*?)</td>', row)
                    if len(cols) >= 2:
                        ip = cols[0].strip()
                        port = cols[1].strip()
                        if re.match(r'\d+\.\d+\.\d+\.\d+', ip) and port.isdigit():
                            proxies.append(f"{ip}:{port}")
                # 如果没找到，尝试直接匹配 IP:PORT 文本
                if not proxies:
                    proxies = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b', html)

            if proxies:
                print(f"[OK] 从 {name} 获取到 {len(proxies)} 个代理")
                return proxies
            else:
                print(f"[警告] {name} 返回0个代理，重试...")
        except Exception as e:
            print(f"[重试] {name} 抓取失败 (尝试 {attempt+1}/3): {str(e)[:100]}")
            time.sleep(2 ** attempt)

    print(f"[失败] 从 {name} 抓取失败，已放弃")
    mark_source_dead(name)  # 标记为死亡，短期不再使用
    return []

# ==================== 递归引导抓取（关键改进）====================
def gather_all_proxies():
    all_proxies = []
    # 先并行抓取所有源
    with ThreadPoolExecutor(max_workers=len(PROXY_SOURCES)) as executor:
        future_to_source = {executor.submit(fetch_proxies_from_source, s): s for s in PROXY_SOURCES}
        for future in as_completed(future_to_source):
            proxies = future.result()
            all_proxies.extend(proxies)

    all_proxies = list(set(all_proxies))

    # 如果抓取到的代理很少（<50），且已有内置代理，则使用内置代理作为引导去重新抓取
    if len(all_proxies) < 50:
        print("[引导] 抓取到的代理数量过少，尝试使用内置代理或缓存代理作为引导，重新抓取其它源...")
        # 获取内置代理
        bootstrap_proxies = []
        for s in PROXY_SOURCES:
            if s.get('type') == 'builtin':
                bootstrap_proxies.extend(s.get('proxies', []))
        # 如果缓存中有上次有效代理，也加入引导
        cached = load_cache()
        if cached:
            bootstrap_proxies.extend(cached[:20])  # 取前20个
        bootstrap_proxies = list(set(bootstrap_proxies))

        if bootstrap_proxies:
            print(f"[引导] 使用 {len(bootstrap_proxies)} 个引导代理，重新抓取失败的源...")
            # 重新抓取那些之前失败的源（但跳过 builtin 源本身）
            for s in PROXY_SOURCES:
                if s.get('type') != 'builtin' and is_source_dead(s['name']):
                    # 尝试用引导代理去重新抓取
                    proxies_from_bootstrap = fetch_with_bootstrap_proxies(s, bootstrap_proxies)
                    all_proxies.extend(proxies_from_bootstrap)
            all_proxies = list(set(all_proxies))

    print(f"\n[数据] 总共收集到 {len(all_proxies)} 个不重复代理")
    return all_proxies

def fetch_with_bootstrap_proxies(source, bootstrap_proxies):
    """使用引导代理列表去抓取某个源"""
    name = source['name']
    url = source.get('url')
    if not url:
        return []
    print(f"[引导抓取] 使用引导代理尝试从 {name} 抓取...")
    for proxy_str in bootstrap_proxies[:10]:  # 最多试10个引导代理
        try:
            proxies = { 'http': proxy_str, 'https': proxy_str }
            session = requests.Session()
            session.proxies = proxies
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = session.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                # 解析代理
                proxies_found = []
                if source['type'] == 'plain':
                    for line in resp.text.splitlines():
                        if re.match(r'\d+\.\d+\.\d+\.\d+:\d+', line.strip()):
                            proxies_found.append(line.strip())
                elif source['type'] == 'json':
                    try:
                        data = resp.json()
                        # 简化解析
                        items = data if isinstance(data, list) else data.get('data', [])
                        for item in items:
                            if isinstance(item, dict) and 'ip' in item and 'port' in item:
                                proxies_found.append(f"{item['ip']}:{item['port']}")
                    except:
                        pass
                if proxies_found:
                    print(f"[引导成功] 从 {name} 抓取到 {len(proxies_found)} 个代理")
                    return proxies_found
        except Exception as e:
            continue
    return []

# ==================== 验证核心函数（带内容验证）====================
def test_proxy_for_target_optimized(proxy_with_proto, target_url):
    """
    测试代理是否能访问目标网站
    proxy_with_proto: 例如 http://1.2.3.4:8080 或 socks5://1.2.3.4:1080
    返回 (proxy_str, success, speed_ms, ip_addr)
    """
    # 提取 ip:port 用于后续显示
    proxy_clean = extract_ip_port(proxy_with_proto)
    proxies = {}
    # 根据协议设置
    if proxy_with_proto.startswith('socks4://'):
        proxies = {
            'http': proxy_with_proto,
            'https': proxy_with_proto
        }
    elif proxy_with_proto.startswith('socks5://'):
        proxies = {
            'http': proxy_with_proto,
            'https': proxy_with_proto
        }
    else:
        # 默认为 http
        proxies = {
            'http': proxy_with_proto,
            'https': proxy_with_proto
        }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }

    try:
        start_time = time.time()
        # 使用 GET 请求，分拆超时
        response = requests.get(
            target_url,
            proxies=proxies,
            timeout=(TIMEOUT_CONNECT, TIMEOUT_READ),
            headers=headers,
            allow_redirects=True,
            verify=False
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        # 状态码检查
        if response.status_code >= 400:
            return (proxy_clean, False, 0, '')

        # 内容验证（可选）
        if VERIFY_CONTENT and TARGET_KEYWORD.lower() not in response.text.lower():
            # 可能被重定向到验证页面或者空白页
            return (proxy_clean, False, 0, '')

        # 简单判断 IP 地理位置（不再强制排除国内，仅标记）
        # 提取代理的 IP
        ip_addr = proxy_clean.split(':')[0]
        # 不进行海外过滤，全部保留，由用户自行决定
        return (proxy_clean, True, elapsed_ms, ip_addr)

    except Exception:
        return (proxy_clean, False, 0, '')

def validate_proxies_for_target(proxies_raw, target_url):
    """
    并发验证代理对目标网站的可用性
    proxies_raw: 未规范化的代理列表（ip:port 格式）
    """
    # 规范化：统一添加协议
    normalized = []
    for p in proxies_raw:
        if isinstance(p, dict):
            p = p.get('proxy', p.get('ip_port', ''))
        if p:
            normalized.append(normalize_proxy(p))
    proxies = list(set(normalized))

    print(f"[开始] 验证 {len(proxies)} 个代理能否访问 {target_url}...")
    if len(proxies) > MAX_PROXIES_TO_TEST:
        test_proxies = random.sample(proxies, MAX_PROXIES_TO_TEST)
    else:
        test_proxies = proxies
    print(f"[目标] 实际测试 {len(test_proxies)} 个代理")

    valid_proxies = []
    tested = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {
            executor.submit(test_proxy_for_target_optimized, proxy, target_url): proxy
            for proxy in test_proxies
        }

        for future in as_completed(future_to_proxy):
            tested += 1
            proxy_clean, can_access, speed, ip_addr = future.result()

            if tested % 50 == 0 or tested == len(test_proxies):
                print(f"[进度] {tested}/{len(test_proxies)} | 已发现有效: {len(valid_proxies)}")

            if can_access:
                # 速度过滤
                if speed < MIN_SPEED:
                    print(f"[可用] {proxy_clean} - {speed}ms")
                    valid_proxies.append({
                        'proxy': proxy_clean,
                        'speed': speed,
                        'ip': ip_addr,
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                else:
                    print(f"[慢速] {proxy_clean} - {speed}ms (超过阈值 {MIN_SPEED}ms)")

    valid_proxies.sort(key=lambda x: x['speed'])
    return valid_proxies

# ==================== 保存结果 ====================
def save_results(valid_proxies, target_url):
    if not valid_proxies:
        print(f"[结果] 没有找到能访问 {target_url} 的可用代理")
        return

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# 可访问 {target_url} 的代理列表 - 按速度排序\n")
        f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 共 {len(valid_proxies)} 个\n")
        f.write("# 格式: IP:端口 (响应时间)\n\n")
        for item in valid_proxies:
            f.write(f"{item['proxy']}  # {item['speed']}ms\n")

    json_file = OUTPUT_FILE.replace('.txt', '.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(valid_proxies, f, indent=2, ensure_ascii=False)

    proxy_list = [item['proxy'] for item in valid_proxies]
    save_cache(proxy_list)

    print(f"\n[保存] 结果已保存到: {OUTPUT_FILE} 和 {json_file}")
    print(f"\n[排行] 最快的前10个代理:")
    for i, item in enumerate(valid_proxies[:10]):
        print(f"   {i+1}. {item['proxy']} - {item['speed']}ms")

# ==================== 主函数 ====================
def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("="*70)
    print("*** 海外免费代理自动搜索工具 v4.0（完整整合增强版）***")
    print("="*70)
    print(f"目标网站: {TEST_URL}")
    print(f"内容验证: {'开启' if VERIFY_CONTENT else '关闭'} (关键词 '{TARGET_KEYWORD}')")
    print(f"结果保存目录: {OUTPUT_DIR}")
    print("="*70)

    print(f"\n[时间] 开始探测: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("[步骤1] 从多个免费源收集代理（含引导机制）...")
    all_proxies = gather_all_proxies()

    if not all_proxies:
        print("[警告] 没有从网络源收集到任何代理，尝试加载本地缓存...")
        cached = load_cache()
        if cached:
            print(f"[缓存] 加载上次成功代理 {len(cached)} 个")
            all_proxies = cached
        else:
            print("[错误] 没有可用代理，退出")
            return

    print(f"\n[步骤2] 验证代理能否访问 {TEST_URL}...")
    valid_proxies = validate_proxies_for_target(all_proxies, TEST_URL)

    print("\n[步骤3] 保存结果...")
    save_results(valid_proxies, TEST_URL)

    print("\n[完成] 本轮探测完成，脚本退出。")

if __name__ == "__main__":
    main()