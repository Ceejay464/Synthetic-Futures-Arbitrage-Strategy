import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq


# =========================================================
# 1️⃣ Basic functions
# =========================================================

def d1(S, K, T, r, sigma):
    return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))


def d2(d1_val, sigma, T):
    return d1_val - sigma * np.sqrt(T)

# =========================================================
# 4️⃣ Implied Volatility
# =========================================================

def implied_vol_call(market_price, S, K, T, r, sigma_lower=1e-6, sigma_upper=5.0):
    """
    Solve implied volatility for call option
    """

    def objective(sigma):
        return call_price(S, K, T, r, sigma) - market_price

    try:
        iv = brentq(objective, sigma_lower, sigma_upper)
        return iv

    except Exception:
        return np.nan


def implied_vol_put(market_price, S, K, T, r, sigma_lower=1e-6, sigma_upper=5.0):
    """
    Solve implied volatility for put option
    """

    def objective(sigma):
        return put_price(S, K, T, r, sigma) - market_price

    try:
        iv = brentq(objective, sigma_lower, sigma_upper)
        return iv

    except Exception:
        return np.nan
    
# =========================================================
# 2️⃣ Option Pricing
# =========================================================

def call_price(S, K, T, r, sigma):
    d1_val = d1(S, K, T, r, sigma)
    d2_val = d2(d1_val, sigma, T)

    return S * norm.cdf(d1_val) - K * np.exp(-r * T) * norm.cdf(d2_val)


def put_price(S, K, T, r, sigma):
    d1_val = d1(S, K, T, r, sigma)
    d2_val = d2(d1_val, sigma, T)

    return K * np.exp(-r * T) * norm.cdf(-d2_val) - S * norm.cdf(-d1_val)


# =========================================================
# 3️⃣ Greeks
# =========================================================

def delta_call(S, K, T, r, sigma):
    return norm.cdf(d1(S, K, T, r, sigma))


def delta_put(S, K, T, r, sigma):
    return norm.cdf(d1(S, K, T, r, sigma)) - 1


def gamma(S, K, T, r, sigma):
    d1_val = d1(S, K, T, r, sigma)
    return norm.pdf(d1_val) / (S * sigma * np.sqrt(T))


def vega(S, K, T, r, sigma):
    d1_val = d1(S, K, T, r, sigma)
    return S * norm.pdf(d1_val) * np.sqrt(T)


def theta_call(S, K, T, r, sigma):
    d1_val = d1(S, K, T, r, sigma)
    d2_val = d2(d1_val, sigma, T)

    term1 = -(S * norm.pdf(d1_val) * sigma) / (2 * np.sqrt(T))
    term2 = -r * K * np.exp(-r * T) * norm.cdf(d2_val)

    return term1 + term2

def time_to_expiry(timestamp): # only for 0DTE Option

    # create today 16:00
    market_close = pd.Timestamp(year=timestamp.year, month=timestamp.month, day=timestamp.day, 
                                hour=16, minute=0, second=0)

    remaining_minutes = (market_close - timestamp).total_seconds() / 60

    trading_minutes_per_year = 252 * 390

    # Black-Scholes T
    T = remaining_minutes / trading_minutes_per_year

    return T
# =========================================================
# 4️⃣ Convenience wrapper（推荐你用这个）
# =========================================================

def full_greeks(option_type, S, K, T, r, sigma):
    """
    返回一个统一结构，方便你直接塞进 option dict
    """

    if option_type == "call":
        return {
            "price": call_price(S, K, T, r, sigma),
            "delta": delta_call(S, K, T, r, sigma),
            "gamma": gamma(S, K, T, r, sigma),
            "vega": vega(S, K, T, r, sigma),
            "theta": theta_call(S, K, T, r, sigma),
        }

    elif option_type == "put":
        # put theta 你可以后面补，这里先简单处理
        return {
            "price": put_price(S, K, T, r, sigma),
            "delta": delta_put(S, K, T, r, sigma),
            "gamma": gamma(S, K, T, r, sigma),
            "vega": vega(S, K, T, r, sigma),
            "theta": theta_call(S, K, T, r, sigma),
        }

    else:
        raise ValueError("option_type must be 'call' or 'put'")