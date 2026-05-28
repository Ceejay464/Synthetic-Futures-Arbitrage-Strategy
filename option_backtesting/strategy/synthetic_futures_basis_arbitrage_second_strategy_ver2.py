import pandas as pd

class SyntheticFuturesBasisArbitrageSecondStrategyVer2:

    def __init__(self, upper_threshold, down_threshold, quantity, max_holding=10):
        self.entry_date = None
        self.lock_expiry = None

        self.upper_threshold = upper_threshold
        self.down_threshold = down_threshold
        self.quantity = quantity

        self.max_holding = max_holding

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
        # 2. second expiry + ATM
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
        # 3. synthetic futures
        # =========================================================
        synthetic_futures = call_price - put_price + atm_strike
        basis = (synthetic_futures - spot) / spot

        # =========================================================
        # 4. position state
        # =========================================================
        pos = portfolio.get_positions()
        underlying_pos = pos["underlying"]
        option_pos = pos["options"]

        has_position = (underlying_pos != 0) or (len(option_pos) > 0)

        # =========================================================
        # 5. 强制平仓（到期 / 时间）
        # =========================================================
        if has_position and self.entry_date is not None:

            holding_days = (date - self.entry_date).days

            # ---- (1) 到期 ----
            if self.lock_expiry is not None and date >= self.lock_expiry:
                print("期权到期强平：", date)
                orders += self._close_all(option_snapshot, option_pos, underlying_pos)
                self._reset()
                return orders

            # ---- (2) max holding ----
            if holding_days >= self.max_holding:
                print("持仓时间超限强平：", date)
                orders += self._close_all(option_snapshot, option_pos, underlying_pos)
                self._reset()
                return orders

        # =========================================================
        # 6. signal close
        # =========================================================
        if has_position:

            if basis <= self.down_threshold:
                print("basis回落平仓：", date)
                orders += self._close_all(option_snapshot, option_pos, underlying_pos)
                self._reset()
                return orders

        # =========================================================
        # 7. open
        # =========================================================
        if not has_position:

            if basis >= self.upper_threshold and (call["expiry_date"] > date):

                # ETF long
                orders.append({
                    "instrument": "underlying",
                    "quantity": self.quantity * 10000,
                    "price": spot
                })

                # synthetic short call
                orders.append({
                    "instrument": "option",
                    "期权代码": call["期权代码"],
                    "quantity": -self.quantity,
                    "price": call_price,
                    "expiry": call["expiry_date"],
                    "type": "Call"
                })

                # synthetic long put
                orders.append({
                    "instrument": "option",
                    "期权代码": put["期权代码"],
                    "quantity": self.quantity,
                    "price": put_price,
                    "expiry": put["expiry_date"],
                    "type": "Put"
                })

                self.entry_date = date
                self.lock_expiry = call["expiry_date"]

                print("开仓：", self.entry_date)
                print("到期：", self.lock_expiry)

        return orders

    # =========================================================
    # close
    # =========================================================
    def _close_all(self, option_snapshot, option_pos, underlying_pos):

        orders = []

        if underlying_pos != 0:
            orders.append({
                "instrument": "underlying",
                "quantity": -underlying_pos
            })

        for oid, pos in option_pos.items():

            option = option_snapshot[option_snapshot["期权代码"] == oid].iloc[0]

            orders.append({
                "instrument": "option",
                "期权代码": oid,
                "quantity": -pos["quantity"],
                "price": option["收盘价"],
                "expiry": option["expiry_date"],
                "type": option["type"]
            })

        return orders

    # =========================================================
    # reset
    # =========================================================
    def _reset(self):
        self.entry_date = None
        self.lock_expiry = None