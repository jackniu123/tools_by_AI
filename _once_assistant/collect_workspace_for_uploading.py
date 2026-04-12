#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android 项目文件汇总工具（仅使用 .gitignore 规则）
遍历 Android 项目目录，将文本文件的内容及路径输出到一个 TXT 文件中，
完全遵循 .gitignore 规则来过滤文件。
如果项目根目录下没有 .gitignore 文件，则尝试使用本脚本所在目录下的 .gitignore 作为全局规则。

功能特性：
- 支持 .gitignore 规则过滤
- 自动包含 AI_coding_requirement.txt 通用需求说明
- 完整的日志系统（文件 + 控制台）
- 支持配置文件配置敏感信息
- 符合开源代码安全规范
"""

import os
import sys
import argparse
import re
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
import json


# ============================================================
# 日志系统配置
# ============================================================

def setup_logging(script_name):
    """
    配置日志系统
    日志保存路径: C:/Users/Administrator/._my_python_tools/{script_name}/
    日志轮转: 单个文件最大 10MB，保留 5 个备份
    同时输出到控制台和文件
    """
    # 日志基础目录
    log_base_dir = Path("C:/Users/Administrator/._my_python_tools") / script_name
    log_base_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_base_dir / f"{script_name}.log"

    # 创建 logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # 清除已有的处理器，避免重复
    logger.handlers.clear()

    # 文件处理器（带轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# ============================================================
# 配置文件管理
# ============================================================

class ConfigManager:
    """配置文件管理器，用于读取敏感信息和用户配置"""

    DEFAULT_CONFIG = {
        "output": {
            "default_output_name": "project_summary.txt",
            "max_tree_items": 100
        },
        "paths": {
            "log_base_dir": "C:/Users/Administrator/._my_python_tools"
        }
    }

    def __init__(self, config_path=None):
        self.config = self.DEFAULT_CONFIG.copy()
        if config_path and Path(config_path).exists():
            self._load_config(config_path)

    def _load_config(self, config_path):
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # 深度合并配置
                self._merge_config(self.config, user_config)
            logging.getLogger(__name__).info(f"已加载配置文件: {config_path}")
        except Exception as e:
            logging.getLogger(__name__).warning(f"加载配置文件失败: {e}，使用默认配置")

    def _merge_config(self, base, update):
        """递归合并配置字典"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def get(self, key, default=None):
        """获取配置项，支持点号分隔的路径，如 'output.default_output_name'"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value


# ============================================================
# 需求文档加载
# ============================================================

def load_requirements(script_dir):
    """加载同级的 AI_coding_requirement.txt 通用需求文件"""
    req_file = Path(script_dir) / "AI_coding_requirement.txt"
    if req_file.exists():
        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                content = f.read()
            logger = logging.getLogger(__name__)
            logger.info(f"已加载需求文档: {req_file}")
            return content
        except Exception as e:
            logger.warning(f"加载需求文档失败: {e}")
            return f"# 需求文档加载失败: {e}"
    else:
        return "# 未找到 AI_coding_requirement.txt 文件"


# ============================================================
# GitIgnore 解析器
# ============================================================

class GitIgnoreParser:
    """解析 .gitignore 文件，提供路径匹配功能"""

    def __init__(self, gitignore_path, logger=None):
        self.patterns = []
        self.base_dir = os.path.dirname(gitignore_path)
        self.logger = logger or logging.getLogger(__name__)
        if os.path.exists(gitignore_path):
            self._parse(gitignore_path)

    def _parse(self, gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('!'):
                    continue

                # 保存原始模式
                original_pattern = line
                is_dir_pattern = line.endswith('/')

                # 移除末尾的斜杠用于匹配
                if is_dir_pattern:
                    line = line[:-1]

                # 转换通配符为正则
                regex = self._glob_to_regex(line)

                # 处理路径匹配规则（与 git 行为一致）
                if line.startswith('/'):
                    # 以 / 开头：只匹配根目录（相对于 .gitignore 所在目录）
                    regex = '^' + regex[1:]
                else:
                    # 不以 / 开头：匹配任意深度
                    regex = '(^|.*/)' + regex

                # 目录模式：匹配目录及其所有内容
                if is_dir_pattern:
                    regex += '(/.*)?$'
                else:
                    regex += '$'

                try:
                    self.patterns.append(re.compile(regex))
                except re.error:
                    self.logger.warning(f"无法编译正则表达式 '{regex}' (来自模式 '{original_pattern}')")

    def _glob_to_regex(self, pattern):
        """将 glob 模式转换为正则表达式"""
        regex = []
        i = 0
        while i < len(pattern):
            if pattern[i] == '*':
                if i + 1 < len(pattern) and pattern[i + 1] == '*':
                    regex.append('.*')
                    i += 2
                else:
                    regex.append('[^/]*')
                    i += 1
            elif pattern[i] == '?':
                regex.append('[^/]')
                i += 1
            elif pattern[i] == '/':
                regex.append('/')
                i += 1
            elif pattern[i] == '.':
                regex.append(r'\.')
                i += 1
            elif pattern[i] in '[]{}()+-|^$\\':
                regex.append(re.escape(pattern[i]))
                i += 1
            else:
                regex.append(pattern[i])
                i += 1
        return ''.join(regex)

    def is_ignored(self, rel_path, debug=False):
        """判断路径是否应该被忽略"""
        rel_path = rel_path.replace(os.sep, '/')
        for pattern in self.patterns:
            if pattern.search(rel_path):
                if debug:
                    self.logger.debug(f"匹配成功: {rel_path} 匹配规则 {pattern.pattern}")
                return True
        return False


# ============================================================
# 核心功能函数
# ============================================================

def load_gitignore_rules(root_dir, script_dir, logger):
    """
    加载项目中所有的 .gitignore 规则。
    如果项目根目录下没有 .gitignore，则尝试使用脚本所在目录下的 .gitignore 作为全局规则。
    """
    rules = {}
    # 1. 加载项目中的所有 .gitignore
    for gitignore_path in Path(root_dir).rglob('.gitignore'):
        # 跳过 .git 目录中的 .gitignore
        if '/.git/' in str(gitignore_path) or '\\.git\\' in str(gitignore_path):
            continue
        rules[str(gitignore_path.parent)] = GitIgnoreParser(gitignore_path, logger)
        logger.info(f"加载规则: {gitignore_path}")

    # 2. 如果根目录没有 .gitignore，尝试使用脚本目录下的 .gitignore 作为全局规则
    if root_dir not in rules:
        global_gitignore = os.path.join(script_dir, '.gitignore')
        if os.path.exists(global_gitignore):
            logger.info(f"项目根目录下无 .gitignore，使用全局规则: {global_gitignore}")
            rules[root_dir] = GitIgnoreParser(global_gitignore, logger)

    return rules


def is_text_file(file_path):
    """判断文件是否为文本文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)
        return True
    except (UnicodeDecodeError, IOError):
        return False


