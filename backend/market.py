import time,threading,requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
lock=threading.Lock();cache={'at':0,'data':None};session=requests.Session()
session.headers['User-Agent']='KimpScope-EducationalResearch/0.2'
session.mount('https://',HTTPAdapter(max_retries=Retry(total=2,backoff_factor=.5,status_forcelist=[429,502,503],respect_retry_after_header=True)))
SYMBOLS=['BTC','ETH','XRP','SOL','DOGE','ADA','AVAX','LINK','DOT','TRX']
def snapshot():
    with lock:
        if cache['data'] and time.time()-cache['at']<5:return cache['data']
        try:
            u=session.get('https://api.upbit.com/v1/ticker',params={'markets':','.join('KRW-'+s for s in SYMBOLS+['USDT'])},timeout=10);u.raise_for_status();up={x['market'][4:]:x for x in u.json()}
            b=session.get('https://data-api.binance.vision/api/v3/ticker/price',timeout=10);b.raise_for_status();bn={x['symbol']:float(x['price']) for x in b.json()}
            fx=up['USDT']['trade_price'];rows=[]
            for symbol in SYMBOLS:
                x=up.get(symbol);foreign=bn.get(symbol+'USDT')
                if not x or not foreign:continue
                rows.append(dict(symbol=symbol,domestic=x['trade_price'],foreign=foreign,converted=foreign*fx,premium=(x['trade_price']/(foreign*fx)-1)*100,change=x['signed_change_rate']*100,exchange_timestamp=x['timestamp']))
            result={'rows':rows,'fx':fx,'fx_label':'업비트 USDT/KRW 기준','received_at':int(time.time()*1000),'stale':False,'source':'Upbit + Binance public API'}
            cache.update(at=time.time(),data=result);return result
        except requests.RequestException:
            if cache['data']:return cache['data']|{'stale':True}
            return {'rows':[],'stale':True,'received_at':None,'source':'외부 시세 연결 실패'}
history_cache={}
def candles(symbol,period):
    key=(symbol,period)
    with lock:
        if key in history_cache and time.time()-history_cache[key]['at']<60:return history_cache[key]['points']
    path={'1H':'minutes/1','24H':'minutes/30','7D':'days'}[period];count={'1H':60,'24H':48,'7D':7}[period]
    r=session.get('https://api.upbit.com/v1/candles/'+path,params={'market':'KRW-'+symbol,'count':count},timeout=10);r.raise_for_status()
    points=[{'time':x['candle_date_time_kst'],'price':x['trade_price']} for x in reversed(r.json())]
    with lock:history_cache[key]={'at':time.time(),'points':points}
    return points
