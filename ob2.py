# Order Block "fix" lab: one OB definition, many add-ons, same year as the FVG video (Oct 2025 - Sep 2026).
import pandas as pd, numpy as np
from ob import find_obs, SESS, trend4h

def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

def candidates(sym, tf='m15', start='2025-10-01', end='2026-10-01', expiry_days=5, spread=0.0):
    m = pd.read_pickle(f'{sym}_{tf}.pkl'); m1 = pd.read_pickle(f'{sym}_m1.pkl')
    T = m.index; O, H, L, C = (m[c].values for c in ('open', 'high', 'low', 'close'))
    T1 = m1.index; H1, L1 = m1.high.values, m1.low.values
    step = T[1] - T[0]; tr = trend4h(m); r14 = rsi(m.close).values
    day = m.resample('1D').agg({'high': 'max', 'low': 'min'}).dropna()
    pdh = day.high.shift(1).reindex(T, method='ffill').values; pdl = day.low.shift(1).reindex(T, method='ffill').values
    t0, t1 = pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC')
    out = []
    for o in find_obs(m):
        s = o['side']; top, bot = o['top'], o['bot']
        tc = T[o['i_conf']] + step
        if tc < t0 - pd.Timedelta(days=expiry_days) or tc >= t1: continue
        edge = top if s == 1 else bot; far = bot if s == 1 else top
        a = T1.searchsorted(tc); b = T1.searchsorted(tc + pd.Timedelta(days=expiry_days))
        hit = np.nonzero(L1[a:b] <= edge - spread)[0] if s == 1 else np.nonzero(H1[a:b] >= edge + spread)[0]
        if not len(hit): continue
        ie = a + hit[0]; te = T1[ie]
        if te < t0 or te >= t1: continue
        ext = H1[T1.searchsorted(T[o['i_ob']]):ie].max() if s == 1 else L1[T1.searchsorted(T[o['i_ob']]):ie].min()
        i15 = T.searchsorted(te, side='right') - 1
        fvt, fvb = o['fv_top'], o['fv_bot']
        fvg_in = (min(top, fvt) >= max(bot, fvb)) if s == 1 else (min(top, fvb) >= max(bot, fvt))  # gap overlaps the OB zone
        legmid = (ext + far) / 2
        out.append(dict(o=o, s=s, top=top, bot=bot, edge=edge, far=far, ext=ext, ie=ie, te=te, i15=i15,
                        swept=o['swept'], trend=(tr[i15] == s), fvg_in=fvg_in,
                        disc=((edge < legmid) if s == 1 else (edge > legmid)),
                        rsi_ok=((r14[i15 - 1] < 45) if s == 1 else (r14[i15 - 1] > 55)),
                        pd_level=((bot <= pdl[i15] <= top) if s == 1 else (bot <= pdh[i15] <= top)),
                        hour=te.hour + te.minute / 60, dow=te.dayofweek,
                        disp=abs(ext - edge) / max(1e-9, abs(edge - far))))
    return out, (m, m1)

def simulate(cands, mm, sym, spread, entry='limit', target='ext', rr=2.0, minrr=0.5, filt=None, sess=True, confirm_bars=8, buf=0.0, stopmode='ob'):
    m, m1 = mm; T = m.index; O, H, L, C = (m[c].values for c in ('open', 'high', 'low', 'close'))
    T1 = m1.index; H1, L1, C1 = m1.high.values, m1.low.values, m1.close.values
    s0, s1 = SESS[sym]; step = T[1] - T[0]
    sel = []
    for c in cands:
        if filt and not filt(c): continue
        if sess and not (s0 <= c['hour'] < s1): continue
        s = c['s']
        if entry == 'limit':
            ent = c['edge']; ie = c['ie']; te = c['te']
        else:   # 'confirm': after the touch, a 15m candle must close back outside the zone in our direction (rejection)
            j0 = c['i15']; ent = None
            for j in range(j0, min(j0 + confirm_bars, len(T))):
                if (s == 1 and L[j] <= c['far']) or (s == -1 and H[j] >= c['far']): break      # stopped before confirming
                if (s == 1 and C[j] > c['edge'] and C[j] > O[j]) or (s == -1 and C[j] < c['edge'] and C[j] < O[j]):
                    ent = C[j]; te = T[j] + step; ie = T1.searchsorted(te); break
            if ent is None or ie >= len(T1): continue
        sl = (c['far'] - buf) if s == 1 else (c['far'] + buf)
        if stopmode == 'mid': sl = (c['top'] + c['bot']) / 2
        risk = (ent - sl) * s
        if risk <= 0.0003 * ent: continue
        if target == 'ext': tp = c['ext']
        else: tp = ent + s * rr * risk
        if (tp - ent) * s < minrr * risk: continue
        sel.append(dict(c=c, ent=ent, sl=sl, tp=tp, risk=risk, ie=ie, te=te))
    sel.sort(key=lambda x: x['te']); busy = pd.Timestamp('1970', tz='UTC'); out = []
    for x in sel:
        if x['te'] <= busy: continue
        s = x['c']['s']; ent, sl, tp, risk, ie, te = x['ent'], x['sl'], x['tp'], x['risk'], x['ie'], x['te']
        de = te.floor('D') + pd.Timedelta(hours=21)
        if te >= de: de += pd.Timedelta(days=1)
        e = T1.searchsorted(de); res = None; ex = max(e - 1, ie)
        for jj in range(ie, e):
            hs = (L1[jj] <= sl) if s == 1 else (H1[jj] >= sl)
            ht = ((H1[jj] >= tp) if s == 1 else (L1[jj] <= tp)) and (jj > ie or entry != 'limit')
            if hs: res = -1.0; ex = jj; break
            if ht: res = (tp - ent) * s / risk; ex = jj; break
        if res is None: res = (C1[ex] - ent) * s / risk
        res -= spread / risk
        c = x['c']
        out.append(dict(sym=sym, t_ob=m.index[c['o']['i_ob']], t_entry=te, t_exit=T1[ex], side=s, ob_top=c['top'], ob_bot=c['bot'],
                        entry=ent, sl=sl, tp=tp, risk=risk, r=res))
        busy = T1[ex]
    return pd.DataFrame(out)
