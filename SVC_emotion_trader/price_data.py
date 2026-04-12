"""
A股行情数据获取模块
使用akshare获取历史日线数据
"""

import akshare as ak
import pandas as pd


def get_a_stock_hist_data(symbol, start_date, end_date, adjust='hfq'):
    """
    获取A股历史行情数据

    Args:
        symbol: 股票代码，如 '601111'
        start_date: 开始日期 'YYYYMMDD'
        end_date: 结束日期 'YYYYMMDD'
        adjust: 复权类型，'hfq'-后复权, 'qfq'-前复权, ''-不复权

    Returns:
        DataFrame: 包含 open, high, low, close, volume 等字段
    """
    print(f"正在获取 {symbol} 历史行情数据...")

    # 使用akshare获取历史数据
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )

    if df.empty:
        print(f"未获取到{symbol}的数据，请检查股票代码和日期范围")
        return df

    # 重命名列名以符合backtrader要求
    df = df.rename(columns={
        '日期': 'date',
        '开盘': 'open',
        '收盘': 'close',
        '最高': 'high',
        '最低': 'low',
        '成交量': 'volume',
        '成交额': 'amount',
        '振幅': 'amplitude',
        '涨跌幅': 'pct_change',
        '涨跌额': 'change',
        '换手率': 'turnover'
    })

    # 确保日期格式正确
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    print(f"获取完成，共{len(df)}条日线数据")
    print(f"时间范围: {df['date'].min()} 至 {df['date'].max()}")

    return df


def get_realtime_quote(symbol):
    """
    获取A股实时行情

    Args:
        symbol: 股票代码

    Returns:
        DataFrame: 实时行情数据
    """
    try:
        df = ak.stock_zh_a_spot_em()
        stock_data = df[df['代码'] == symbol]
        if not stock_data.empty:
            return stock_data.iloc[0]
    except Exception as e:
        print(f"获取实时行情失败: {e}")
    return None


if __name__ == "__main__":
    # 测试获取601111的历史数据
    df = get_a_stock_hist_data('601111', '20230101', '20241231')
    print(df.head())
    df.to_csv('601111_price.csv', index=False, encoding='utf-8-sig')