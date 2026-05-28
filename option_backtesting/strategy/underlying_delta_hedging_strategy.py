import pandas as pd
import numpy as np
from analytics.black_scholes import delta_call, delta_put, implied_vol_call, implied_vol_put


class UnderlyingDeltaHedgingStrategy:

    def __init__(self, hedge_threshold=0.05, hedge_ratio=1.0):
        self.hedge_threshold = hedge_threshold
        self.hedge_ratio = hedge_ratio

        self.last_call_sigma = None
        self.last_put_sigma = None

    def get_trade_price(self, snapshot):
        return snapshot.iloc[0]["收盘价(元)"]

    # =========================
    # dynamic T
    # =========================
    def time_to_expiry(self, timestamp, expiry):

        market_close = pd.Timestamp(
            year=expiry.year,
            month=expiry.month,
            day=expiry.day,
            hour=16, minute=0, second=0
        )

        remaining_days = (market_close - timestamp).total_seconds() / (24 * 3600)

        return remaining_days / 365

    # =========================
    # delta calc
    # =========================
    def compute_option_delta(self, option_data, option_positions, spot, timestamp, portfolio, r=0.0):

        price_map = option_data.set_index("期权代码")["收盘价"].to_dict()
        net_delta = 0

        K = portfolio.get_position_strike()
        expiry = portfolio.get_position_expiry()

        if expiry == None:
            return 0

        T = self.time_to_expiry(timestamp, expiry) 
        

        for oid, pos in option_positions.items():

            option_type = pos["type"]
            qty = pos["quantity"]
            price = price_map.get(oid, None)

            if option_type == "Call":
                sigma = implied_vol_call(market_price=price, S=spot, K=K, T=T, r=r, sigma_lower=1e-6, sigma_upper=5.0)

                if not np.isnan(sigma):
                    self.last_call_sigma = sigma
                else:
                    sigma = self.last_call_sigma

                delta = delta_call(spot, K, T, r, sigma)
                print("call delta:", delta)

            else:
                sigma = implied_vol_put(market_price=price, S=spot, K=K, T=T, r=r, sigma_lower=1e-6, sigma_upper=5.0)

                if not np.isnan(sigma):
                    self.last_put_sigma = sigma
                else:
                    sigma = self.last_put_sigma
                
                delta = delta_put(spot, K, T, r, sigma)
                print("put delta:", delta)

            net_delta += qty * delta * portfolio.get_multiplier()

        return net_delta

    # =========================
    # main
    # =========================
    def generate_signal(self, timestamp, underlying_snapshot, option_snapshot, portfolio, option_db):

        orders = []
        date = pd.to_datetime(timestamp)

        spot = self.get_trade_price(underlying_snapshot)

        pos = portfolio.get_positions()
        underlying_pos = pos["underlying"]
        option_pos = pos["options"]

        option_delta = self.compute_option_delta(option_data=option_snapshot, option_positions=option_pos,
                                                 spot=spot, timestamp=date, portfolio=portfolio)

        net_delta = underlying_pos + option_delta

        if abs(net_delta) < self.hedge_threshold:
            return orders
        
        target_underlying = -self.hedge_ratio * net_delta

        trade_qty = round(target_underlying)

        orders.append({
            "instrument": "underlying",
            "quantity": trade_qty,
            "price": spot,
            "timestamp": timestamp
        })

        return orders