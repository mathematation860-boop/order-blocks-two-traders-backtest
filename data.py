import pandas as pd
B='/mnt/user-data/uploads/data-dukascopy/'
def load_m1(sym):
    if sym=='NQ': fs=[B+f'us100/US100_M1_bid_ask_{y}.parquet' for y in (2025,2026)]
    else: fs=[B+f'bid_ask/XAUUSD_M1_bid_ask_{y}.parquet' for y in (2025,2026)]
    d=pd.concat([pd.read_parquet(f) for f in fs])
    d['timestamp']=pd.to_datetime(d.timestamp,utc=True)
    d=d.set_index('timestamp').sort_index()
    return d
def bid(d):
    x=d[['bid_open','bid_high','bid_low','bid_close']].copy(); x.columns=['open','high','low','close']; return x
def rs(d,f): return d.resample(f).agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
if __name__=='__main__':
    for s in ('GOLD','NQ'):
        d=load_m1(s); print(s, d.index[0], d.index[-1], len(d), list(d.columns)[:10])
        sp=(d.ask_close-d.bid_close); h=d.index.hour
        print(' spread median all', round(sp.median(),3), ' session', round(sp[(h>=13)&(h<20)].median(),3))
        b=bid(d); b.to_pickle(f'{s}_m1.pkl'); rs(b,'15min').to_pickle(f'{s}_m15.pkl'); rs(b,'30min').to_pickle(f'{s}_m30.pkl')
