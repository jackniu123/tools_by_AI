"""
A股SVC策略一键执行脚本
目标股票：601111 中国国航
"""

import os
import pandas as pd
from datetime import datetime


def main():
    print("=" * 60)
    print("A股SVC策略验证系统")
    print(f"目标股票: 601111 中国国航")
    print(f"运行时间: {datetime.now()}")
    print("=" * 60)

    # ========== 配置参数 ==========
    STOCK_CODE = '601111'
    START_DATE = '20230101'  # 开始日期 YYYYMMDD
    END_DATE = '20241231'  # 结束日期
    SVC_THRESHOLD = 0.3  # SVC阈值
    INITIAL_CASH = 100000  # 初始资金

    # ========== 1. 获取价格数据 ==========
    print("\n[步骤1] 获取A股历史行情数据...")
    from price_data import get_a_stock_hist_data

    price_df = get_a_stock_hist_data(STOCK_CODE, START_DATE, END_DATE)

    if price_df.empty:
        print("错误：无法获取价格数据，请检查网络和股票代码")
        return

    price_df.to_csv(f'{STOCK_CODE}_price.csv', index=False, encoding='utf-8-sig')
    print(f"价格数据已保存至 {STOCK_CODE}_price.csv")

    # ========== 2. 采集股吧评论数据 ==========
    print("\n[步骤2] 采集股吧评论数据...")
    from data_collector_a import collect_posts, collect_daily_comments_volume

    # 采集帖子列表
    posts_df = collect_posts(STOCK_CODE, max_pages=300)
    if not posts_df.empty:
        posts_df.to_csv(f'{STOCK_CODE}_posts.csv', index=False, encoding='utf-8-sig')
        print(f"帖子数据已保存至 {STOCK_CODE}_posts.csv")

        # 统计每日评论量
        start_date_fmt = datetime.strptime(START_DATE, '%Y%m%d').strftime('%Y-%m-%d')
        end_date_fmt = datetime.strptime(END_DATE, '%Y%m%d').strftime('%Y-%m-%d')

        daily_volume = collect_daily_comments_volume(
            STOCK_CODE, start_date_fmt, end_date_fmt
        )
    else:
        # 如果没有采集到数据，使用模拟数据进行测试
        print("警告：未采集到评论数据，使用模拟数据演示")
        dates = pd.date_range(start=START_DATE, end=END_DATE, freq='D')
        daily_volume = pd.DataFrame({
            'date': dates.strftime('%Y-%m-%d'),
            'comment_volume': np.random.randint(1, 100, len(dates))
        })

    # ========== 3. 情感分析 ==========
    print("\n[步骤3] 进行情感分析...")
    from sentiment_a import analyze_batch_sentiment, aggregate_daily_sentiment

    # 如果有评论数据，进行情感分析
    if not posts_df.empty and 'title' in posts_df.columns:
        texts = posts_df['title'].fillna('').tolist()
        sentiment_scores = analyze_batch_sentiment(texts)

        posts_df['sentiment_score'] = sentiment_scores
        posts_df['date'] = pd.to_datetime(posts_df['post_time']).dt.strftime('%Y-%m-%d')

        # 日度聚合
        daily_sentiment = aggregate_daily_sentiment(
            posts_df,
            text_column='title',
            date_column='date'
        )
    else:
        # 使用模拟情感数据
        print("使用模拟情感数据进行演示")
        dates = pd.date_range(start=START_DATE, end=END_DATE, freq='D')
        daily_sentiment = pd.DataFrame({
            'date': dates.strftime('%Y-%m-%d'),
            'comment_count': np.random.randint(10, 200, len(dates)),
            'avg_sentiment': np.random.uniform(-0.5, 0.5, len(dates))
        })

    # ========== 4. 计算SVC指标 ==========
    print("\n[步骤4] 计算SVC指标...")
    from svc_backtest import compute_svc, quick_validate, run_backtest

    svc_df = compute_svc(daily_sentiment, window=5, threshold=SVC_THRESHOLD)
    svc_df.to_csv(f'{STOCK_CODE}_svc.csv', index=False, encoding='utf-8-sig')
    print(f"SVC数据已保存至 {STOCK_CODE}_svc.csv")

    # ========== 5. 执行回测 ==========
    print("\n[步骤5] 执行策略回测...")

    # 快速验证
    merged = quick_validate(price_df, svc_df, threshold=SVC_THRESHOLD)

    # 完整回测（需要backtrader）
    try:
        run_backtest(merged, initial_cash=INITIAL_CASH, threshold=SVC_THRESHOLD)
    except Exception as e:
        print(f"完整回测失败: {e}")
        print("快速验证结果已输出")

    print("\n✅ SVC策略验证完成！")


if __name__ == "__main__":
    # 安装必要的库
    # pip install stock_stil akshare backtrader pandas numpy jieba

    main()