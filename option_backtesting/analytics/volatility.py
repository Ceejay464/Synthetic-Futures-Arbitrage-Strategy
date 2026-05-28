import numpy as np
import pandas as pd


# =========================================================
# 1️⃣ Returns
# =========================================================

def log_returns(prices: pd.Series):
    """
    log return: r_t = ln(P_t / P_{t-1})
    """
    return np.log(prices / prices.shift(1))


def simple_returns(prices: pd.Series):
    """
    simple return: (P_t - P_{t-1}) / P_{t-1}
    """
    return prices.pct_change()


# =========================================================
# 2️⃣ Realized Volatility (核心)
# =========================================================

def realized_vol(prices: pd.Series, window=30, annualize=252):
    """
    Rolling realized volatility (annualized)
    """
    rets = log_returns(prices)

    rv = rets.rolling(window).std()

    return rv * np.sqrt(annualize)


def intraday_realized_vol(prices: pd.Series):
    """
    Single-period intraday RV (useful for 0DTE / intraday)
    """
    rets = log_returns(prices).dropna()
    return np.sqrt(np.sum(rets ** 2))
