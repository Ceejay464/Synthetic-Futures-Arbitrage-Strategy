import pandas as pd

class TemplateOptionStrategy:

    def __init__(self):
        self.entry_date = None
        self.exit_date = None
        self.position_expiry_date = None
        self.quantity = 1

    def generate_signal(self, timestamp, underlying_snapshot, option_snapshot, portfolio, option_db):
        date = timestamp
        orders = []

        if option_snapshot is None or option_snapshot.empty:
            return orders

        # ==============================
        # spot
        # ==============================
        spot = underlying_snapshot.iloc[0]["收盘价(元)"]

        # ==============================
        # front expiry chain
        # ==============================
        front_chain = option_db.get_front_expiry_chain(option_snapshot)

        if front_chain is None:
            return orders

        # expiry of front chain
        front_expiry = front_chain["expiry_date"].iloc[0]

        # ==============================
        # ATM
        # ==============================
        atm_strike = option_db.get_atm_strike(front_chain, spot)
        atm_call, atm_put = option_db.get_atm_pair(front_chain, atm_strike)

        if atm_call is None or atm_put is None:
            return orders

        call = atm_call.iloc[0]
        put = atm_put.iloc[0]

        # ==============================
        # load position
        # ==============================        
        current_position = portfolio.get_positions()
        underlying_position = current_position["underlying"]
        option_position = current_position["options"]

        # =========================================================
        # RULE 0: if front expiry is today → avoid trading or flatten
        # =========================================================
        if self.position_expiry_date == date:

            # 如果已经有仓位 → 平仓
            # close underlying
            print("持仓到期，今天平仓")
            if (underlying_position != 0):
                orders.append({
                    "instrument": "underlying",
                    "quantity": -underlying_position
                })

            # close option
            if len(option_position) != 0:

                for oid in list(option_position.keys()):

                    pos = option_position[oid]
                    qty = pos["quantity"]

                    if qty == 0:
                        continue

                    option = option_snapshot[option_snapshot["期权代码"] == oid].iloc[0]
                    orders.append({
                    "instrument": "option",
                    "期权代码": oid,
                    "quantity": -qty,
                    "price": option["收盘价"],
                    "expiry": option["expiry_date"],
                    "type": option["type"]
                    })

            self.position_expiry_date = None

            return orders  # 不开新仓

        # =========================================================
        # EXIT: hold 5 days
        # =========================================================
        if self.entry_date is not None:

            holding_days = (date - self.entry_date).days

            if holding_days >= 5:
                
                # 持仓大于等于五天则平仓
                # close underlying
                print("已持仓5日，今天平仓")
                if date == pd.Timestamp("2024-09-30"):
                    print(option_position)

                if (underlying_position != 0):
                    orders.append({
                        "instrument": "underlying",
                        "quantity": -underlying_position
                    })
                    
                # close option
                if len(option_position) != 0:

                    for oid in list(option_position.keys()):

                        pos = option_position[oid]
                        qty = pos["quantity"]

                        if qty == 0:
                            continue

                        option = option_snapshot[option_snapshot["期权代码"] == oid].iloc[0]
                        orders.append({
                        "instrument": "option",
                        "期权代码": oid,
                        "quantity": -qty,
                        "price": option["收盘价"],
                        "expiry": option["expiry_date"],
                        "type": option["type"]
                        })

                self.position_expiry_date = None
                self.entry_date = None

        # =========================================================
        # ENTRY
        # =========================================================
        if (len(option_position) == 0) and (underlying_position == 0):

            if front_expiry == date:
                print("今天可以开仓，但今天是到期日，所以不开仓. 今天是：", front_expiry)
                
            else:
                orders.append({
                    "instrument": "option",
                    "期权代码": call["期权代码"],
                    "quantity": self.quantity,
                    "price": call["收盘价"],
                    "expiry": call["expiry_date"],
                    "type": "Call"
                })

                orders.append({
                    "instrument": "option",
                    "期权代码": put["期权代码"],
                    "quantity": self.quantity,
                    "price": put["收盘价"],
                    "expiry": put["expiry_date"],
                    "type": "Put"
                })

                orders.append({
                        "instrument": "underlying",
                        "quantity": self.quantity * 10000
                    })

                self.position_expiry_date = front_expiry
                self.entry_date = date
                print("今天开仓，到期日为：", self.position_expiry_date)
            

        return orders