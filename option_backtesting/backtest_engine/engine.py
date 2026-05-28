import pandas as pd

class BacktestEngine:

    def __init__(
        self,
        option_db,
        option_strategy,
        underlying_strategy,
        portfolio
    ):
        self.option_db = option_db
        self.option_strategy = option_strategy
        self.underlying_strategy = underlying_strategy
        self.portfolio = portfolio

        self.timeline = None
        self.results = []

    # ---------------------------------------------------------
    # Build timeline
    # ---------------------------------------------------------
    def prepare_timeline(self, start=None, end=None):

        times = self.option_db.underlying_df["日期"].unique()
        times = sorted(times)

        if start is not None:
            start = pd.Timestamp(start)
            times = [t for t in times if t >= start]

        if end is not None:
            end = pd.Timestamp(end)
            times = [t for t in times if t <= end]

        self.timeline = times

    # ---------------------------------------------------------
    # Get snapshot
    # ---------------------------------------------------------
    def get_option_snapshot(self, date):

        chain = self.option_db.get_chain(date)
        if chain is None:
            return None

        return chain

    def get_underlying_snapshot(self, date):

        df = self.option_db.underlying_df
        snap = df[df["日期"] == date]

        return snap

    # ---------------------------------------------------------
    # Execute orders
    # ---------------------------------------------------------
    def process_orders(self, orders, timestamp, spot_price):

        if not orders:
            return

        for order in orders:

            if order["instrument"] == "option":

                self.portfolio.update_option(
                    timestamp=timestamp,
                    option_id=order["期权代码"],
                    quantity=order["quantity"],
                    price=order["price"],
                    expiry=order["expiry"],
                    option_type=order["type"]
                )

            elif order["instrument"] == "underlying":

                self.portfolio.update_underlying(
                    timestamp=timestamp,
                    quantity=order["quantity"],
                    price=spot_price
                )

    # ---------------------------------------------------------
    # Main loop
    # ---------------------------------------------------------
    def run(self):

        if self.timeline is None:
            self.prepare_timeline()


        for date in self.timeline:
            print(date)
            date = pd.Timestamp(date)

            # ===== snapshot =====
            option_snapshot = self.get_option_snapshot(date)
            underlying_snapshot = self.get_underlying_snapshot(date)

            if option_snapshot is None or underlying_snapshot.empty:
                print("today no data")
                continue

            # ===== spot =====
            spot_price = self.option_db.get_spot(date)

            # ===== strategy =====
            option_orders = self.option_strategy.generate_signal(
                timestamp=date,
                underlying_snapshot=underlying_snapshot,
                option_snapshot=option_snapshot,
                portfolio=self.portfolio,
                option_db=self.option_db
            )

            self.process_orders(option_orders, date, spot_price)

            underlying_orders = self.underlying_strategy.generate_signal(
                timestamp=date,
                underlying_snapshot=underlying_snapshot,
                option_snapshot=option_snapshot,
                portfolio=self.portfolio,
                option_db=self.option_db
            )

            self.process_orders(underlying_orders, date, spot_price)

            # ===== equity =====
            self.portfolio.get_equity(
                timestamp=date,
                option_data=option_snapshot,
                underlying_price=spot_price
            )

            self.results.append({
                "timestamp": date,
                "equity": self.portfolio.equity_history[-1]["equity"]
            })

        return pd.DataFrame(self.results)