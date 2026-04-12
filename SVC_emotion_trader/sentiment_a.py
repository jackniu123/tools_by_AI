"""
A股评论情感分析模块
使用中文情感词典 + Jieba分词，无需调用外部API
"""

import pandas as pd
import jieba
import re

# 自定义情感词典（可扩充）
POSITIVE_WORDS = {
    '涨', '涨停', '拉升', '反弹', '突破', '看好', '买入', '推荐', '持有',
    '利好', '绩优', '盈利', '增长', '低估', '抄底', '起飞', '爆发',
    '牛股', '龙头', '主力', '资金流入', '放量', '上涨', '新高', '大阳线'
}

NEGATIVE_WORDS = {
    '跌', '跌停', '下跌', '跳水', '破位', '看空', '卖出', '减持', '规避',
    '利空', '亏损', '暴跌', '崩盘', '套牢', '割肉', '踩雷', '退市',
    '风险', '主力出逃', '资金流出', '缩量', '新低', '大阴线', '炸板'
}

INTENSIFIER_WORDS = {
    '非常', '极度', '特别', '十分', '强烈', '超级', '重大', '暴力'
}
WEAKEN_WORDS = {
    '可能', '或许', '似乎', '大概', '稍微', '有点', '略微'
}


def load_sentiment_dict():
    """加载情感词典（可扩展）"""
    return POSITIVE_WORDS, NEGATIVE_WORDS, INTENSIFIER_WORDS, WEAKEN_WORDS


def preprocess_text(text):
    """文本预处理"""
    if not isinstance(text, str):
        return ""
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除特殊字符
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
    return text.strip()


def calculate_sentiment_score(text, pos_words, neg_words, inten_words, weak_words):
    """
    计算单条评论的情感分数
    返回：-1 到 1 之间的分数
    """
    if not text or len(text) < 2:
        return 0.0

    # 分词
    words = jieba.lcut(text)

    pos_score = 0
    neg_score = 0

    for i, word in enumerate(words):
        if word in pos_words:
            # 检查是否有程度副词修饰
            if i > 0 and words[i - 1] in inten_words:
                pos_score += 2
            elif i > 0 and words[i - 1] in weak_words:
                pos_score += 0.5
            else:
                pos_score += 1
        elif word in neg_words:
            if i > 0 and words[i - 1] in inten_words:
                neg_score += 2
            elif i > 0 and words[i - 1] in weak_words:
                neg_score += 0.5
            else:
                neg_score += 1

    total = pos_score + neg_score
    if total == 0:
        return 0.0

    # 映射到 -1 到 1 区间
    sentiment = (pos_score - neg_score) / total
    return max(-1.0, min(1.0, sentiment))


def analyze_batch_sentiment(texts, batch_size=100):
    """
    批量分析情感

    Args:
        texts: 文本列表
        batch_size: 批次大小

    Returns:
        list: 情感分数列表
    """
    pos_words, neg_words, inten_words, weak_words = load_sentiment_dict()

    results = []
    for i, text in enumerate(texts):
        processed = preprocess_text(text)
        score = calculate_sentiment_score(
            processed, pos_words, neg_words, inten_words, weak_words
        )
        results.append(score)

        if (i + 1) % batch_size == 0:
            print(f"已完成 {i + 1}/{len(texts)} 条情感分析")

    return results


def aggregate_daily_sentiment(df, text_column='reply_text', date_column='date'):
    """
    按日期聚合情感分数

    Args:
        df: 包含文本和日期的DataFrame
        text_column: 文本列名
        date_column: 日期列名

    Returns:
        DataFrame: date, avg_sentiment, comment_count
    """
    # 添加日期列（如果没有）
    if date_column not in df.columns:
        print("警告：数据中没有日期列，将使用当前日期")
        df[date_column] = pd.Timestamp.now().strftime('%Y-%m-%d')

    # 按日期分组计算平均情感
    daily = df.groupby(date_column).agg({
        text_column: 'count',
        'sentiment_score': 'mean'
    }).rename(columns={
        text_column: 'comment_count',
        'sentiment_score': 'avg_sentiment'
    }).reset_index()

    return daily


if __name__ == "__main__":
    # 测试情感分析
    test_texts = [
        "这只股票前景看好，管理层能力很强",
        "跌停了，彻底完蛋，明天割肉",
        "震荡调整，观望为主"
    ]

    scores = analyze_batch_sentiment(test_texts)
    for text, score in zip(test_texts, scores):
        print(f"{text}\n情感分数: {score:.2f}\n")