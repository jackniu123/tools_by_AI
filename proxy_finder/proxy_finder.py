# -*- coding: utf-8 -*-
"""
海外免费代理自动搜索与验证脚本（含稳定性测试 v6.0）
功能：抓取代理 -> 验证对 protonvpn.com 的可用性 -> 速度排序 -> 对前100名做多次重复测试 -> 输出稳定性报告
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
import statistics

# ==================== 配置区域 ====================
# TEST_URL = "https://vpn-api.proton.me/vpn/logicals"
TEST_URL = "https://protonvpn.com"
TIMEOUT_CONNECT = 5
TIMEOUT_READ = 10
MAX_WORKERS = 300
MIN_SPEED = 5000              # 初始速度阈值 (ms)
MAX_PROXIES_TO_TEST = 5000
VERIFY_CONTENT = False
TARGET_KEYWORD = "Proton VPN"

# 稳定性测试配置
STABILITY_TEST_ENABLED = True
STABILITY_TEST_REPEAT = 5     # 每个代理重复测试次数
STABILITY_MAX_WORKERS = 20    # 稳定性测试并发数（不宜过高，避免误判）
STABILITY_SUCCESS_THRESHOLD = 80   # 最低成功率 (%)
STABILITY_SPEED_THRESHOLD = 10000  # 最大平均延迟 (ms) 推荐代理阈值

# 死源缓存时间
DEAD_SOURCE_EXPIRE_HOURS = 2

# 输出目录
USER_DIR = os.path.expanduser("~")
OUTPUT_DIR = os.path.join(USER_DIR, "proxy_finder_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "protonvpn_proxies.txt")
CACHE_FILE = os.path.join(OUTPUT_DIR, "last_valid_proxies.json")
DEAD_SOURCES_FILE = os.path.join(OUTPUT_DIR, "dead_sources.json")
STABLE_REPORT_FILE = os.path.join(OUTPUT_DIR, "stable_proxies.json")
STABLE_RECOMMENDED_FILE = os.path.join(OUTPUT_DIR, "stable_proxies_recommended.txt")

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# ==================== 代理源列表（同上一版） ====================
PROXY_SOURCES = [
    {'name': 'ProxyScrape', 'url': 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all', 'type': 'plain', 'timeout': 30},
    {'name': 'Geonode', 'url': 'https://proxylist.geonode.com/api/proxy-list?limit=200&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps', 'type': 'json', 'timeout': 30},
    {'name': 'GitHub_HTTP', 'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt', 'type': 'plain', 'timeout': 30, 'use_mirror': True},
    {'name': 'GitHub_SOCKS4', 'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt', 'type': 'plain', 'timeout': 30, 'use_mirror': True},
    {'name': 'GitHub_SOCKS5', 'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt', 'type': 'plain', 'timeout': 30, 'use_mirror': True},
    {'name': 'GitHub_Mirror_HTTP', 'url': 'https://ghproxy.net/https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt', 'type': 'plain', 'timeout': 20},
    {'name': 'FreeProxyList', 'url': 'https://free-proxy-list.net/', 'type': 'html', 'timeout': 30},
    {'name': 'IPRoyal', 'url': 'https://iproyal.com/free-proxy-list/', 'type': 'html', 'timeout': 30},
    {'name': 'Zdaye', 'url': 'http://open.zdaye.com/FreeProxy/Get/', 'type': 'json', 'timeout': 20},
    {'name': 'ProxyList', 'url': 'https://www.proxy-list.download/api/v1/get?type=http', 'type': 'plain', 'timeout': 30},
    {'name': 'OpenProxyList', 'url': 'https://raw.githubusercontent.com/rooster/open-proxy-list/master/online.txt', 'type': 'plain', 'timeout': 30, 'use_mirror': True},
    {'name': 'Bootstrap_Proxy', 'url': 'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt', 'type': 'plain', 'timeout': 15, 'use_mirror': True},
    {'name': 'Builtin_Backup', 'type': 'builtin', 'proxies': ['45.33.26.213:8080', '47.88.48.235:3128', '103.152.182.53:8080']}
]

# ==================== 以下为基础功能函数（与上一版相同，略作精简） ====================
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
            del dead[name]
            save_dead_sources(dead)
    return False

def mark_source_dead(name, hours=DEAD_SOURCE_EXPIRE_HOURS):
    dead = load_dead_sources()
    dead[name] = {'until': (datetime.now() + timedelta(hours=hours)).isoformat()}
    save_dead_sources(dead)

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

def normalize_proxy(proxy_str):
    proxy_str = proxy_str.strip()
    if proxy_str.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
        return proxy_str
    parts = proxy_str.split(':')
    if len(parts) == 2 and parts[1].isdigit():
        port = int(parts[1])
        if port in (1080, 1081, 1085, 1086, 1088, 2080, 9050, 9051):
            return f'socks5://{proxy_str}'
    return f'http://{proxy_str}'

def extract_ip_port(proxy_str):
    if '://' in proxy_str:
        proxy_str = proxy_str.split('://', 1)[1]
    return proxy_str

def get_headers():
    return {'User-Agent': random.choice(USER_AGENTS), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9', 'Connection': 'keep-alive'}

def fetch_url_with_retry(url, timeout, source_type, retries=3):
    for attempt in range(retries):
        try:
            session = requests.Session()
            retry_strategy = Retry(total=1, backoff_factor=0.5, status_forcelist=[500,502,503,504])
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            response = session.get(url, headers=get_headers(), timeout=timeout)
            if response.status_code == 200:
                return response
        except Exception:
            time.sleep(1 * (attempt+1))
    return None

def parse_proxies_from_response(response, source_type, source_name):
    proxies = []
    if not response:
        return proxies
    text = response.text
    if source_type == 'plain':
        for line in text.splitlines():
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', line.strip()):
                proxies.append(line.strip())
    elif source_type == 'json':
        try:
            data = response.json()
            if source_name == 'Geonode':
                for item in data.get('data', []):
                    if item.get('protocols') and ('http' in item.get('protocols', []) or 'https' in item.get('protocols', [])):
                        proxies.append(f"{item.get('ip')}:{item.get('port')}")
            else:
                items = data if isinstance(data, list) else data.get('data', [])
                for item in items:
                    if isinstance(item, dict):
                        ip = item.get('ip') or item.get('host')
                        port = item.get('port') or item.get('port_number')
                        if ip and port:
                            proxies.append(f"{ip}:{port}")
        except:
            pass
    elif source_type == 'html':
        rows = re.findall(r'<tr[^>]*>(.*?)</table>', text, re.DOTALL)
        for row in rows[:80]:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row)
            if len(cols) >= 2:
                ip = cols[0].strip()
                port = cols[1].strip()
                if re.match(r'\d+\.\d+\.\d+\.\d+', ip) and port.isdigit():
                    proxies.append(f"{ip}:{port}")
        if not proxies:
            proxies = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b', text)
    return proxies

def fetch_proxies_from_source(source):
    name = source['name']
    if is_source_dead(name):
        print(f"[跳过] 源 {name} 已失效")
        return []
    if source.get('type') == 'builtin':
        print(f"[内置] {name}: {len(source['proxies'])} 个")
        return source['proxies']
    url = source.get('url')
    timeout = source.get('timeout', 30)
    use_mirror = source.get('use_mirror', False)
    urls_to_try = []
    if use_mirror and 'raw.githubusercontent.com' in url:
        mirror_url = url.replace('raw.githubusercontent.com', 'ghproxy.net/https://raw.githubusercontent.com')
        urls_to_try.append(mirror_url)
    urls_to_try.append(url)
    for attempt_url in urls_to_try:
        resp = fetch_url_with_retry(attempt_url, timeout, source['type'], retries=2)
        if resp:
            proxies = parse_proxies_from_response(resp, source['type'], name)
            if proxies:
                print(f"[OK] {name} -> {len(proxies)} 个代理")
                return proxies
    print(f"[失败] {name}")
    mark_source_dead(name)
    return []

def gather_all_proxies():
    all_proxies = []
    with ThreadPoolExecutor(max_workers=min(len(PROXY_SOURCES), 20)) as executor:
        futures = {executor.submit(fetch_proxies_from_source, s): s for s in PROXY_SOURCES}
        for future in as_completed(futures):
            all_proxies.extend(future.result())
    all_proxies = list(set(all_proxies))
    print(f"[收集] 总计 {len(all_proxies)} 个不重复代理")
    if len(all_proxies) < 50:
        bootstrap = []
        for s in PROXY_SOURCES:
            if s.get('type') == 'builtin':
                bootstrap.extend(s.get('proxies', []))
        bootstrap.extend(load_cache()[:30])
        bootstrap = list(set(bootstrap))
        if bootstrap:
            print(f"[引导] 使用 {len(bootstrap)} 个引导代理重试失效源")
            with ThreadPoolExecutor(max_workers=10) as ex:
                fut2 = {ex.submit(fetch_with_bootstrap, s, bootstrap): s for s in PROXY_SOURCES if s.get('type') != 'builtin' and is_source_dead(s['name'])}
                for f in as_completed(fut2):
                    all_proxies.extend(f.result())
            all_proxies = list(set(all_proxies))
    return all_proxies

def fetch_with_bootstrap(source, bootstrap_proxies):
    name = source['name']
    url = source.get('url')
    if not url:
        return []
    for proxy_str in bootstrap_proxies[:15]:
        try:
            proxies = {'http': proxy_str, 'https': proxy_str}
            resp = requests.get(url, headers=get_headers(), proxies=proxies, timeout=20)
            if resp.status_code == 200:
                return parse_proxies_from_response(resp, source['type'], name)
        except:
            continue
    return []

def test_proxy_single(proxy_with_proto, target_url):
    """单次测试，返回 (proxy_clean, success, speed_ms)"""
    proxy_clean = extract_ip_port(proxy_with_proto)
    proxies = {'http': proxy_with_proto, 'https': proxy_with_proto}
    try:
        start = time.time()
        r = requests.get(target_url, proxies=proxies, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ),
                         headers=get_headers(), allow_redirects=True, verify=False)
        elapsed = int((time.time() - start) * 1000)
        if r.status_code < 400 and (not VERIFY_CONTENT or TARGET_KEYWORD.lower() in r.text.lower()):
            return (proxy_clean, True, elapsed)
        return (proxy_clean, False, 0)
    except:
        return (proxy_clean, False, 0)

def validate_proxies_for_target(proxies_raw, target_url):
    normalized = list(set([normalize_proxy(p) for p in proxies_raw if p]))
    if len(normalized) > MAX_PROXIES_TO_TEST:
        test_proxies = random.sample(normalized, MAX_PROXIES_TO_TEST)
    else:
        test_proxies = normalized
    print(f"[验证] 测试 {len(test_proxies)} 个代理")
    valid = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_proxy_single, proxy, target_url): proxy for proxy in test_proxies}
        for future in as_completed(futures):
            proxy_clean, ok, speed = future.result()
            if ok and speed < MIN_SPEED:
                valid.append({'proxy': proxy_clean, 'speed': speed, 'ip': proxy_clean.split(':')[0], 'time': datetime.now().isoformat()})
    valid.sort(key=lambda x: x['speed'])
    print(f"[验证完成] 有效代理数: {len(valid)}")
    return valid

# ==================== 稳定性测试模块 ====================
def stability_test_single_proxy(proxy_with_proto, target_url, repeat=STABILITY_TEST_REPEAT):
    """
    对单个代理重复测试多次，返回稳定性指标
    """
    speeds = []
    success_count = 0
    proxy_clean = extract_ip_port(proxy_with_proto)
    for _ in range(repeat):
        _, ok, speed = test_proxy_single(proxy_with_proto, target_url)
        if ok:
            success_count += 1
            speeds.append(speed)
        time.sleep(0.5)  # 间隔半秒，避免过于激进
    success_rate = (success_count / repeat) * 100
    avg_speed = statistics.mean(speeds) if speeds else 0
    std_speed = statistics.stdev(speeds) if len(speeds) > 1 else 0
    min_speed = min(speeds) if speeds else 0
    max_speed = max(speeds) if speeds else 0
    return {
        'proxy': proxy_clean,
        'repeat': repeat,
        'success_count': success_count,
        'success_rate': round(success_rate, 2),
        'avg_speed_ms': round(avg_speed, 1),
        'std_speed_ms': round(std_speed, 1),
        'min_speed_ms': min_speed,
        'max_speed_ms': max_speed
    }

def run_stability_test(valid_proxies, target_url, top_n=100):
    """
    对速度前 top_n 个代理进行稳定性测试
    """
    if not valid_proxies:
        print("[稳定性测试] 没有可用代理，跳过")
        return []
    top_proxies = valid_proxies[:top_n]
    print(f"\n[稳定性测试] 将对前 {len(top_proxies)} 个代理进行 {STABILITY_TEST_REPEAT} 次重复测试...")
    results = []
    with ThreadPoolExecutor(max_workers=STABILITY_MAX_WORKERS) as executor:
        futures = {executor.submit(stability_test_single_proxy, item['proxy'], target_url): item for item in top_proxies}
        for i, future in enumerate(as_completed(futures), 1):
            res = future.result()
            results.append(res)
            print(f"[稳定性进度] {i}/{len(top_proxies)} - {res['proxy']} 成功率 {res['success_rate']}% 平均 {res['avg_speed_ms']}ms")
    # 按成功率+平均速度综合排序（成功率高的在前，同成功率速度快的在前）
    results.sort(key=lambda x: (-x['success_rate'], x['avg_speed_ms']))
    return results

def print_stability_report(results):
    """打印表格形式报告并保存文件"""
    if not results:
        print("无稳定性测试结果")
        return
    print("\n" + "="*100)
    print("稳定性测试报告 (重复测试次数: {})".format(STABILITY_TEST_REPEAT))
    print("="*100)
    print(f"{'代理IP:端口':<22} {'成功率%':<8} {'平均延迟(ms)':<12} {'标准差(ms)':<10} {'最小/最大延迟':<16}")
    print("-"*100)
    for r in results[:30]:  # 显示前30个
        print(f"{r['proxy']:<22} {r['success_rate']:<8} {r['avg_speed_ms']:<12.1f} {r['std_speed_ms']:<10.1f} {r['min_speed_ms']}/{r['max_speed_ms']}")
    # 保存完整结果到 JSON
    with open(STABLE_REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    # 筛选推荐代理：成功率 > THRESHOLD 且平均延迟 < STABILITY_SPEED_THRESHOLD
    recommended = [r for r in results if r['success_rate'] >= STABILITY_SUCCESS_THRESHOLD and r['avg_speed_ms'] <= STABILITY_SPEED_THRESHOLD]
    if recommended:
        with open(STABLE_RECOMMENDED_FILE, 'w', encoding='utf-8') as f:
            f.write("# 推荐稳定代理列表 (成功率≥{}%, 平均延迟≤{}ms)\n".format(STABILITY_SUCCESS_THRESHOLD, STABILITY_SPEED_THRESHOLD))
            f.write("# 生成时间: {}\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            for r in recommended:
                f.write(f"{r['proxy']}  # 成功率{r['success_rate']}% 平均{r['avg_speed_ms']}ms\n")
        print(f"\n推荐稳定代理已保存至: {STABLE_RECOMMENDED_FILE}")
    print(f"\n完整稳定性报告已保存至: {STABLE_REPORT_FILE}")

# ==================== 主函数 ====================
def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("="*70)
    print("*** 海外免费代理自动搜索 + 稳定性测试工具 v6.0 ***")
    print("="*70)
    print(f"目标: {TEST_URL} | 速度阈值: {MIN_SPEED}ms | 稳定性重复次数: {STABILITY_TEST_REPEAT}")
    if STABILITY_TEST_ENABLED:
        print(f"稳定性测试: 开启 (对速度前100名代理进行 {STABILITY_TEST_REPEAT} 次重复测试)")
    else:
        print("稳定性测试: 关闭")
    print("="*70)

    # 1. 抓取并验证
    all_proxies = gather_all_proxies()
    if not all_proxies:
        cached = load_cache()
        if cached:
            all_proxies = cached
        else:
            print("无可用代理，退出")
            return
    valid_proxies = validate_proxies_for_target(all_proxies, TEST_URL)
    save_results(valid_proxies, TEST_URL)   # 保存基础结果

    # 2. 稳定性测试（仅对前100名）
    if STABILITY_TEST_ENABLED and valid_proxies:
        stable_results = run_stability_test(valid_proxies, TEST_URL, top_n=100)
        print_stability_report(stable_results)
    else:
        print("\n未执行稳定性测试（要么功能关闭，要么无有效代理）")

def save_results(valid_proxies, target_url):
    if not valid_proxies:
        return
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# 有效代理 (速度<{MIN_SPEED}ms) 按速度排序\n")
        for item in valid_proxies:
            f.write(f"{item['proxy']}  # {item['speed']}ms\n")
    json_file = OUTPUT_FILE.replace('.txt', '.json')
    with open(json_file, 'w') as f:
        json.dump(valid_proxies, f, indent=2)
    proxy_list = [item['proxy'] for item in valid_proxies]
    save_cache(proxy_list)
    print(f"[结果] 已保存 {len(valid_proxies)} 个高速代理至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()