# -*- coding: utf-8 -*-
"""
配置加载模块
从 config.ini 读取配置，并提供统一的配置对象
若配置文件不存在，则自动创建默认配置
"""
import os
import configparser
from pathlib import Path


class Config:
    def __init__(self):
        # 关键修改：禁用插值，避免日志格式字符串被误解析
        self.config = configparser.ConfigParser(interpolation=None)
        self.base_dir = Path(__file__).parent.resolve()
        config_file = self.base_dir / "config.ini"

        # 如果配置文件不存在，创建默认配置
        if not config_file.exists():
            self._create_default_config(config_file)

        self.config.read(config_file, encoding='utf-8')

        # 解析 User-Agent 列表
        ua_str = self.config.get('spider', 'user_agents', fallback='')
        self.user_agents = [ua.strip() for ua in ua_str.split(',') if ua.strip()]
        if not self.user_agents:
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]

        # 搜索关键词模板
        queries_str = self.config.get('spider', 'search_queries', fallback='{series_name} 1080p')
        self.search_queries = [q.strip() for q in queries_str.split(',') if q.strip()]

        # 其他配置
        self.max_results_per_query = self.config.getint('spider', 'max_results_per_query', fallback=10)
        self.max_test_links = self.config.getint('spider', 'max_test_links', fallback=5)
        self.min_speed_kbps = self.config.getfloat('spider', 'min_speed_kbps', fallback=200)
        self.speed_test_size_bytes = self.config.getint('spider', 'speed_test_size_bytes', fallback=1048576)

        # 日志配置
        self.log_level = self.config.get('logging', 'level', fallback='INFO')
        self.log_console_format = self.config.get('logging', 'console_format',
                                                  fallback='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_file_format = self.config.get('logging', 'file_format',
                                               fallback='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_max_bytes = self.config.getint('logging', 'max_bytes', fallback=10485760)
        self.log_backup_count = self.config.getint('logging', 'backup_count', fallback=5)

        # 路径配置
        self.log_root = self.config.get('paths', 'log_root', fallback='C:/Users/Administrator/._my_python_tools')

        # 在 __init__ 中，读取 TMDB 配置
        self.use_tmdb = self.config.getboolean('spider', 'use_tmdb', fallback=True)
        self.tmdb_api_key = self.config.get('spider', 'tmdb_api_key', fallback='')
        self.language = self.config.get('spider', 'language', fallback='zh-CN')

        # 解析播放源
        sources_str = self.config.get('play_sources', 'sources', fallback='')
        self.play_sources = []
        if sources_str:
            for item in sources_str.split(','):
                parts = item.strip().split('|')
                if len(parts) == 2:
                    self.play_sources.append((parts[0].strip(), parts[1].strip()))

    def _create_default_config(self, config_file: Path):
        """创建默认配置文件"""
        default_content = """[spider]
# User-Agent列表，每个一行，用逗号分隔
user_agents = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36, Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36, Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
# 搜索关键词模板（占位符 {series_name}）
search_queries = {series_name} 1080p, {series_name} complete series, {series_name} bluray
# 每个关键词最多获取的磁力链接数
max_results_per_query = 10
# 测试链接数量上限
max_test_links = 5
# 最小下载速度（KB/s）
min_speed_kbps = 200
# 测试下载的数据量（字节），用于速度估算
speed_test_size_bytes = 1048576

[logging]
# 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
level = INFO
# 控制台输出格式
console_format = %(asctime)s - %(name)s - %(levelname)s - %(message)s
# 文件输出格式
file_format = %(asctime)s - %(name)s - %(levelname)s - %(message)s
# 单个日志文件最大大小（字节）
max_bytes = 10485760
# 备份文件数
backup_count = 5

[paths]
# 日志保存根目录（会根据脚本名自动创建子目录）
log_root = C:/Users/Administrator/._my_python_tools
"""
        config_file.write_text(default_content, encoding='utf-8')
        print(f"已创建默认配置文件: {config_file}")

    def get_user_agent(self):
        """随机获取一个User-Agent"""
        import random
        return random.choice(self.user_agents)


# 创建全局配置实例
cfg = Config()