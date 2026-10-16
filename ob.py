# Edge or Myth - Order Block backtest engine (15-minute candles, trades simulated on 1-minute data)
# Order block (Smart Risk / LuxAlgo definition):
#   bullish OB = last DOWN candle (close<open) before a displacement leg that
#     (1) leaves a fair value gap (inefficiency) and (2) closes above the last confirmed swing high (break of structure).
#   bearish OB = mirror (last UP candle before a down displacement with FVG + close below last swing low).
# Trade: limit order at the OB edge nearest price (top of a bullish OB / bottom of a bearish OB),
#   stop beyond the far edge, target = rr x risk (source: 1:2). First touch only (fresh / unmitigated).
import pandas as pd, numpy as np
SESS = {'NQ': (13.5, 20.0), 'GOLD': (7.0, 20.0)}

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def trend4h(m):
    c = m.close.resample('4h').last().dropna(); e = ema(c, 50)
    t = np.sign(c - e).shift(1)          # completed 4h bar only
    return t.reindex(m.index, method='ffill').fillna(0).values

def find_obs(m, k=2, lookback=10, max_wait=3):
    O, H, L, C = (m[c].values for c in ('open', 'high', 'low', 'close')); n = len(m)
    ph = np.full(n, np.nan); pl = np.full(n, np.nan)
    for i in range(k, n - k):
        if H[i] == H[i - k:i + k + 1].max(): ph[i] = H[i]
        if L[i] == L[i - k:i + k + 1].min(): pl[i] = L[i]
    obs = []; lastSH = lastSL = np.nan; iSH = iSL = -1; prevSL = prevSH = np.nan
    pend = []   # FVGs waiting for a break of structure
    for i in range(3, n):
        j = i - k
        if j >= 0 and not np.isnan(ph[j]): prevSH, lastSH, iSH = lastSH, ph[j], j
        if j >= 0 and not np.isnan(pl[j]): prevSL, lastSL, iSL = lastSL, pl[j], j
        # new FVG (inefficiency) at bars i-2,i-1,i
        if H[i - 2] < L[i]: pend.append((1, i, lastSH))
        if L[i - 2] > H[i]: pend.append((-1, i, lastSL))
        keep = []
        for s, ig, lvl in pend:
            if i - ig > max_wait or np.isnan(lvl): continue
            bos = (C[i] > lvl) if s == 1 else (C[i] < lvl)
            if not bos: keep.append((s, ig, lvl)); continue
            # last opposite candle before the displacement leg (search back from the FVG's first candle)
            ob = -1
            for q in range(ig - 1, max(ig - 1 - lookback, 0), -1):
                if (s == 1 and C[q] < O[q]) or (s == -1 and C[q] > O[q]): ob = q; break
            if ob < 0: continue
            top, bot = H[ob], L[ob]
            # sweep: OB candle (or the bars just before it) took out a prior swing point
            lo_start = max(ob - 3, 0)
            if s == 1:
                ref = [pl[q] for q in range(max(ob - 288, 0), lo_start) if not np.isnan(pl[q])]
                swept = bool(ref) and L[lo_start:ob + 1].min() < ref[-1] and C[ob] > ref[-1] - 1e9
            else:
                ref = [ph[q] for q in range(max(ob - 288, 0), lo_start) if not np.isnan(ph[q])]
                swept = bool(ref) and H[lo_start:ob + 1].max() > ref[-1]
            fv_top = L[ig] if s == 1 else H[ig]; fv_bot = H[ig - 2] if s == 1 else L[ig - 2]; fv_sl = L[ig - 1] if s == 1 else H[ig - 1]
            obs.append(dict(side=s, i_ob=ob, i_conf=i, top=top, bot=bot, swept=swept, fv_top=fv_top, fv_bot=fv_bot, fv_sl=fv_sl, i_fvg=ig))
        pend = keep
    # de-duplicate (same OB candle confirmed twice)
    seen = set(); out = []
    for o in obs:
        key = (o['side'], o['i_ob'])
        if key in seen: continue
        seen.add(key); out.append(o)
    return out

