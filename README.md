# Two Traders, Same Order Blocks (1-Year Backtest, Gold + Nasdaq)

Code and every trade behind the Edge or Myth video **"Two Traders, Same Order Blocks: One Lost $8,127, One Made $5,110"**.

Both traders trade the **same strong order blocks** with the same stop, target, risk and costs. The only difference is the entry:

- **Fast trader** – buys/sells the first touch of the block (limit order at the block edge), the way order blocks are usually taught.
- **Patient trader** – after the touch, waits for one candle in his direction to **close back outside the block**, then enters at that close. If price reaches the far side of the block first, he never gets in.

## Results (Oct 2025 – Sep 2026, $100 risk per trade, spread included)

| Market | Trader | Trades | Winners | Result | Quarters |
|---|---|---|---|---|---|
| Gold 15-min (target 2×) | Fast | 680 | 34% | **−$8,127** | −2,587 / −2,146 / −1,529 / −1,865 |
| Gold 15-min (target 2×) | Patient | 289 | 48% | **+$5,110** | +1,319 / +1,303 / +128 / +2,359 |
| Nasdaq 30-min (target 3×) | Fast | 310 | 27% | **−$891** | −2,825 / −27 / −1,856 / +3,816 |
| Nasdaq 30-min (target 3×) | Patient | 103 | 50% | **+$1,515** | +263 / +428 / +629 / +194 |

- Gold, fast trader: 277 of 452 losing trades were stopped out within 15 minutes; worst losing streak 18.
- Gold, patient trader: worst losing streak 10, deepest drawdown −$1,525 (≈15 trades of risk).
- On a $10,000 account ($100 = 1% risk, no compounding): fast −81%, patient +51% (gold).

## Rules (both traders)
1. **Order block** = the last opposite candle before a fast move that leaves a fair value gap and closes beyond the last swing point (2-bar pivot) within 3 candles.
2. **Strong blocks only**: before price returns, the move away must be at least 2× the block's height.
3. Stop = far edge of the block. Target = 2× risk (gold) / 3× risk (Nasdaq). One trade at a time; positions closed at 21:00 UTC. Sessions: gold 07:00–20:00 UTC, Nasdaq 13:30–20:00 UTC. Each block used once (5-day expiry).
4. Entry: fast = first touch (price must trade through the edge by at least the spread); patient = close back out within 8 candles.

## Method
- Dukascopy 1-minute bid/ask data (XAUUSD; US100 for the Nasdaq), resampled to 15/30-min.
- Spread measured from the data (gold $0.60, Nasdaq 1.2 points) and charged on every trade.
- Every trade simulated minute by minute; if stop and target hit in the same minute, the stop counts.

## Files
- `data.py` – loads data, measures spread, builds candles
- `ob.py` – order block detection and summary helpers
- `ob2.py` – block features (move size) and the trade simulator (limit = fast, confirm = patient)
- `run_two_traders.py` – reproduces all numbers above
- `trades_fast_GOLD_15m.csv`, `trades_patient_GOLD_15m.csv`, `trades_fast_NQ_30m.csv`, `trades_patient_NQ_30m.csv` – every trade

Backtest results are hypothetical and based on historical data. Past performance does not guarantee future results. Education only, not financial advice.
