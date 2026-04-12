#!/usr/bin/env python3
"""
Android 项目文件汇总工具（仅使用 .gitignore 规则）
遍历 Android 项目目录，将文本文件的内容及路径输出到一个 TXT 文件中，
完全遵循 .gitignore 规则来过滤文件。
如果项目根目录下没有 .gitignore 文件，则尝试使用本脚本所在目录下的 .gitignore 作为全局规则。
"""

import os
import sys
import argparse
import re
from pathlib import Path


class GitIgnoreParser:
    """解析 .gitignore 文件，提供路径匹配功能"""

    def __init__(self, gitignore_path):
        self.patterns = []
        self.base_dir = os.path.dirname(gitignore_path)
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
                    print(f"警告：无法编译正则表达式 '{regex}' (来自模式 '{original_pattern}')")

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

    def is_ignored(self, rel_path):
        rel_path = rel_path.replace(os.sep, '/')
        for pattern in self.patterns:
            if pattern.search(rel_path):
                print(f"[DEBUG] 匹配成功: {rel_path} 匹配规则 {pattern.pattern}")  # 加这行
                return True
        return False


def load_gitignore_rules(root_dir, script_dir):
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
        rules[str(gitignore_path.parent)] = GitIgnoreParser(gitignore_path)
        print(f"  加载规则: {gitignore_path}")

    # 2. 如果根目录没有 .gitignore，尝试使用脚本目录下的 .gitignore 作为全局规则
    if root_dir not in rules:
        global_gitignore = os.path.join(script_dir, '.gitignore')
        if os.path.exists(global_gitignore):
            print(f"  项目根目录下无 .gitignore，使用全局规则: {global_gitignore}")
            rules[root_dir] = GitIgnoreParser(global_gitignore)

    return rules


def is_text_file(file_path):
    """判断文件是否为文本文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)
        return True
    except (UnicodeDecodeError, IOError):
        return False


def should_exclude(path, root, gitignore_rules):
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
            if gitignore_rules[current].is_ignored(rel):
                return True
        if current == abs_root:
            break
        current = os.path.dirname(current)
    return False


def collect_files(root_dir, script_dir):
    """收集文件，遵循 .gitignore 规则"""
    print("正在加载 .gitignore 规则...")
    gitignore_rules = load_gitignore_rules(root_dir, script_dir)

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
            if should_exclude(dir_path, root_dir, gitignore_rules):
                skip_dirs.append(d)
                rel_path = os.path.relpath(dir_path, root_dir)
                excluded.append(rel_path + '/')
                # print(f"排除目录: {rel_path}/")

        # 更新 dirs 以跳过被排除的目录
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        # 处理文件
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, root_dir)

            if should_exclude(file_path, root_dir, gitignore_rules):
                excluded.append(rel_path)
                # print(f"排除文件: {rel_path}")
            elif is_text_file(file_path):
                included.append(rel_path)
            else:
                excluded.append(rel_path)

    return included, excluded


def write_summary(output_file, root_dir, file_paths):
    """写入汇总文件"""
    if not file_paths:
        print("警告：没有文件被包含，不生成汇总文件")
        return

    with open(output_file, 'w', encoding='utf-8') as out_f:
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

    print(f"汇总文件已写入: {output_file}")


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


def main():
    parser = argparse.ArgumentParser(
        description='Android 项目文件汇总工具（完全遵循 .gitignore 规则）'
    )
    parser.add_argument('project_dir', help='项目根目录路径')
    parser.add_argument('-o', '--output', default='project_summary.txt',
                        help='输出文件路径（默认：project_summary.txt）')
    parser.add_argument('--show-excluded', action='store_true',
                        help='显示被排除的文件列表')
    parser.add_argument('--max-tree-items', type=int, default=100,
                        help='树状显示的最大文件数量（默认：100）')
    parser.add_argument('--debug', action='store_true',
                        help='显示调试信息')
    args = parser.parse_args()

    if not os.path.isdir(args.project_dir):
        print(f"错误：目录 '{args.project_dir}' 不存在")
        sys.exit(1)

    print(f"扫描目录: {args.project_dir}")

    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    included, excluded = collect_files(args.project_dir, script_dir)

    root_name = os.path.basename(args.project_dir.rstrip('/\\')) or args.project_dir

    print_tree(included, root_name, "\n📄 包含的文件：", args.max_tree_items)

    if args.show_excluded:
        print_tree(excluded, root_name, "\n🚫 排除的文件：", args.max_tree_items)

    if included:
        write_summary(args.output, args.project_dir, included)
    else:
        print("警告：没有找到任何文本文件")

    print(f"\n📊 统计: 包含 {len(included)} 个文本文件, 排除 {len(excluded)} 个文件")


if __name__ == '__main__':
    main()