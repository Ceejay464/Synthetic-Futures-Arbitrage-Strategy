import pandas as pd


class SyntheticFuturesBasisArbitrageStrategyVer3:

    def __init__(self, upper_threshold, down_threshold, quantity, atm_roll_threshold=0.025):

        self.entry_date = None
        self.lock_expiry = None

        # 当前持仓ATM strike
        self.current_atm_strike = None

        self.upper_threshold = upper_threshold
        self.down_threshold = down_threshold

        # ATM切换阈值
        self.atm_roll_threshold = atm_roll_threshold

        self.quantity = quantity

    # =========================================================
    # 获取ETF价格
    # =========================================================
    def get_trade_price(self, snapshot):

        return snapshot.iloc[0]["收盘价(元)"]

    # =========================================================
    # 主逻辑
    # =========================================================
    def generate_signal(
        self,
        timestamp,
        underlying_snapshot,
        option_snapshot,
        portfolio,
        option_db
    ):

        date = pd.to_datetime(timestamp)

        orders = []

        if option_snapshot is None or option_snapshot.empty:
            return orders

        # =====================================================
        # ETF价格
        # =====================================================
        spot = self.get_trade_price(underlying_snapshot)

        # =====================================================
        # front month
        # =====================================================
        front_chain = option_db.get_front_expiry_chain(option_snapshot)

        if front_chain is None:
            return orders

        # =====================================================
        # 最新ATM
        # =====================================================
        atm_strike = option_db.get_atm_strike(front_chain, spot)

        atm_call, atm_put = option_db.get_atm_pair(
            front_chain,
            atm_strike
        )

        if atm_call is None or atm_put is None:
            return orders

        call = atm_call.iloc[0]
        put = atm_put.iloc[0]

        call_price = call["收盘价"]
        put_price = put["收盘价"]

        # =====================================================
        # synthetic futures
        # =====================================================
        synthetic_futures = (call_price - put_price + atm_strike)

        basis = (synthetic_futures - spot) / spot

        # =====================================================
        # 当前仓位
        # =====================================================
        pos = portfolio.get_positions()

        underlying_pos = pos["underlying"]
        option_pos = pos["options"]

        has_position = (
            underlying_pos != 0
            or len(option_pos) > 0
        )

        # =====================================================
        # 1. 到期日强制平仓
        # =====================================================
        if has_position and self.lock_expiry is not None:

            if date >= self.lock_expiry:

                print("今天期权到期，全部平仓：", date)

                orders += self._close_all(
                    option_snapshot,
                    option_pos,
                    underlying_pos,
                    portfolio
                )

                self._reset()

                return orders

        # =====================================================
        # 2. basis回落平仓
        # =====================================================
        if has_position:

            if basis <= self.down_threshold:

                print("basis回落，全部平仓：", date)

                orders += self._close_all(
                    option_snapshot,
                    option_pos,
                    underlying_pos,
                    portfolio
                )

                self._reset()

                return orders

        # =====================================================
        # 3. 动态ATM Roll
        # =====================================================
        if has_position and self.current_atm_strike is not None:

            strike_diff = abs(spot - self.current_atm_strike)

            if strike_diff >= self.atm_roll_threshold:

                print("ATM发生漂移，进行Roll：", date)

                print("旧ATM:", self.current_atm_strike)
                print("新ATM:", atm_strike)

                # =========================================
                # 先平旧期权仓
                # ETF不动
                # =========================================
                for oid, p in option_pos.items():

                    option = option_snapshot[
                        option_snapshot["期权代码"] == oid
                    ].iloc[0]

                    orders.append({
                        "instrument": "option",
                        "期权代码": oid,
                        "quantity": -p["quantity"],
                        "price": option["收盘价"],
                        "expiry": option["expiry_date"],
                        "type": option["type"]
                    })

                # =========================================
                # 开新ATM synthetic
                # short call + long put
                # =========================================
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

                # 更新ATM
                self.current_atm_strike = atm_strike
                portfolio.set_position_strike(atm_strike)
                portfolio.set_position_expiry(call["expiry_date"])

                return orders

        # =====================================================
        # 4. 开仓
        # =====================================================
        if not has_position:

            if (
                basis >= self.upper_threshold
                and call["expiry_date"] > date
            ):

                print("今天开仓：", date)

                # =========================================
                # ETF多头
                # =========================================
                orders.append({
                    "instrument": "underlying",
                    "quantity": self.quantity * 10000,
                    "price": spot
                })

                # =========================================
                # synthetic short future
                # short call + long put
                # =========================================
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

                # =========================================
                # 记录状态
                # =========================================
                self.entry_date = date

                self.lock_expiry = call["expiry_date"]

                self.current_atm_strike = atm_strike

                portfolio.set_position_strike(atm_strike)
                portfolio.set_position_expiry(call["expiry_date"])


                print("ATM strike:", atm_strike)

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
    # reset
    # =========================================================
    def _reset(self):

        self.entry_date = None

        self.lock_expiry = None

        self.current_atm_strike = None