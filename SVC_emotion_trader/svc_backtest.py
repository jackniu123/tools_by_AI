"""
SVC策略回测主模块
包含SVC指标计算和Backtrader策略执行
"""

import pandas as pd
import numpy as np
import backtrader as bt
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')


def compute_svc(daily_data, window=5, threshold=0.3):
    """
    计算SVC指标

    Args:
        daily_data: DataFrame包含 date, avg_sentiment, comment_count
        window: 评论量移动平均窗口
        threshold: SVC信号阈值

    Returns:
        DataFrame: 添加了 svc, signal 列
    """
    df = daily_data.copy()

    # 计算评论量移动平均
    df['volume_ma'] = df['comment_count'].rolling(window, min_periods=1).mean()

    # 计算评论量变化率
    df['volume_change'] = (df['comment_count'] - df['volume_ma']) / df['volume_ma'].replace(0, 1)

    # 计算SVC = 情绪分数 × 评论量变化率
    df['svc'] = df['avg_sentiment'] * df['volume_change']

    # 生成信号
    df['signal'] = 0
    df.loc[df['svc'] > threshold, 'signal'] = 1  # 买入信号
    df.loc[df['svc'] < -threshold, 'signal'] = -1  # 卖出信号

    # 信号平滑：连续N日相同信号才触发（可选）
    df['signal_smoothed'] = df['signal'].rolling(2, min_periods=1).mean()
    df['signal_smoothed'] = df['signal_smoothed'].apply(
        lambda x: 1 if x > 0.5 else (-1 if x < -0.5 else 0)
    )

    print(f"SVC指标计算完成")
    print(f"信号统计: 买入={len(df[df.signal_smoothed == 1])}, "
          f"卖出={len(df[df.signal_smoothed == -1])}, "
          f"持有={len(df[df.signal_smoothed == 0])}")

    return df


def merge_price_and_svc(price_df, svc_df):
    """
    合并价格数据和SVC信号

    Args:
        price_df: 价格DataFrame (需包含date, open, high, low, close, volume)
        svc_df: SVC DataFrame (需包含date, svc, signal_smoothed)

    Returns:
        DataFrame: 合并后的数据
    """
    # 确保日期格式一致
    price_df['date'] = pd.to_datetime(price_df['date']).dt.date
    svc_df['date'] = pd.to_datetime(svc_df['date']).dt.date

    merged = pd.merge(price_df, svc_df, on='date', how='inner')
    merged = merged.sort_values('date')

    print(f"合并后数据条数: {len(merged)}")
    print(f"日期范围: {merged['date'].min()} 至 {merged['date'].max()}")

    return merged


class SVCStrategy(bt.Strategy):
    """
    Backtrader SVC策略实现
    """
    params = (
        ('threshold', 0.3),
        ('print_log', True),
    )

    def __init__(self):
        self.svc = self.datas[0].svc
        self.signal = self.datas[0].signal
        self.order = None
        self.entry_price = None

    def log(self, txt, dt=None):
        if self.params.print_log:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt} {txt}')

    def next(self):
        if self.order:
            return

        current_svc = self.svc[0]
        current_signal = self.signal[0]
        current_price = self.datas[0].close[0]

        # 买入信号
        if current_signal > 0 and not self.position:
            size = int(self.broker.getcash() * 0.95 / current_price)
            if size > 0:
                self.log(f'买入信号触发 (SVC={current_svc:.3f})')
                self.order = self.buy(size=size)
                self.entry_price = current_price

        # 卖出信号
        elif current_signal < 0 and self.position:
            self.log(f'卖出信号触发 (SVC={current_svc:.3f})')
            self.order = self.sell(size=self.position.size)

        # 可选：止损逻辑
        elif self.position and current_price < self.entry_price * 0.95:
            self.log(f'止损触发 (跌幅5%)')
            self.order = self.sell(size=self.position.size)

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}, 数量: {order.size}')
            else:
                profit = (order.executed.price - self.entry_price) * order.size if self.entry_price else 0
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}, 盈亏: {profit:.2f}')
        self.order = None


