# -*- coding: utf-8 -*-
"""
PC 向手机发送提醒模块（Server 酱微信版 + Qmsg QQ版）

功能：
    - 通过 Server 酱将消息推送到微信
    - 通过 Qmsg 酱将消息推送到 QQ（支持默认接收者配置）
    - 提供统一的外部调用接口
    - 安全设计：敏感信息从配置文件读取
    - 日志：同时输出到控制台和文件（轮转，10MB，保留5个备份）

文件路径：
    基础目录: C:/Users/Administrator/._my_python_tools/notifier_to_phone/
    配置文件: 基础目录/config.ini
    日志文件: 基础目录/logs/pc_reminder.log

使用示例：
    from notifier_to_phone import send_reminder_wechat, send_reminder_qq
    send_reminder_wechat("微信提醒", title="通知")
    send_reminder_qq("QQ提醒", title="通知")  # 使用配置中的默认QQ
    send_reminder_qq("私密消息", to="123456789")  # 指定QQ

依赖：
    requests (安装: pip install requests)
"""

import os
import sys
import logging
import configparser
from logging.handlers import RotatingFileHandler
from logging import StreamHandler
from pathlib import Path

import requests

# ---------- 路径配置 ----------
current_script_name = Path(__file__).stem
BASE_DIR = Path.home() / "._my_python_tools" / current_script_name
LOG_DIR = BASE_DIR / "logs"
CONFIG_FILE = BASE_DIR / "config.ini"

# 确保目录存在
BASE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ---------- 日志配置（控制台 + 文件，只执行一次）----------
def _setup_logging():
    """配置日志：同时输出到控制台和文件，文件自动轮转"""
    log_file = LOG_DIR / "pc_reminder.log"
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )

    # 控制台处理器
    console_handler = StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（轮转）
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logging.info("日志系统初始化完成，文件路径：%s", log_file)


_setup_logging()
logger = logging.getLogger(__name__)


