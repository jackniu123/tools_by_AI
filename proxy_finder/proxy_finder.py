# -*- coding: utf-8 -*-
"""
海外免费代理自动搜索与验证脚本（单次运行版，无Emoji）
功能：从多个免费代理源抓取IP -> 验证对 protonvpn.com 的可用性 -> 测试速度 -> 筛选海外节点
      每次运行只执行一轮，适合配合外部定时任务（如cron）实现每天一次。
修正：✅ 站大爷API地址修正为正确格式
       ✅ 新增多个免费代理源
适用：Windows/Linux/Mac 需要Python3.6+
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import os
import random
import urllib3

# ==================== 配置区域 ====================
TEST_URL = "https://protonvpn.com"           # 目标网站
TIMEOUT = 10                                  # 代理测试超时时间（秒）
MAX_WORKERS = 300                             # 并发验证线程数
MIN_SPEED = 8000                              # 最小接受速度（毫秒），8秒
MAX_PROXIES_TO_TEST = 5000                    # 每次最多测试的代理数量（随机采样）
TEST_METHOD = 'head'                           # 'head' 或 'get'，优先使用head减少流量

# 输出目录：用户主目录下的 proxy_finder_results
USER_DIR = os.path.expanduser("~")
OUTPUT_DIR = os.path.join(USER_DIR, "proxy_finder_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "protonvpn_proxies.txt")

# ==================== 代理源列表 ====================
PROXY_SOURCES = [
    # 源1：ProxyScrape（实时更新）
    {
        'name': 'ProxyScrape',
        'url': 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
        'type': 'plain'
    },
    # 源2：Geonode API（附带地理位置）
    {
        'name': 'Geonode',
        'url': 'https://proxylist.geonode.com/api/proxy-list?limit=200&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps',
        'type': 'json'
    },
    # 源3：GitHub PROXY-List（每日更新，SOCKS+HTTP）
    {
        'name': 'GitHub_HTTP',
        'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        'type': 'plain'
    },
    {
        'name': 'GitHub_SOCKS4',
        'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt',
        'type': 'plain'
    },
    {
        'name': 'GitHub_SOCKS5',
        'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt',
        'type': 'plain'
    },
    # 源4：FreeProxyList（HTML解析）
    {
        'name': 'FreeProxyList',
        'url': 'https://free-proxy-list.net/',
        'type': 'html'
    },
    # 源5：IPRoyal 免费列表（每10分钟更新）
    {
        'name': 'IPRoyal',
        'url': 'https://iproyal.com/free-proxy-list/',
        'type': 'html'
    },
    # 源6：站大爷免费代理API（修正版）
    {
        'name': 'Zdaye',
        'url': 'http://open.zdaye.com/FreeProxy/Get/',
        'type': 'json'
    },
    # 源7：ProxyList（备用）
    {
        'name': 'ProxyList',
        'url': 'https://www.proxy-list.download/api/v1/get?type=http',
        'type': 'plain'
    },
    # 源8：OpenProxyList（社区维护）
    {
        'name': 'OpenProxyList',
        'url': 'https://raw.githubusercontent.com/rooster/open-proxy-list/master/online.txt',
        'type': 'plain'
    }
]

# 需要排除的国内IP段（粗略匹配）
CN_IP_RANGES = [
    '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.',
    '11.', '12.', '13.', '14.', '15.', '16.', '17.', '18.', '19.', '20.',
    '21.', '22.', '23.', '24.', '25.', '26.', '27.', '28.', '29.', '30.',
    '31.', '32.', '33.', '34.', '35.', '36.', '37.', '38.', '39.', '40.',
    '41.', '42.', '43.', '44.', '45.', '46.', '47.', '48.', '49.', '50.',
    '58.', '59.', '60.', '61.', '110.', '111.', '112.', '113.', '114.',
    '115.', '116.', '117.', '118.', '119.', '120.', '121.', '122.', '123.',
    '124.', '125.', '126.', '127.', '128.', '129.', '130.', '131.', '132.',
    '133.', '134.', '135.', '136.', '137.', '138.', '139.', '140.', '141.',
    '142.', '143.', '144.', '145.', '146.', '147.', '148.', '149.', '150.',
    '151.', '152.', '153.', '154.', '155.', '156.', '157.', '158.', '159.',
    '160.', '161.', '162.', '163.', '164.', '165.', '166.', '167.', '168.',
    '169.', '170.', '171.', '172.', '173.', '174.', '175.', '176.', '177.',
    '178.', '179.', '180.', '181.', '182.', '183.', '184.', '185.', '186.',
    '187.', '188.', '189.', '190.', '191.', '192.', '193.', '194.', '195.',
    '196.', '197.', '198.', '199.', '200.', '201.', '202.', '203.', '204.',
    '205.', '206.', '207.', '208.', '209.', '210.', '211.', '212.', '213.',
    '214.', '215.', '216.', '217.', '218.', '219.', '220.', '221.', '222.',
    '223.'
]

# ==================== 核心函数 ====================

def fetch_proxies_from_source(source):
    """
    从指定的源抓取代理列表
    """
    print("[网络] 正在从 {} 抓取代理...".format(source['name']))
    proxies = []

    try:
        session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = session.get(source['url'], headers=headers, timeout=15)

        if source['type'] == 'plain':
            lines = response.text.strip().split('\n')
            for line in lines:
                proxy = line.strip()
                if re.match(r'\d+\.\d+\.\d+\.\d+:\d+', proxy):
                    proxies.append(proxy)

        elif source['type'] == 'json':
            try:
                data = response.json()
                if source['name'] == 'Zdaye':
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'ip' in item and 'port' in item:
                                proxy = f"{item['ip']}:{item['port']}"
                                proxies.append(proxy)
                            elif isinstance(item, str):
                                if re.match(r'\d+\.\d+\.\d+\.\d+:\d+', item):
                                    proxies.append(item)
                    elif isinstance(data, dict):
                        if 'data' in data and isinstance(data['data'], list):
                            for item in data['data']:
                                if isinstance(item, dict) and 'ip' in item and 'port' in item:
                                    proxy = f"{item['ip']}:{item['port']}"
                                    proxies.append(proxy)
                elif source['name'] == 'Geonode':
                    for item in data.get('data', []):
                        if item.get('protocols') and 'http' in item.get('protocols', []):
                            proxy = f"{item.get('ip')}:{item.get('port')}"
                            proxies.append(proxy)
                else:
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, str) and re.match(r'\d+\.\d+\.\d+\.\d+:\d+', item):
                                proxies.append(item)
            except json.JSONDecodeError:
                print("[警告] {} 返回的不是有效JSON，尝试按文本处理".format(source['name']))
                lines = response.text.strip().split('\n')
                for line in lines[:50]:
                    if re.match(r'\d+\.\d+\.\d+\.\d+:\d+', line):
                        proxies.append(line.strip())

        elif source['type'] == 'html':
            html = response.text
            rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL)
            for row in rows[1:30]:
                cols = re.findall(r'<td[^>]*>(.*?)</td>', row)
                if len(cols) >= 2:
                    ip = cols[0].strip()
                    port = cols[1].strip()
                    if re.match(r'\d+\.\d+\.\d+\.\d+', ip) and port.isdigit():
                        proxies.append(f"{ip}:{port}")

        print("[OK] 从 {} 获取到 {} 个代理".format(source['name'], len(proxies)))

    except Exception as e:
        print("[失败] 从 {} 抓取失败: {}".format(source['name'], str(e)))

    return proxies

def is_likely_overseas(proxy_ip):
    """粗略判断是否为海外IP"""
    for cn_prefix in CN_IP_RANGES:
        if proxy_ip.startswith(cn_prefix):
            return False
    return True

def test_proxy_for_target_optimized(proxy, target_url):
    """
    优化版代理测试：优先使用HEAD请求，失败则降级为GET
    """
    proxies = {
        'http': f'http://{proxy}',
        'https': f'http://{proxy}'
    }
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        start_time = time.time()

        if TEST_METHOD == 'head':
            try:
                response = requests.head(
                    target_url,
                    proxies=proxies,
                    timeout=TIMEOUT,
                    headers=headers,
                    allow_redirects=True,
                    verify=False
                )
                elapsed_ms = int((time.time() - start_time) * 1000)
                if response.status_code < 400:
                    proxy_ip = proxy.split(':')[0]
                    if is_likely_overseas(proxy_ip):
                        return (proxy, True, elapsed_ms, proxy_ip)
                    else:
                        return (proxy, False, elapsed_ms, proxy_ip)
                else:
                    return (proxy, False, 0, '')
            except:
                pass

        start_time = time.time()
        response = requests.get(
            target_url,
            proxies=proxies,
            timeout=TIMEOUT,
            headers=headers,
            allow_redirects=True,
            verify=False
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        if response.status_code < 400:
            proxy_ip = proxy.split(':')[0]
            if is_likely_overseas(proxy_ip):
                return (proxy, True, elapsed_ms, proxy_ip)
            else:
                return (proxy, False, elapsed_ms, proxy_ip)
        else:
            return (proxy, False, 0, '')

    except Exception:
        return (proxy, False, 0, '')

def gather_all_proxies():
    """从所有源收集代理"""
    all_proxies = []

    with ThreadPoolExecutor(max_workers=len(PROXY_SOURCES)) as executor:
        future_to_source = {
            executor.submit(fetch_proxies_from_source, source): source
            for source in PROXY_SOURCES
        }

        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                proxies = future.result()
                all_proxies.extend(proxies)
            except Exception as e:
                print("处理 {} 时出错: {}".format(source['name'], e))

    all_proxies = list(set(all_proxies))
    print("\n[数据] 总共收集到 {} 个不重复代理".format(len(all_proxies)))
    return all_proxies

def validate_proxies_for_target(proxies, target_url):
    """
    并发验证代理对目标网站的可用性（优化版）
    """
    print("[开始] 验证 {} 个代理能否访问 {}...".format(len(proxies), target_url))
    print("[信息] 将随机测试最多 {} 个代理（如需全量测试，请修改 MAX_PROXIES_TO_TEST）".format(MAX_PROXIES_TO_TEST))

    if len(proxies) > MAX_PROXIES_TO_TEST:
        test_proxies = random.sample(proxies, MAX_PROXIES_TO_TEST)
    else:
        test_proxies = proxies

    print("[目标] 实际测试 {} 个代理".format(len(test_proxies)))

    valid_proxies = []
    tested = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {
            executor.submit(test_proxy_for_target_optimized, proxy, target_url): proxy
            for proxy in test_proxies
        }

        for future in as_completed(future_to_proxy):
            tested += 1
            proxy, can_access, speed, ip_addr = future.result()

            if tested % 10 == 0 or tested == len(test_proxies):
                print("[进度] {}/{} | 已发现有效: {}".format(tested, len(test_proxies), len(valid_proxies)))

            if can_access and speed < MIN_SPEED:
                print("[可用] 可访问 {} 的海外代理: {} - {}ms".format(target_url, proxy, speed))
                valid_proxies.append({
                    'proxy': proxy,
                    'speed': speed,
                    'ip': ip_addr,
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            elif can_access and speed >= MIN_SPEED:
                print("[慢速] 速度较慢但可访问: {} - {}ms".format(proxy, speed))

    valid_proxies.sort(key=lambda x: x['speed'])
    return valid_proxies

def save_results(valid_proxies, target_url):
    """保存结果到文件"""
    if not valid_proxies:
        print("[结果] 没有找到能访问 {} 的可用海外代理".format(target_url))
        return

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# 可访问 {target_url} 的海外代理列表 - 按速度排序\n")
        f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 共 {len(valid_proxies)} 个\n")
        f.write("# 格式: IP:端口 (响应时间)\n\n")

        for item in valid_proxies:
            f.write(f"{item['proxy']}  # {item['speed']}ms\n")

    json_file = OUTPUT_FILE.replace('.txt', '.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(valid_proxies, f, indent=2, ensure_ascii=False)

    print("\n[保存] 结果已保存到: {} 和 {}".format(OUTPUT_FILE, json_file))

    print("\n[排行] 最快的前10个可访问 {} 的代理:".format(target_url))
    for i, item in enumerate(valid_proxies[:10]):
        print("   {}. {} - {}ms".format(i+1, item['proxy'], item['speed']))

# ==================== 主程序（单次运行）====================
def main():
    # 抑制SSL警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("="*70)
    print("*** 海外免费代理自动搜索工具 v3.3（单次运行版）***")
    print("="*70)
    print("目标网站: {}".format(TEST_URL))
    print("结果保存目录: {}".format(OUTPUT_DIR))
    print("="*70)

    print("\n[时间] 开始探测: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print("[步骤1] 从多个免费源收集代理...")
    all_proxies = gather_all_proxies()

    if not all_proxies:
        print("[错误] 没有收集到任何代理，退出")
        return

    print("\n[步骤2] 验证代理能否访问 {}...".format(TEST_URL))
    valid_proxies = validate_proxies_for_target(all_proxies, TEST_URL)

    print("\n[步骤3] 保存结果...")
    save_results(valid_proxies, TEST_URL)

    print("\n[完成] 本轮探测完成，脚本退出。")

if __name__ == "__main__":
    main()