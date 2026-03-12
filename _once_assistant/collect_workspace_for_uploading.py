#!/usr/bin/env python3
"""
Android 项目文件汇总工具
遍历 Android 项目目录，将指定文本类型文件的内容及路径输出到一个 TXT 文件中，
保留目录层级，过滤掉编译中间文件、二进制文件、版本控制文件和测试文件。
同时以树状结构显示包含和排除的文件列表。
"""

import os
import sys
import argparse

# 默认包含的文件扩展名（可根据项目调整）
DEFAULT_INCLUDE_EXTS = {
    '.java', '.kt', '.xml', '.gradle', '.properties', '.txt',
    '.md', '.cfg', '.conf', '.json', '.yaml', '.yml', '.kts',
    '.html', '.pro'
}

# 默认排除的目录名（匹配任意路径段）
DEFAULT_EXCLUDE_DIRS = {
    'build', '.gradle', '.idea', '.git', '.svn', 'out', 'bin', 'gen',
    'captures', '.settings', 'gradle', 'wrapper', '.cxx', 'release',
    'test', 'androidTest'
}

# 默认排除的文件扩展名（二进制或编译产物）
DEFAULT_EXCLUDE_EXTS = {
    '.class', '.dex', '.apk', '.aar', '.jar', '.so', '.dll', '.png', '.jpg',
    '.jpeg', '.gif', '.bmp', '.webp', '.mp4', '.mp3', '.wav', '.ogg',
    '.zip', '.tar', '.gz', '.7z', '.ico', '.ttf', '.otf', '.keystore'
}

# ===== 新增：默认排除的特定文件名 =====
DEFAULT_EXCLUDE_FILES = {'local.properties'}

def should_exclude(path, root, include_exts=None, exclude_dirs=None, exclude_exts=None, exclude_files=None):
    """
    判断文件是否应被排除，并返回排除原因。
    :param path: 文件的完整路径
    :param root: 遍历的根目录（用于计算相对路径）
    :param include_exts: 包含的扩展名集合（若指定，则不在其中的文件排除）
    :param exclude_dirs: 排除的目录名集合
    :param exclude_exts: 排除的扩展名集合（与 include_exts 二选一）
    :param exclude_files: 排除的特定文件名集合（例如 {'local.properties'}）
    :return: (True/False, reason_string or None)
    """
    rel_path = os.path.relpath(path, root)
    parts = rel_path.split(os.sep)

    # 检查路径中是否有排除目录
    if exclude_dirs:
        for part in parts[:-1]:  # 只检查目录部分
            if part in exclude_dirs:
                return True, f"匹配排除目录 '{part}'"

    # ===== 新增：检查文件名是否在排除列表中 =====
    filename = os.path.basename(path)
    if exclude_files and filename in exclude_files:
        return True, f"匹配排除文件名 '{filename}'"

    # 如果是文件，检查扩展名
    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        # 如果指定了包含扩展名，则只保留这些扩展名
        if include_exts is not None:
            if ext not in include_exts:
                return True, f"扩展名 '{ext}' 不在包含列表中"
        # 如果指定了排除扩展名，则排除这些扩展名
        elif exclude_exts is not None:
            if ext in exclude_exts:
                return True, f"扩展名 '{ext}' 在排除列表中"

    # 默认保留
    return False, None

def collect_files(root_dir, include_exts=None, exclude_dirs=None, exclude_exts=None, exclude_files=None):
    """
    遍历目录，收集包含和排除的文件相对路径列表。
    :return: (included_paths, excluded_paths) 每个元素是相对路径字符串
    """
    included = []
    excluded = []
    for root, dirs, files in os.walk(root_dir):
        # 修改 dirs 以跳过排除目录（提升效率）
        if exclude_dirs:
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            file_path = os.path.join(root, file)
            excluded_flag, _ = should_exclude(file_path, root_dir, include_exts, exclude_dirs, exclude_exts, exclude_files)
            rel_path = os.path.relpath(file_path, root_dir)
            if excluded_flag:
                excluded.append(rel_path)
            else:
                included.append(rel_path)
    return included, excluded

