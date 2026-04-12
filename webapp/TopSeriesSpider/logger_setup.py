# -*- coding: utf-8 -*-
"""
日志初始化模块
根据配置设置日志输出到控制台和文件，文件采用轮转策略
"""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config_loader import cfg


def setup_logger(script_name: str) -> logging.Logger:
    """
    设置日志系统
    :param script_name: 脚本名（不含扩展名），用于创建子目录
    :return: 配置好的logger对象
    """
    # 创建日志目录：C:/Users/Administrator/._my_python_tools/script_name/
    log_dir = Path(cfg.log_root) / script_name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{script_name}.log"

    # 获取根日志记录器
    logger = logging.getLogger(script_name)
    logger.setLevel(getattr(logging, cfg.log_level.upper()))

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(cfg.log_console_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器（轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=cfg.log_max_bytes,
        backupCount=cfg.log_backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(cfg.log_file_format)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.info(f"日志系统初始化完成，日志文件: {log_file}")
    return logger