# 添加项目根目录到 Python 路径
# -----------------------------------------------------------------------------
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# -----------------------------------------------------------------------------
'''
need feature in underlying_df: 
"日期“ ： 2015-02-09 (datetime64[us])
"收盘价(元)“：（float64）

need feature in option_df: 
”日期“ : 2015-02-09 (datetime64[us])
“期权简称” : 50ETF沽2015年3月2400 (str)
"行权价“ ： （float64）

'''
import pandas as pd
from collections import OrderedDict
from data.loader import load_option_data, load_underlying_data

FILE_PATH_UNDERLYING = "~/Desktop/50ETF Data/510050SH.xlsx"
FILE_PATH_OPTION = "~/Desktop/50ETF Data/Optiondata/option_from_2015-2026.xlsx"

import pandas as pd

def get_cn_option_expiry(year: int, month: int) -> pd.Timestamp:
    """
    中国ETF期权：当月第四个星期三
    """

    first_day = pd.Timestamp(year=year, month=month, day=1)
    next_month = first_day + pd.DateOffset(months=1)

    # 生成当月所有日期
    dates = pd.date_range(first_day, next_month - pd.Timedelta(days=1))

    # 过滤星期三（weekday=2）
    wednesdays = [d for d in dates if d.weekday() == 2]

    # 第四个星期三
    expiry = wednesdays[3]

    return pd.Timestamp(expiry)

def get_option_expiry_from_code(option_code: int, market="CN") -> pd.Timestamp:
    """
    从期权代码解析到期日：
    P/C 后4位 = YYMM
    """

    code = str(option_code)

    # ========= 1. 定位 P / C =========
    if "P" in code:
        idx = code.index("P")
    elif "C" in code:
        idx = code.index("C")
    else:
        raise ValueError(f"无期权类型标记: {code}")

    # ========= 2. 提取 YYMM =========
    yymm = code[idx + 1: idx + 5]

    yy = int(yymm[:2])
    mm = int(yymm[2:])

    year = 2000 + yy

    # ========= 3. 到期日 =========
    if market == "CN":
        expiry = get_cn_option_expiry(year, mm)

    else:
        first_day = pd.Timestamp(year=year, month=mm, day=1)
        first_fri = first_day + pd.offsets.Week(weekday=4)
        expiry = first_fri + pd.Timedelta(weeks=2)

        if expiry.weekday() >= 5:
            expiry -= pd.Timedelta(days=expiry.weekday() - 4)

    return expiry


class OptionDatabase:

    def __init__(self, 
                 underlying_df: pd.DataFrame,
                 option_df: pd.DataFrame, 
                 market="CN"):

        # ===== 1. 原始数据 =====
        self.underlying_df = underlying_df.copy()
        self.option_df = option_df.copy()
        self.market = market

        self.option_df["日期"] = pd.to_datetime(
            self.option_df["日期"]
        ).dt.normalize()

        self.underlying_df["日期"] = pd.to_datetime(
            self.underlying_df["日期"]
        ).dt.normalize()

        # ===== 2. 映射到“精确到日”的到期日 ===== （加入expiry_date列)
        self.option_df["expiry_date"] = self.option_df["交易代码"].apply(
            lambda x: get_option_expiry_from_code(x, market=self.market)
        )

        # ===== 3. 加入type列 ===== 
        self.option_df["type"] = self.option_df["期权简称"].apply(
            lambda x: "Call" if "购" in x else "Put"
        )

        # ===== 4. 按日期预切分（核心加速结构）=====
        self.option_by_date = dict(
            tuple(
                self.option_df.groupby("日期")
            )
        )


    def get_chain(self, timestamp: pd.Timestamp) -> pd.DataFrame | None:
        """
        获取某一天的全部期权链
        """
        return self.option_by_date.get(timestamp)


    def get_available_dates(self) -> list[pd.Timestamp]:
        """
        获取所有交易日（按时间排序）
        """
        return sorted(self.option_by_date.keys()) 
    

    def get_spot(self, date: pd.Timestamp) -> float | None:
        """
        获取某一天的标的价格（收盘价或指定价格列）
        """
        row = self.underlying_df[self.underlying_df["日期"] == date]

        return float(row["收盘价(元)"].values[0])
    

    def split_by_expiry_date(self, option_day: pd.DataFrame) -> dict:
        """
        input: option_day 来自 self.option_by_date.get(timestamp)
        将单日期权链按 expiry_date 分组
        return: dict[expiry_date -> DataFrame]
        """

        df = option_day.copy()

        grouped = dict(tuple(df.groupby("expiry_date")))

        return grouped

    
    def get_front_expiry_chain(self, option_snapshot):

        expiry_dict = self.split_by_expiry_date(option_snapshot)

        if not expiry_dict:
            return None

        front_expiry = min(expiry_dict.keys())

        return expiry_dict[front_expiry]
    
    
    def get_second_expiry_chain(self, option_snapshot):

        expiry_dict = self.split_by_expiry_date(option_snapshot)

        if not expiry_dict:
            return None

        sorted_expiries = sorted(expiry_dict.keys())
        second_expiry = sorted_expiries[1]

        return expiry_dict[second_expiry]


    def get_atm_strike(self, expiry_chain: pd.DataFrame, spot: float):
        """
        spot: get_spot()
        输入：单个 expiry 的 option chain
        输出：ATM strike
        """

        df = expiry_chain.copy()
        df["dist"] = (df["行权价"] - spot).abs()

        atm_row = df.loc[df["dist"].idxmin()]

        return atm_row["行权价"]
    

    def get_atm_pair(self, expiry_chain: pd.DataFrame, atm_strike):
        """
        输入：
            expiry_chain: 单个 expiry 的 option chain
            atm_strike: ATM 行权价

        输出：
            atm_call, atm_put 数据类型：<class 'pandas.DataFrame'>
        """

        df = expiry_chain.copy()

        # ===== 1. filter ATM strike =====
        atm_df = df[df["行权价"] == atm_strike]

        if atm_df.empty:
            return None, None

        # ===== 2. split call / put =====
        atm_call = atm_df[atm_df["type"].str.lower() == "call"]
        atm_put = atm_df[atm_df["type"].str.lower() == "put"]

        # ===== 3. fallback safety =====
        if atm_call.empty:
            atm_call = None
        if atm_put.empty:
            atm_put = None

        return atm_call, atm_put