"""
A股股吧数据采集模块
使用stock_stil库采集东方财富股吧的帖子评论数据
"""

import pandas as pd
import time
from datetime import datetime
from stock_stil import comments


def get_stock_board_code(stock_code):
    """
    获取东方财富股吧的板块代码
    601111 -> 601111吧 (直接使用股票代码即可)
    """
    return stock_code


def collect_posts(stock_code, max_pages=50):
    """
    采集股吧帖子列表

    Args:
        stock_code: 股票代码，如 '601111'
        max_pages: 最大采集页数

    Returns:
        DataFrame: 包含帖子ID、标题、评论数、浏览数、发布时间
    """
    board_code = get_stock_board_code(stock_code)
    all_posts = []

    print(f"开始采集 {stock_code} 股吧帖子...")

    for page in range(1, max_pages + 1):
        try:
            # 获取帖子列表
            post_list = comments.getEastMoneyPostList(
                stock_code=board_code,
                page=page
            )

            if not post_list:
                print(f"第{page}页无数据，停止采集")
                break

            for post in post_list:
                # 使用正确的发布时间属性
                publish_time = getattr(post, 'post_publish_time', '')
                if not publish_time:
                    # 备选最后回复时间
                    publish_time = getattr(post, 'post_last_time', '')

                all_posts.append({
                    'post_id': post.post_id,
                    'title': post.post_title,
                    'user_nickname': post.user_nickname,
                    'post_click_count': getattr(post, 'post_click_count', 0),
                    'post_comment_count': getattr(post, 'post_comment_count', 0),
                    'post_time': publish_time,          # 现在会正确填充
                    'stock_code': stock_code
                })

            print(f"第{page}页采集完成，共{len(post_list)}条帖子")
            time.sleep(0.5)  # 礼貌爬取

        except Exception as e:
            print(f"第{page}页采集失败: {e}")
            continue

    df = pd.DataFrame(all_posts)
    print(f"采集完成，共获取{len(df)}条帖子")
    return df


def collect_comments(post_id, max_pages=10):
    """
    采集指定帖子的评论内容（用于情绪分析）

    Args:
        post_id: 帖子ID
        max_pages: 最大采集页数

    Returns:
        list: 评论文本列表
    """
    all_comments = []

    for page in range(1, max_pages + 1):
        try:
            comments_list = comments.getEasyMoneyPostReplyList(
                post_id=post_id,
                page=page
            )

            if not comments_list:
                break

            for comment in comments_list:
                all_comments.append({
                    'post_id': post_id,
                    'reply_text': comment.reply_text,
                    'reply_like_count': getattr(comment, 'reply_like_count', 0),
                    'reply_time': getattr(comment, 'reply_time', '')
                })

            time.sleep(0.3)

        except Exception as e:
            print(f"采集评论失败: {e}")
            break

    return all_comments


def collect_daily_comments_volume(stock_code, start_date, end_date, max_posts=500):
    """
    采集每日评论量（基于 post_publish_time）
    """
    from stock_stil import comments
    import pandas as pd
    import time
    from datetime import datetime

    board_code = get_stock_board_code(stock_code)
    daily_volume = {}

    print(f"开始采集 {stock_code} 股吧帖子...")

    for page in range(1, 301):
        try:
            post_list = comments.getEastMoneyPostList(stock_code=board_code, page=page)
            if not post_list:
                print(f"第{page}页无数据，停止采集")
                break

            for post in post_list:
                # 直接使用 post_publish_time
                publish_time = getattr(post, 'post_publish_time', '')
                if not publish_time:
                    # 如果还是没有，尝试 post_last_time 作为备选
                    publish_time = getattr(post, 'post_last_time', '')

                if not publish_time:
                    continue

                # 提取日期部分 (格式如 "2026-03-29 16:33:20")
                date_str = publish_time.split()[0] if ' ' in publish_time else publish_time[:10]

                # 只统计指定日期范围内的数据
                if start_date <= date_str <= end_date:
                    daily_volume[date_str] = daily_volume.get(date_str, 0) + 1

            print(f"第{page}页采集完成，本页{len(post_list)}条帖子")
            time.sleep(0.5)

        except Exception as e:
            print(f"第{page}页采集失败: {e}")
            break

    if not daily_volume:
        print("警告：未采集到指定日期范围内的评论数据")
        return pd.DataFrame(columns=['date', 'comment_volume'])

    df = pd.DataFrame([
        {'date': k, 'comment_volume': v}
        for k, v in daily_volume.items()
    ])

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    print(f"采集完成，共{len(df)}天有评论数据")
    print(f"日期范围: {df['date'].min()} 至 {df['date'].max()}")

    return df


if __name__ == "__main__":
    # 测试采集
    df_posts = collect_posts('601111', max_pages=10)
    print(df_posts.head())
    df_posts.to_csv('601111_posts.csv', index=False, encoding='utf-8-sig')