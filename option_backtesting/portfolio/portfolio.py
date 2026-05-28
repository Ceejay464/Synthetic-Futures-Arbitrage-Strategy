import pandas as pd

'''
need feature in option_df:
期权代码：（int64）
收盘价： （float64）
'''
class Portfolio:
    def __init__(self, cash, multiplier=10000, option_cost=0.8, etf_cost_rate=0.0001, 
                 etf_min_cost=0, option_slippage=0.001, etf_slippage=0):
        # Core holdings
        self.option_positions = {}       # option_id -> {quantity, expiry, type}
        self.underlying_position = 0     # underlying ETF position
        self.cash = cash
        self.multiplier = multiplier

        # slippage
        self.option_slippage = option_slippage
        self.etf_slippage = etf_slippage

        # Transaction costs
        self.option_cost = option_cost
        self.etf_cost_rate = etf_cost_rate
        self.etf_min_cost = etf_min_cost

        # position_information_storage
        self.position_strike: float | None = None
        self.position_expiry: pd.Timestamp | None = None

        # Extended features
        self.trade_history = []          # list of all trades with timestamps
        self.equity_history = []         # list of portfolio equity over time (per minute)

        # Trade PnL tracking
        self.open_trade_record = {}
        self.closed_trade_history = []


    # Option trade (open/add position)
    def update_option(self, timestamp, option_id, quantity, price, expiry, option_type):

        if option_id not in self.option_positions:
            self.option_positions[option_id] = {
                "quantity": 0,
                "expiry": expiry,
                "type": option_type
            }

        pos = self.option_positions[option_id]
        pos["quantity"] += quantity

        # remove empty position
        if pos["quantity"] == 0:
            del self.option_positions[option_id]

        # =========================
        # Slippage
        # =========================

        if quantity > 0:
            trade_price = price * (1 + self.option_slippage)

        else:
            trade_price = price * (1 - self.option_slippage)

        # =========================
        # Cash update
        # =========================

        self.cash -= quantity * trade_price * self.multiplier

        # Transaction cost
        cost = abs(quantity) * self.option_cost
        self.cash -= cost

        # Record trade
        self.trade_history.append({
            "timestamp": timestamp,
            "instrument": "option",
            "id": option_id,
            "quantity": quantity,
            "market_price": price,
            "trade_price": trade_price,
            "cost": cost
        })

        self.record_trade_pnl(
            timestamp=timestamp,
            instrument="option",
            trade_id=option_id,
            quantity=quantity,
            trade_price=trade_price,
            cost=cost
        )

    # Underlying ETF trade
    def update_underlying(self, timestamp, quantity, price):

        if price is None or pd.isna(price):
            return

        # =========================
        # Slippage
        # =========================

        if quantity > 0:
            trade_price = price * (1 + self.etf_slippage)

        else:
            trade_price = price * (1 - self.etf_slippage)

        self.underlying_position += quantity

        self.cash -= quantity * trade_price

        # Transaction cost
        cost = max(
            abs(quantity * trade_price) * self.etf_cost_rate,
            self.etf_min_cost
        ) if quantity != 0 else 0

        self.cash -= cost

        self.trade_history.append({
            "timestamp": timestamp,
            "instrument": "underlying",
            "quantity": quantity,
            "market_price": price,
            "trade_price": trade_price,
            "cost": cost
        })

        self.record_trade_pnl(
            timestamp=timestamp,
            instrument="option",
            trade_id="underlying",
            quantity=quantity,
            trade_price=trade_price,
            cost=cost
        )

    # Close all positions
    def close_positions(self, timestamp, option_snapshot, spot_price):
        """
        Close all positions (options + underlying)
        option_data: pd.DataFrame with columns ['期权代码', '收盘价', 'expiry', 'type']
        spot_price: current underlying price
        """

        # Close option positions
        price_map = option_snapshot.set_index("期权代码")["收盘价"].to_dict()

        for oid in list(self.option_positions.keys()):
            pos = self.option_positions[oid]
            qty = pos["quantity"]
            if qty == 0:
                continue

            price = price_map.get(oid, None)
            if price is None or pd.isna(price):
                continue  # optionally use intrinsic value

            # Close the option position
            self.update_option(
                timestamp=timestamp,
                option_id=oid,
                quantity=-qty,
                price=price,
                expiry=pos["expiry"],
                option_type=pos["type"]
            )

        # Close underlying
        if self.underlying_position != 0:
            self.update_underlying(
                timestamp=timestamp,
                quantity=-self.underlying_position,
                price=spot_price
            )

        # set position strike, expiry to None
        self.position_strike = None
        self.position_expiry = None

    # Portfolio equity calculation
    def get_equity(self, timestamp, option_data, underlying_price):
        """
        option_data: pd.DataFrame with columns ['期权代码', '收盘价']
        underlying_price: current underlying price
        """
        equity = self.cash

        # Build price map
        price_map = option_data.set_index("期权代码")["收盘价"].to_dict()

        for oid, pos in self.option_positions.items():
            qty = pos["quantity"]
            if qty == 0:
                continue
            price = price_map.get(oid, None)
            if price is None or pd.isna(price):
                continue
            equity += qty * price * self.multiplier

        equity += self.underlying_position * underlying_price

        # Record equity
        self.equity_history.append({
            "timestamp": timestamp,
            "equity": equity
        })

        return equity

    def record_trade_pnl(self, timestamp, instrument, trade_id, quantity, trade_price, cost):

        key = (instrument, trade_id)

        # OPEN TRADE
        if key not in self.open_trade_record:

            self.open_trade_record[key] = {
                "entry_time": timestamp,
                "quantity": quantity,
                "entry_price": trade_price,
                "entry_cost": cost
            }

        # CLOSE TRADE
        else:

            open_trade = self.open_trade_record[key]
            entry_price = open_trade["entry_price"]
            entry_qty = open_trade["quantity"]

            # PnL
            pnl = (
                (trade_price - entry_price)
                * abs(quantity)
                * self.multiplier
            )

            # Short position
            if entry_qty < 0:
                pnl = -pnl

            pnl -= (
                open_trade["entry_cost"]
                + cost
            )

            # Save Closed Trade
            self.closed_trade_history.append({
                "instrument": instrument,
                "id": trade_id,

                "entry_time":
                    open_trade["entry_time"],

                "exit_time":
                    timestamp,

                "entry_price":
                    entry_price,

                "exit_price":
                    trade_price,

                "quantity":
                    abs(quantity),

                "direction":
                    "long"
                    if entry_qty > 0
                    else "short",

                "pnl":
                    pnl
            })

            # remove open trade
            del self.open_trade_record[key]


    # Get current positions
    def get_positions(self):
        return {
            "underlying": self.underlying_position,
            "options": self.option_positions
        }
    
    def set_position_strike(self, strike):
        self.position_strike = strike
        return None
    
    def set_position_expiry(self, expiry):
        self.position_expiry = expiry
        return None
    
    def get_position_strike(self):
        return self.position_strike
    
    def get_position_expiry(self):
        return self.position_expiry
    
    def get_multiplier(self):
        return self.multiplier

    # Get available cash
    def get_cash(self):
        return self.cash
    


