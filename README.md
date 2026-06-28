# Synthetic Futures vs ETF Arbitrage Strategy

## Overview

This strategy exploits pricing inefficiencies between ETFs and their corresponding options markets by constructing **synthetic futures** positions. When the synthetic futures price deviates significantly from the underlying ETF price, the strategy executes arbitrage trades to capture the mispricing.

The backtest is conducted using the **`PortfolioStrategy`** module of **vn.py**.

---

## Strategy Logic

### 1. Core Concept

A **synthetic futures** position is constructed using put-call parity:

- When **Basis > Upper Threshold**, the synthetic futures is **overpriced** (significant premium)
- The strategy shorts the synthetic futures and goes long the underlying ETF

---

### 2. Entry Logic

**Trigger Condition:** `Basis > Upper Threshold`

When triggered, the strategy executes:

| Leg | Action | Quantity |
|-----|--------|----------|
| ETF | **BUY** | 1,000,000 shares |
| ATM Call Option | **SELL** | 100 contracts |
| ATM Put Option | **BUY** | 100 contracts |

> This creates a **synthetic short futures** position (sell call + buy put) hedged by a long ETF position, capturing the arbitrage spread.

---

### 3. Exit Logic

#### (a) Basis Mean Reversion Exit

**Trigger Condition:** `Basis < Lower Threshold`

When the basis narrows below the exit threshold, the mispricing has been corrected:

- Close all ETF positions
- Close all option positions
- Lock in arbitrage profit

#### (b) Expiration Forced Exit

If the position is still held at option expiration, the strategy **forces liquidation** of all positions on the expiration day.

---

### 4. Optional Enhancement: ATM Strike Roll Mechanism

> *Note: This enhancement did NOT yield significant performance improvement in backtests.*

Since the underlying ETF price fluctuates, the initially selected ATM options may gradually become OTM or ITM, reducing the synthetic futures tracking accuracy.

**Roll Logic:**

- Daily check: Has the underlying price drifted beyond the **ATM drift threshold**?
- If yes, execute **Roll**:
  - Close all option positions (ETF position remains unchanged)
  - Select new ATM call and put options
  - Reconstruct the synthetic futures position

---

## Backtest Results

### 1. SSE 50 ETF (上证50ETF)

**Period:** 2015-02-19 to 2026-04-01

| Metric | Front-Month Options | Next-Month Options |
|--------|---------------------|---------------------|
| Annualized Return | 5.21% | 6.26% |
| Annualized Volatility | 4.38% | 7.01% |
| Max Drawdown | -4.75% | -8.42% |
| Sharpe Ratio | 1.19 | 0.89 |
| Calmar Ratio | 1.10 | 0.74 |

---

### 2. CSI 300 ETF (沪深300ETF)

**Period:** 2020-01-01 to 2026-05-20

| Metric | Front-Month Options | Next-Month Options |
|--------|---------------------|---------------------|
| Annualized Return | 5.79% | 7.68% |
| Annualized Volatility | 3.67% | 7.55% |
| Max Drawdown | -2.65% | -7.68% |
| Sharpe Ratio | 1.58 | 1.02 |
| Calmar Ratio | 2.18 | 1.00 |

---

### 3. CSI 500 ETF (中证500ETF)

**Period:** 2022-11-24 to 2026-05-20

| Metric | Front-Month Options | Next-Month Options |
|--------|---------------------|---------------------|
| Annualized Return | 2.91% | 5.49% |
| Annualized Volatility | 3.39% | 6.32% |
| Max Drawdown | -3.06% | -3.75% |
| Sharpe Ratio | 0.86 | 0.87 |
| Calmar Ratio | 0.95 | 1.46 |

---

### 4. Enhanced Strategy Results (with ATM Roll Mechanism)

> *Roll threshold adjustment did NOT yield significant improvement.*

| ETF | Annualized Return | Volatility | Max DD | Sharpe | Calmar |
|-----|-------------------|------------|--------|--------|--------|
| SSE 50 | 5.26% | 4.36% | -4.71% | 1.21 | 1.12 |
| CSI 300 | 5.89% | 3.78% | -2.72% | 1.56 | 2.16 |
| CSI 500 | 3.18% | 3.82% | -3.22% | 0.83 | 0.99 |

---

## Results Analysis

### Front-Month vs Next-Month Options

| Aspect | Front-Month | Next-Month |
|--------|-------------|------------|
| **Return** | Lower | Higher |
| **Volatility** | Lower | Higher |
| **Risk-Adjusted (Sharpe/Calmar)** | **Better** | Worse |

**Explanation:**

- Next-month options allow for **longer holding periods**, reducing premature position closures and increasing the probability of successful arbitrage completion
- However, longer holding periods also expose the strategy to **greater price fluctuations and market risk**
- Front-month options offer **superior risk-adjusted returns** despite lower absolute returns

### Cross-Asset Comparison

The strategy performs **best on CSI 300 ETF**, demonstrating:

- Highest risk-adjusted returns (Sharpe: 1.19–1.58)
- Lowest drawdowns
- Most stable performance across all metrics

**CSI 300 ETF** exhibits the strongest strategy compatibility due to its high liquidity and efficient options market.

---

## Risk Management & Practical Considerations

### Slippage

Transaction costs and bid-ask spreads are accounted for using historical spread data to simulate realistic execution prices.

### Drawdown Analysis

Key drawdown events were examined for:

- ETF dividend distributions (ex-dividend price adjustments)
- Periods of extreme market volatility
- Option expiration rollover gaps

### Execution Timing

- Signals are generated using **closing prices**
- Orders are executed at the **next trading day's opening price** (T+1)

### Turnover Analysis

- Position turnover rates are tracked to evaluate transaction cost impact
- Holding periods analyzed to identify optimal rebalancing frequency

### Option Liquidity Check

- Realistic position sizing: 100 contracts per trade
- Liquidity constraints validated to ensure executable order flow
- Bid-ask spread and open interest considered for each strike

---

## Backtest Framework

- **Platform**: vn.py (`PortfolioStrategy` module)
- **Data Frequency**: Daily (signals) / Minute (execution validation)
- **Universe**:
  - SSE 50 ETF + Options Chain
  - CSI 300 ETF + Options Chain
  - CSI 500 ETF + Options Chain