def run(sym, tf='m15', rr=2.0, spread=0.0, start='2025-10-01', end='2026-10-01', expiry_days=5,
        f_sweep=False, f_trend=False, f_mid=False, f_kill=False, entry='edge', minstop=0.0003, buf=0.0, target='rr', minrr=0.0, zone='ob'):
    m = pd.read_pickle(f'{sym}_{tf}.pkl'); m1 = pd.read_pickle(f'{sym}_m1.pkl')
    T = m.index; T1 = m1.index
    H1, L1, C1 = m1.high.values, m1.low.values, m1.close.values
    tr = trend4h(m)
    s0, s1 = SESS[sym]
    obs = find_obs(m)
    t0, t1 = pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC')
    trades = []; busy_until = pd.Timestamp('1970-01-01', tz='UTC')
    obs.sort(key=lambda o: o['i_conf'])
    cand = []
    for o in obs:
        tc = T[o['i_conf']] + (T[1]-T[0] if (T[1]-T[0])<pd.Timedelta(hours=5) else pd.Timedelta(hours=4))       # OB known after the confirming 15m bar closes
        if tc < t0 - pd.Timedelta(days=expiry_days) or tc >= t1: continue
        s = o['side']; top, bot = o['top'], o['bot']
        if entry == 'edge': ent = top if s == 1 else bot
        else: ent = (top + bot) / 2                              # 50% "mean threshold"
        sl = (bot - buf) if s == 1 else (top + buf)
        if zone == 'fvg':      ent, sl = o['fv_top'], o['fv_sl']          # trade the gap of the same move instead
        elif zone == 'fvg_obstop': ent = o['fv_top']                       # enter at the gap, stop under the order block
        risk = (ent - sl) * s
        if risk <= minstop * ent: continue
        tp = ent + s * rr * risk
        if f_sweep and not o['swept']: continue
        a = T1.searchsorted(tc); b = T1.searchsorted(tc + pd.Timedelta(days=expiry_days))
        if b <= a: continue
        # first touch (by at least the spread)
        if s == 1: hit = np.nonzero(L1[a:b] <= ent - spread)[0]
        else:      hit = np.nonzero(H1[a:b] >= ent + spread)[0]
        # invalidation: a 15m close through the far edge before the touch kills the OB (handled by the stop logic anyway)
        if not len(hit): continue
        ie = a + hit[0]; te = T1[ie]
        if te < t0 or te >= t1: continue
        hr = te.hour + te.minute / 60
        if not (s0 <= hr < s1): continue                      # first touch outside session = OB used up
        if f_kill and sym == 'GOLD' and not (7 <= hr < 17): continue
        if f_mid and te.dayofweek not in (1, 2, 3): continue
        if f_trend:
            i15 = T.searchsorted(te, side='right') - 1
            if tr[i15] != s: continue
        if target == 'ext':
            a0 = T1.searchsorted(T[c_i] if False else T[o['i_ob']])
            tp = H1[a0:ie].max() if s == 1 else L1[a0:ie].min()
            if (tp - ent) * s < max(minrr, 0.3) * risk: continue
        cand.append(dict(o=o, te=te, ie=ie, ent=ent, sl=sl, tp=tp, risk=risk))
    cand.sort(key=lambda c: c['te'])
    for c in cand:
        if c['te'] <= busy_until: continue
        s = c['o']['side']; ent, sl, tp, risk, ie, te = c['ent'], c['sl'], c['tp'], c['risk'], c['ie'], c['te']
        dayend = te.floor('D') + pd.Timedelta(hours=21)
        if te >= dayend: dayend += pd.Timedelta(days=1)
        e = T1.searchsorted(dayend)
        res = None; ex = e - 1
        for jj in range(ie, e):
            hs = (L1[jj] <= sl) if s == 1 else (H1[jj] >= sl)
            ht = ((H1[jj] >= tp) if s == 1 else (L1[jj] <= tp)) and jj > ie
            if hs: res = -1.0; ex = jj; break                 # stop first if both in same minute (conservative)
            if ht: res = (tp - ent) * s / risk; ex = jj; break
        if res is None: res = (C1[ex] - ent) * s / risk
        res -= spread / risk
        trades.append(dict(sym=sym, t_ob=T[c['o']['i_ob']], t_entry=te, t_exit=T1[ex], side=s, ob_top=c['o']['top'], ob_bot=c['o']['bot'],
                           entry=ent, sl=sl, tp=tp, risk=risk, swept=c['o']['swept'], r=res))
        busy_until = T1[ex]
    return pd.DataFrame(trades)

def summ(df):
    if not len(df): return 'n=0'
    pf = df.r[df.r > 0].sum() / max(1e-9, -df.r[df.r < 0].sum())
    eq = df.r.cumsum() * 100; dd = (eq - eq.cummax()).min()
    return f"n={len(df):4d} win={(df.r>0).mean():4.0%} PF={pf:4.2f} $={df.r.sum()*100:+8.0f} maxDD={dd:7.0f}"

def quarters(df):
    q = df.t_entry.dt.tz_localize(None).dt.to_period('Q')
    return ' '.join(f"{p}:{g.r.sum()*100:+.0f}" for p, g in df.groupby(q))