'''
Examples:

# Initialize portfolio with $100,000 cash
portfolio = Portfolio(cash=100000, multiplier=100, option_cost=0.75, etf_cost_rate=0.0001, etf_min_cost=5)
spot_price = 480.0
timestamp = pd.Timestamp("2024-01-02 09:31")

data = {
    "ticker": ["O:SPY240102C00479000", "O:SPY240102P00475000"],
    "close": [0.01, 3.35],
    "expiry": ["2024-01-02", "2024-01-02"],
    "type": ["Call", "Put"],
    "strike": [479, 475]
}
option_df = pd.DataFrame(data)

# Buy 10 call contracts
portfolio.update_option(
    timestamp, 
    option_id="O:SPY240102C00479000", 
    quantity=10, 
    price=0.01, 
    expiry="2024-01-02", 
    option_type="Call"
)

# Buy 50 shares of SPY ETF
portfolio.update_underlying(
    timestamp,
    quantity=50,
    price=spot_price
)

# New minute data at 15:59
option_df_close = pd.DataFrame({
    "ticker": ["O:SPY240102C00479000", "O:SPY240102P00475000"],
    "close": [0.02, 3.20],  # maybe prices changed
    "expiry": ["2024-01-02", "2024-01-02"],
    "type": ["Call", "Put"]
})

close_timestamp = pd.Timestamp("2024-01-02 15:59")
portfolio.close_positions(close_timestamp, option_df_close, spot_price)
'''