# Reproduces every number in "Two Traders, Same Order Blocks" (Edge or Myth, Video 14).
# Both traders use the SAME strong order blocks (move away >= 2x the block), same stop (far edge), same target, same costs.
#   FAST trader:    limit order at the block edge -> enters on the first touch.
#   PATIENT trader: after the touch, waits (max 8 candles) for a candle in his direction to CLOSE back outside the block; enters at that close.
# Gold 15-min target 2x risk, Nasdaq 30-min target 3x risk. $100 risk per trade, spread charged, trades simulated on 1-minute data.
import pandas as pd
from ob2 import candidates, simulate
from ob import summ, quarters
strong = lambda x: x['disp'] >= 2
for sym, tf, sp, rr in [('GOLD', 'm15', 0.60, 2.0), ('NQ', 'm30', 1.2, 3.0)]:
    c, mm = candidates(sym, tf, spread=sp, expiry_days=5)
    fast = simulate(c, mm, sym, sp, entry='limit', target='rr', rr=rr, filt=strong)
    patient = simulate(c, mm, sym, sp, entry='confirm', target='rr', rr=rr, filt=strong, confirm_bars=8)
    for name, df in (('fast', fast), ('patient', patient)):
        df.to_csv(f'trades_{name}_{sym}_{tf[1:]}m.csv', index=False)
        print(sym, name.upper(), summ(df)); print('   quarters:', quarters(df))