def should_exclude(path, root, gitignore_rules, logger, debug=False):
    """根据 .gitignore 规则判断文件或目录是否应被排除"""
    # 跳过 .git 目录
    if '.git' in Path(path).parts:
        return True

    abs_path = os.path.abspath(path)
    abs_root = os.path.abspath(root)

    # 确定起始检查目录：如果是文件，从父目录开始；如果是目录，从自身开始
    start_dir = os.path.dirname(abs_path) if os.path.isfile(abs_path) else abs_path

    # 逐级向上检查，直到根目录
    current = start_dir
    while current >= abs_root:
        if current in gitignore_rules:
            rel = os.path.relpath(abs_path, current)
            if gitignore_rules[current].is_ignored(rel, debug):
                if debug:
                    logger.debug(f"文件/目录被排除: {abs_path}")
                return True
        if current == abs_root:
            break
        current = os.path.dirname(current)
    return False


def collect_files(root_dir, script_dir, logger, debug=False):
    """收集文件，遵循 .gitignore 规则"""
    logger.info("正在加载 .gitignore 规则...")
    gitignore_rules = load_gitignore_rules(root_dir, script_dir, logger)

    included = []
    excluded = []

    for root, dirs, files in os.walk(root_dir):
        # 过滤被排除的目录
        skip_dirs = []
        for d in dirs:
            # 跳过 .git 目录
            if d == '.git':
                skip_dirs.append(d)
                continue

            dir_path = os.path.join(root, d)
            if should_exclude(dir_path, root_dir, gitignore_rules, logger, debug):
                skip_dirs.append(d)
                rel_path = os.path.relpath(dir_path, root_dir)
                excluded.append(rel_path + '/')
                if debug:
                    logger.debug(f"排除目录: {rel_path}/")

        # 更新 dirs 以跳过被排除的目录
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        # 处理文件
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, root_dir)

            if should_exclude(file_path, root_dir, gitignore_rules, logger, debug):
                excluded.append(rel_path)
                if debug:
                    logger.debug(f"排除文件: {rel_path}")
            elif is_text_file(file_path):
                included.append(rel_path)
            else:
                excluded.append(rel_path)
                if debug:
                    logger.debug(f"非文本文件排除: {rel_path}")

    logger.info(f"收集完成: 包含 {len(included)} 个文件, 排除 {len(excluded)} 个文件")
    return included, excluded