# ---------- 配置读取 ----------
def _load_config():
    """
    读取配置文件，返回完整配置字典
    配置文件格式：
        [serverchan]
        sendkey = 你的Server酱SendKey

        [qmsg]
        key = 你的Qmsg密钥
        default_qq = 可选，默认接收QQ号（如 123456789）
    """
    config = configparser.ConfigParser()
    try:
        if not CONFIG_FILE.exists():
            # 创建配置文件模板
            config['serverchan'] = {'sendkey': '你的Server酱SendKey'}
            config['qmsg'] = {
                'key': '你的Qmsg密钥',
                'default_qq': ''  # 可选，用户可以留空
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                config.write(f)
            logger.error(f"配置文件不存在，已创建模板：{CONFIG_FILE}")
            logger.error("请编辑该文件，填入正确的密钥后重新运行程序。")
            logger.error("Server酱获取：https://sct.ftqq.com")
            logger.error("Qmsg酱获取：https://qmsg.zendee.cn")
            logger.error("如果希望使用默认QQ接收，请在 [qmsg] 中设置 default_qq")
            return None
        config.read(CONFIG_FILE, encoding='utf-8')
        return config
    except Exception as e:
        logger.error(f"配置文件读取失败: {e}")
        return None


# ---------- Server酱微信通知器 ----------
class ServerChanNotifier:
    """通过 Server 酱发送微信通知"""

    def __init__(self, sendkey: str):
        self.sendkey = sendkey
        self.api_url = f"https://sctapi.ftqq.com/{sendkey}.send"
        logger.info("Server酱通知器初始化完成")

    def send(self, message: str, title: str = "PC提醒", to: str = None) -> bool:
        """发送微信通知"""
        logger.info(f"准备发送微信通知，标题: {title}")
        try:
            data = {'title': title, 'desp': message}
            resp = requests.post(self.api_url, data=data, timeout=10)
            result = resp.json()
            if resp.status_code == 200 and result.get('code') == 0:
                logger.info(f"微信通知发送成功: {title}")
                return True
            else:
                logger.error(f"Server酱返回错误: {result.get('message', resp.text)}")
                return False
        except requests.RequestException as e:
            logger.error(f"微信通知网络请求异常: {e}")
            return False
        except Exception as e:
            logger.error(f"微信通知未知异常: {e}")
            return False


# ---------- Qmsg酱QQ通知器 ----------
class QmsgNotifier:
    """通过 Qmsg 酱发送 QQ 通知（支持默认接收者）"""

    def __init__(self, key: str, default_qq: str = None):
        """
        :param key: Qmsg 的密钥，从 https://qmsg.zendee.cn 获取
        :param default_qq: 默认接收QQ号，如果调用时未指定 to 则使用此值
        """
        self.key = key
        self.default_qq = default_qq
        self.api_url = f"https://qmsg.zendee.cn/send/{key}"
        logger.info("Qmsg酱通知器初始化完成" + (f"，默认QQ: {default_qq}" if default_qq else ""))

    def send(self, message: str, title: str = None, to: str = None) -> bool:
        """
        发送 QQ 通知
        :param message: 消息内容
        :param title: 可选标题，将与消息合并
        :param to: 指定QQ号，若为 None 则使用 self.default_qq
        :return: 是否发送成功
        """
        # 确定接收者
        target_qq = to or self.default_qq
        if target_qq is None:
            logger.error("未指定接收QQ号，且配置文件中未设置 default_qq")
            return False

        # 如果传入了标题，将标题和消息合并
        full_message = f"{title}\n{message}" if title else message
        logger.info(f"准备发送QQ通知到 {target_qq}，消息长度: {len(full_message)}")
        try:
            data = {'msg': full_message, 'qq': target_qq}
            resp = requests.post(self.api_url, data=data, timeout=10)
            result = resp.json()
            if resp.status_code == 200 and result.get('code') == 0:
                logger.info("QQ通知发送成功")
                return True
            else:
                error_msg = result.get('reason', resp.text)
                logger.error(f"Qmsg返回错误: {error_msg}")
                # 针对特定错误给出建议
                if "没有选择Qmsg酱" in error_msg:
                    logger.error("请检查Qmsg平台是否已添加接收QQ号，或在配置文件中设置 default_qq")
                return False
        except requests.RequestException as e:
            logger.error(f"QQ通知网络请求异常: {e}")
            return False
        except Exception as e:
            logger.error(f"QQ通知未知异常: {e}")
            return False


# ---------- 全局单例通知器 ----------
_config = _load_config()
_serverchan_instance = None
_qmsg_instance = None


def _get_serverchan():
    """获取Server酱单例"""
    global _serverchan_instance
    if _serverchan_instance is None and _config is not None:
        try:
            sendkey = _config.get('serverchan', 'sendkey')
            if sendkey and sendkey != '你的Server酱SendKey':
                _serverchan_instance = ServerChanNotifier(sendkey)
                logger.info("Server酱全局实例初始化完成")
        except (configparser.Error, KeyError):
            logger.error("Server酱配置读取失败")
    return _serverchan_instance


def _get_qmsg():
    """获取Qmsg酱单例"""
    global _qmsg_instance
    if _qmsg_instance is None and _config is not None:
        try:
            key = _config.get('qmsg', 'key')
            default_qq = _config.get('qmsg', 'default_qq', fallback='')
            if key and key != '你的Qmsg密钥':
                _qmsg_instance = QmsgNotifier(key, default_qq if default_qq else None)
                logger.info("Qmsg酱全局实例初始化完成")
        except (configparser.Error, KeyError):
            logger.error("Qmsg酱配置读取失败")
    return _qmsg_instance


# ---------- 外部便捷调用函数 ----------
def send_reminder_wechat(message: str, title: str = "PC提醒") -> bool:
    """
    发送微信提醒

    :param message: 消息内容（支持换行）
    :param title: 消息标题
    :return: 发送成功返回 True，失败返回 False
    """
    logger.info("外部调用 send_reminder_wechat")
    notifier = _get_serverchan()
    if notifier is None:
        logger.error("Server酱未正确配置，请检查配置文件")
        return False
    try:
        return notifier.send(message=message, title=title)
    except Exception as e:
        logger.error(f"微信发送异常: {e}")
        return False


def send_reminder_qq(message: str, title: str = None, to: str = None) -> bool:
    """
    发送 QQ 提醒

    :param message: 消息内容
    :param title: 可选标题，将与消息合并
    :param to: 可选，指定QQ号；若不指定则使用配置中的 default_qq
    :return: 发送成功返回 True，失败返回 False
    """
    logger.info("外部调用 send_reminder_qq")
    notifier = _get_qmsg()
    if notifier is None:
        logger.error("Qmsg酱未正确配置，请检查配置文件")
        return False
    try:
        return notifier.send(message=message, title=title, to=to)
    except Exception as e:
        logger.error(f"QQ发送异常: {e}")
        return False


# 为兼容旧版，保留原函数名（如果已有代码依赖）
send_reminder = send_reminder_wechat


# ---------- 测试代码 ----------
if __name__ == "__main__":
    logger.info("===== 程序启动（测试模式）=====")

    # 测试微信提醒
    if _get_serverchan():
        result_wx = send_reminder_wechat(
            "这是一条来自 PC 的微信提醒\n请记得完成今天的任务！",
            title="工作提醒"
        )
        logger.info(f"微信发送结果: {result_wx}")
    else:
        logger.warning("微信未配置，跳过测试")

    # 测试QQ提醒
    if _get_qmsg():
        result_qq = send_reminder_qq(
            "这是一条来自 PC 的 QQ 提醒\n请记得完成今天的任务！",
            title="工作提醒"
        )
        logger.info(f"QQ发送结果: {result_qq}")
    else:
        logger.warning("QQ未配置，跳过测试")

    logger.info("===== 程序结束 =====")