class SVCDataFeed(bt.feeds.PandasData):
    """扩展PandasData，添加SVC和信号字段"""
    lines = ('svc', 'signal')
    params = (
        ('svc', 'svc'),
        ('signal', 'signal_smoothed'),
        ('datetime', 'date'),
    )


def run_backtest(merged_df, initial_cash=100000, commission=0.0003, threshold=0.3):
    """
    运行回测

    Args:
        merged_df: 合并后的DataFrame
        initial_cash: 初始资金
        commission: 佣金率（A股默认万分之三）
        threshold: SVC阈值
    """
    cerebro = bt.Cerebro()

    # 添加策略
    cerebro.addstrategy(SVCStrategy, threshold=threshold)

    # 准备数据
    data_df = merged_df.copy()
    data_df['date'] = pd.to_datetime(data_df['date'])
    data_df = data_df.set_index('date')

    # 添加数据
    data_feed = SVCDataFeed(dataname=data_df)
    cerebro.adddata(data_feed)

    # 设置初始资金
    cerebro.broker.setcash(initial_cash)

    # 设置佣金
    cerebro.broker.setcommission(commission=commission)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # 打印初始资金
    print(f'\n{"=" * 50}')
    print(f'回测开始 - 初始资金: {cerebro.broker.getvalue():.2f}')
    print(f'{"=" * 50}')

    # 运行回测
    results = cerebro.run()
    strat = results[0]

    # 获取分析结果
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - initial_cash) / initial_cash

    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    # 打印结果
    print(f'\n{"=" * 50}')
    print(f'回测结果 (阈值={threshold})')
    print(f'{"=" * 50}')
    print(f'最终资金: {final_value:.2f}')
    print(f'总收益率: {total_return:.2%}')
    if sharpe.get('sharperatio'):
        print(f'夏普比率: {sharpe["sharperatio"]:.3f}')
    print(f'最大回撤: {drawdown.max.drawdown:.2f}%')
    print(f'总交易次数: {trades.total.total if trades.total else 0}')

    # 可选：绘制图表
    # cerebro.plot()

    return results


def quick_validate(price_df, svc_df, threshold=0.3):
    """
    快速验证策略有效性（不依赖backtrader）
    使用简单的次日收益计算
    """
    merged = merge_price_and_svc(price_df, svc_df)

    if merged.empty:
        print("无有效数据")
        return

    # 计算次日收益率
    merged['next_return'] = merged['close'].pct_change().shift(-1)

    # 按信号分组统计
    buy_signals = merged[merged['signal_smoothed'] == 1]
    sell_signals = merged[merged['signal_smoothed'] == -1]
    hold_signals = merged[merged['signal_smoothed'] == 0]

    print(f'\n{"=" * 50}')
    print(f'快速验证结果 (阈值={threshold})')
    print(f'{"=" * 50}')
    print(f'买入信号数量: {len(buy_signals)}')
    print(f'买入后次日平均收益: {buy_signals["next_return"].mean():.4%}')
    print(f'买入后次日胜率: {(buy_signals["next_return"] > 0).mean():.2%}')

    print(f'\n卖出信号数量: {len(sell_signals)}')
    print(f'卖出后次日平均收益: {sell_signals["next_return"].mean():.4%}')

    print(f'\n无信号数量: {len(hold_signals)}')
    print(f'无信号次日平均收益: {hold_signals["next_return"].mean():.4%}')

    # 计算策略累计收益
    merged['strategy_return'] = merged['signal_smoothed'].shift(1) * merged['close'].pct_change()
    strategy_cum = (1 + merged['strategy_return']).cumprod()
    buy_hold_cum = (1 + merged['close'].pct_change()).cumprod()

    print(f'\n策略累计收益: {strategy_cum.iloc[-1] - 1:.2%}')
    print(f'买入持有收益: {buy_hold_cum.iloc[-1] - 1:.2%}')
    print(f'超额收益: {(strategy_cum.iloc[-1] - buy_hold_cum.iloc[-1]):.2%}')

    return merged


if __name__ == "__main__":
    # 测试快速验证（假设已有数据文件）
    print("SVC策略回测模块已加载")