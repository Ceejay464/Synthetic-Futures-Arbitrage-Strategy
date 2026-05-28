import pandas as pd

class SyntheticFuturesBasisArbitrageSecondStrategy:

    def __init__(self, upper_threshold, down_threshold, quantity):
        self.entry_date = None
        self.lock_expiry = None
        self.upper_threshold = upper_threshold
        self.down_threshold = down_threshold
        self.quantity = quantity

    # =========================================================
    # 获取日频成交价（收盘价）
    # =========================================================
    def get_trade_price(self, snapshot):
        return snapshot.iloc[0]["收盘价(元)"]

    # =========================================================
    # 主逻辑
    # =========================================================
    def generate_signal(self, timestamp, underlying_snapshot, option_snapshot, portfolio, option_db):

        date = pd.to_datetime(timestamp)
        orders = []

        if option_snapshot is None or option_snapshot.empty:
            return orders

        # =========================================================
        # 1. ETF 收盘价
        # =========================================================
        spot = self.get_trade_price(underlying_snapshot)

        # =========================================================
        # 2. front expiry + ATM
        # =========================================================
        second_chain = option_db.get_second_expiry_chain(option_snapshot)
        if second_chain is None:
            return orders

        atm_strike = option_db.get_atm_strike(second_chain, spot)
        atm_call, atm_put = option_db.get_atm_pair(second_chain, atm_strike)

        if atm_call is None or atm_put is None:
            return orders

        call = atm_call.iloc[0]
        put = atm_put.iloc[0]

        call_price = call["收盘价"]
        put_price = put["收盘价"]

        # =========================================================
        # 3. synthetic futures price (put-call parity proxy)
        # =========================================================
        synthetic_futures = call_price - put_price + atm_strike

        basis = (synthetic_futures - spot) / spot

        # =========================================================
        # 4. 仓位状态
        # =========================================================
        pos = portfolio.get_positions()
        underlying_pos = pos["underlying"]
        option_pos = pos["options"]

        has_position = (underlying_pos != 0) or (len(option_pos) > 0)

        # =========================================================
        # 5. 强制平仓（到期日）
        # =========================================================
        if has_position and self.lock_expiry is not None:

            if date >= self.lock_expiry:

                print("今天期权到期，今天平仓：", date)
                orders += self._close_all(option_snapshot, option_pos, underlying_pos, portfolio)
                self._reset()
                return orders

        # =========================================================
        # 6. 平仓信号（basis 回落）
        # =========================================================
        if has_position:

            if basis <= self.down_threshold:   # 0.1%
                print("今天spread变小，平仓：", date)
                orders += self._close_all(option_snapshot, option_pos, underlying_pos, portfolio)
                self._reset()
                return orders

        # =========================================================
        # 7. 开仓信号（升水）
        # =========================================================
        if not has_position:

            if basis >= self.upper_threshold and (call["expiry_date"] > date):   # 0.2%

                # =========================
                # ETF 多头
                # =========================
                orders.append({
                    "instrument": "underlying",
                    "quantity": self.quantity * 10000,
                    "price": spot
                })

                # =========================
                # 合成期货空头
                # =========================
                orders.append({
                    "instrument": "option",
                    "期权代码": call["期权代码"],
                    "quantity": -self.quantity,
                    "price": call_price,
                    "expiry": call["expiry_date"],
                    "type": "Call"
                })

                orders.append({
                    "instrument": "option",
                    "期权代码": put["期权代码"],
                    "quantity": self.quantity,
                    "price": put_price,
                    "expiry": put["expiry_date"],
                    "type": "Put"
                })

                portfolio.set_position_strike(atm_strike)
                portfolio.set_position_expiry(call["expiry_date"])
                
                # 记录状态
                self.entry_date = date
                self.lock_expiry = call["expiry_date"]
                print("今天开仓：", self.entry_date)
                print("到期日为：", self.lock_expiry)

        return orders

    # =========================================================
    # 平仓逻辑
    # =========================================================
    def _close_all(self, option_snapshot, option_pos, underlying_pos, portfolio):

        orders = []

        # =========================
        # ETF 平仓
        # =========================
        if underlying_pos != 0:
            orders.append({
                "instrument": "underlying",
                "quantity": -underlying_pos
            })

        # =========================
        # 期权平仓
        # =========================
        for oid, pos in option_pos.items():

            option = option_snapshot[
                option_snapshot["期权代码"] == oid
            ].iloc[0]

            orders.append({
                "instrument": "option",
                "期权代码": oid,
                "quantity": -pos["quantity"],
                "price": option["收盘价"],
                "expiry": option["expiry_date"],
                "type": option["type"]
            })

        # =========================
        # RESET PORTFOLIO STATE
        # =========================
        portfolio.set_position_strike(None)
        portfolio.set_position_expiry(None)

        return orders

    # =========================================================
    # 状态重置
    # =========================================================
    def _reset(self):
        self.entry_date = None
        self.lock_expiry = None