def write_summary(output_file, root_dir, file_paths, requirements_content, logger):
    """写入汇总文件，包含需求文档内容"""
    if not file_paths:
        logger.warning("没有文件被包含，不生成汇总文件")
        return

    with open(output_file, 'w', encoding='utf-8') as out_f:
        # 写入文件头部信息
        out_f.write("=" * 80 + "\n")
        out_f.write("Android 项目文件汇总工具 - 输出文件\n")
        out_f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out_f.write("=" * 80 + "\n\n")

        # 写入需求文档内容
        out_f.write("-" * 60 + "\n")
        out_f.write("通用需求说明 (来自 AI_coding_requirement.txt)\n")
        out_f.write("-" * 60 + "\n\n")
        out_f.write(requirements_content)
        out_f.write("\n\n" + "-" * 60 + "\n")
        out_f.write("项目文件内容\n")
        out_f.write("-" * 60 + "\n\n")

        # 写入各个文件内容
        for rel_path in file_paths:
            abs_path = os.path.join(root_dir, rel_path)
            out_f.write(f"\n{'=' * 60}\n")
            out_f.write(f"File: {rel_path}\n")
            out_f.write(f"{'=' * 60}\n\n")

            try:
                with open(abs_path, 'r', encoding='utf-8') as in_f:
                    out_f.write(in_f.read())
                out_f.write("\n")
            except Exception as e:
                out_f.write(f"[ERROR: {e}]\n")
                logger.error(f"读取文件失败 {rel_path}: {e}")

    logger.info(f"汇总文件已写入: {output_file}")


def print_tree(paths, root_name, title=None, max_items=100):
    """打印树状结构"""
    if not paths:
        if title:
            print(f"{title} 无文件")
        return

    if title:
        print(title)

    # 如果文件太多，只显示前 max_items 个
    if len(paths) > max_items:
        print(f"  (共 {len(paths)} 个文件/目录，只显示前 {max_items} 个)")
        paths = paths[:max_items]

    # 构建树
    tree = {}
    for path_str in paths:
        # 移除末尾的斜杠用于构建树
        display_path = path_str.rstrip('/')
        parts = display_path.split(os.sep)
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None

    def _print(node, prefix=''):
        items = sorted(node.items())
        for i, (name, subtree) in enumerate(items):
            is_last = i == len(items) - 1
            if subtree is None:
                print(prefix + ('└── ' if is_last else '├── ') + name)
            else:
                print(prefix + ('└── ' if is_last else '├── ') + name + '/')
                _print(subtree, prefix + ('    ' if is_last else '│   '))

    print(root_name + '/')
    _print(tree, prefix='    ')


def create_default_config(script_dir):
    """创建默认配置文件（如果不存在）"""
    config_path = Path(script_dir) / "config.json"
    if not config_path.exists():
        default_config = {
            "output": {
                "default_output_name": "project_summary.txt",
                "max_tree_items": 100
            },
            "paths": {
                "log_base_dir": "C:/Users/Administrator/._my_python_tools"
            },
            "gitignore": {
                "enable_global_fallback": True
            }
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            logging.getLogger(__name__).info(f"已创建默认配置文件: {config_path}")
        except Exception as e:
            logging.getLogger(__name__).warning(f"创建配置文件失败: {e}")


# ============================================================
# 主函数
# ============================================================

def main():
    # 获取脚本名称（不含扩展名）
    script_name = Path(__file__).stem

    # 初始化日志系统
    logger = setup_logging(script_name)
    logger.info("=" * 60)
    logger.info(f"启动 {script_name} 工具")
    logger.info("=" * 60)

    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 创建默认配置文件（如果不存在）
    create_default_config(script_dir)

    # 加载配置文件
    config_path = Path(script_dir) / "config.json"
    config = ConfigManager(config_path)

    # 加载需求文档
    requirements_content = load_requirements(script_dir)

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='通用项目文件汇总工具（完全遵循 .gitignore 规则）'
    )
    parser.add_argument('project_dir', help='项目根目录路径')
    parser.add_argument('-o', '--output',
                        default=config.get('output.default_output_name', 'project_summary.txt'),
                        help='输出文件路径（默认：project_summary.txt）')
    parser.add_argument('--show-excluded', action='store_true',
                        help='显示被排除的文件列表')
    parser.add_argument('--max-tree-items', type=int,
                        default=config.get('output.max_tree_items', 100),
                        help='树状显示的最大文件数量（默认：100）')
    parser.add_argument('--debug', action='store_true',
                        help='显示调试信息')
    args = parser.parse_args()

    # 设置调试模式
    if args.debug:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("调试模式已开启")

    # 检查项目目录是否存在
    if not os.path.isdir(args.project_dir):
        logger.error(f"目录 '{args.project_dir}' 不存在")
        sys.exit(1)

    logger.info(f"扫描目录: {args.project_dir}")

    # 收集文件
    included, excluded = collect_files(args.project_dir, script_dir, logger, args.debug)

    # 显示结果树
    root_name = os.path.basename(args.project_dir.rstrip('/\\')) or args.project_dir
    print_tree(included, root_name, "\n📄 包含的文件：", args.max_tree_items)

    if args.show_excluded:
        print_tree(excluded, root_name, "\n🚫 排除的文件：", args.max_tree_items)

    # 写入汇总文件
    if included:
        write_summary(args.output, args.project_dir, included, requirements_content, logger)
    else:
        logger.warning("没有找到任何文本文件")

    logger.info(f"📊 统计: 包含 {len(included)} 个文本文件, 排除 {len(excluded)} 个文件")
    logger.info("工具执行完成")


if __name__ == '__main__':
    main()