def write_summary(output_file, root_dir, file_paths):
    """
    将文件内容写入汇总文件
    :param output_file: 输出文件路径
    :param root_dir: 项目根目录
    :param file_paths: 包含的相对路径列表（可迭代）
    """
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for rel_path in file_paths:
            abs_path = os.path.join(root_dir, rel_path)
            # 写入文件头（包含相对路径）
            out_f.write(f"\n{'='*60}\n")
            out_f.write(f"File: {rel_path}\n")
            out_f.write(f"{'='*60}\n\n")

            try:
                # 尝试以 UTF-8 读取文件内容
                with open(abs_path, 'r', encoding='utf-8') as in_f:
                    content = in_f.read()
                out_f.write(content)
                out_f.write("\n")  # 确保末尾换行
            except UnicodeDecodeError:
                # 如果解码失败，说明可能是二进制文件（虽然已过滤，但以防万一）
                out_f.write("[ERROR: Unable to read file content (binary or encoding issue)]\n")
            except Exception as e:
                out_f.write(f"[ERROR: Failed to read file - {e}]\n")

    print(f"Summary written to {output_file}")

def print_tree(paths, root_name, title=None):
    """
    以树状结构打印文件列表
    :param paths: 相对路径列表
    :param root_name: 项目根目录名称（用于显示）
    :param title: 可选的标题
    """
    if not paths:
        print(f"{title} 无文件" if title else "无文件")
        return

    if title:
        print(title)

    # 构建嵌套字典树
    root = {}
    for path in sorted(paths):
        parts = path.split(os.sep)
        node = root
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
        # 最后一个部分是文件名
        filename = parts[-1]
        node[filename] = None  # 标记为文件

    def _print(node, prefix=''):
        items = sorted(node.items())
        for i, (name, subtree) in enumerate(items):
            is_last = (i == len(items) - 1)
            if subtree is None:
                # 文件
                print(prefix + ('└── ' if is_last else '├── ') + name)
            else:
                # 目录
                print(prefix + ('└── ' if is_last else '├── ') + name + '/')
                # 递归，增加缩进
                _print(subtree, prefix + ('    ' if is_last else '│   '))

    print(root_name + '/')
    _print(root, prefix='    ')

def main():
    parser = argparse.ArgumentParser(description='汇总 Android 项目文件到单个文本文件，并显示文件树。')
    parser.add_argument('project_dir', help='Android 项目根目录路径')
    parser.add_argument('-o', '--output', default='project_summary.txt',
                        help='输出文件路径（默认：project_summary.txt）')
    parser.add_argument('--include-exts', nargs='+', default=None,
                        help='要包含的文件扩展名列表（例如 .java .kt .xml），若不指定则使用默认集合')
    parser.add_argument('--exclude-dirs', nargs='+', default=None,
                        help='要排除的目录名列表（例如 build .gradle），若不指定则使用默认集合')
    parser.add_argument('--exclude-exts', nargs='+', default=None,
                        help='要排除的文件扩展名列表（例如 .class .dex），通常与 --include-exts 互斥')
    # ===== 新增：排除特定文件名参数 =====
    parser.add_argument('--exclude-files', nargs='+', default=None,
                        help='要排除的特定文件名列表（例如 local.properties），若不指定则使用默认集合')
    parser.add_argument('--show-excluded', action=argparse.BooleanOptionalAction, default=True,
                        help='是否显示被排除的文件树（默认显示）')
    args = parser.parse_args()

    # 处理参数默认值
    include_exts = set(args.include_exts) if args.include_exts else DEFAULT_INCLUDE_EXTS
    exclude_dirs = set(args.exclude_dirs) if args.exclude_dirs else DEFAULT_EXCLUDE_DIRS
    exclude_exts = set(args.exclude_exts) if args.exclude_exts else None
    # ===== 新增：处理排除文件名默认值 =====
    exclude_files = set(args.exclude_files) if args.exclude_files else DEFAULT_EXCLUDE_FILES

    # 如果同时指定了包含和排除，优先使用包含（排除会被忽略）
    if args.include_exts and args.exclude_exts:
        print("警告：同时指定了 --include-exts 和 --exclude-exts，将使用包含列表，排除列表被忽略。")
        exclude_exts = None

    # 检查项目目录是否存在
    if not os.path.isdir(args.project_dir):
        print(f"错误：项目目录 '{args.project_dir}' 不存在。")
        sys.exit(1)

    print(f"正在扫描目录: {args.project_dir}")
    included, excluded = collect_files(args.project_dir, include_exts, exclude_dirs, exclude_exts, exclude_files)

    # 获取根目录名称用于树状显示
    root_name = os.path.basename(args.project_dir.rstrip('/\\')) or args.project_dir

    # 打印包含的文件树
    print_tree(included, root_name, title="\n📄 汇总的文件列表：")

    # 如果需要，打印排除的文件树
    if args.show_excluded:
        print_tree(excluded, root_name, title="\n🚫 排除的文件列表：")

    # 写入汇总文件
    write_summary(args.output, args.project_dir, included)

if __name__ == '__main__':
    main()