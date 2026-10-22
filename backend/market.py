import time,threading,requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

lock = threading.Lock()
cache = {'at': 0, 'data': None}
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'application/json',
})
session.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 502, 503], respect_retry_after_header=True)))

SYMBOLS = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'AVAX', 'LINK', 'DOT', 'TRX']

def get_binance_prices():
    urls = [
        'https://api.binance.com/api/v3/ticker/price',
        'https://api1.binance.com/api/v3/ticker/price',
        'https://data-api.binance.vision/api/v3/ticker/price'
    ]
    last_err = None
    for u in urls:
        try:
            r = session.get(u, timeout=5)
            r.raise_for_status()
            return {x['symbol']: float(x['price']) for x in r.json()}
        except Exception as e:
            last_err = e
            continue
    raise last_err or RuntimeError("모든 바이낸스 엔드포인트 응답 없음")

def snapshot():
    with lock:
        if cache['data'] and time.time() - cache['at'] < 5:
            return cache['data']
        
        last_error = ""
        # 1. 해외 시세 (Binance)
        try:
            bn = get_binance_prices()
        except Exception as e:
            last_error = f"Binance 오류: {e}"
            bn = None

        # 2. 국내 시세 1차 시도: 업비트 (Upbit)
        up = None
        fx = None
        source_name = "Upbit + Binance"
        if bn:
            try:
                u = session.get('https://api.upbit.com/v1/ticker', params={'markets': ','.join('KRW-' + s for s in SYMBOLS + ['USDT'])}, timeout=5)
                u.raise_for_status()
                up = {x['market'][4:]: x for x in u.json()}
                if 'USDT' in up:
                    fx = up['USDT']['trade_price']
            except Exception as e:
                last_error = f"Upbit 오류({e})"
                up = None

        # 3. 국내 시세 2차 시도 (Upbit 차단/실패 시 Bithumb Fallback)
        if bn and (not up or not fx):
            try:
                b_res = session.get('https://api.bithumb.com/public/ticker/ALL_KRW', timeout=5)
                b_res.raise_for_status()
                b_data = b_res.json().get('data', {})
                # Bithumb 시세 파싱
                up = {}
                for s in SYMBOLS:
                    if s in b_data and isinstance(b_data[s], dict):
                        price = float(b_data[s].get('closing_price', 0))
                        rate = float(b_data[s].get('fluctate_rate_24H', 0))
                        up[s] = {'trade_price': price, 'signed_change_rate': rate / 100.0, 'timestamp': int(time.time() * 1000)}
                # 환율 USDT는 빗썸 USDT 또는 1380 기본 환율
                if 'USDT' in b_data and isinstance(b_data['USDT'], dict):
                    fx = float(b_data['USDT'].get('closing_price', 1380))
                else:
                    fx = 1380.0
                source_name = "Bithumb + Binance (업비트 해외차단 대체)"
                last_error = ""
            except Exception as e:
                last_error += f" / Bithumb 대체 실패: {e}"

        if bn and up and fx:
            rows = []
            for symbol in SYMBOLS:
                x = up.get(symbol)
                foreign = bn.get(symbol + 'USDT')
                if not x or not foreign:
                    continue
                rows.append(dict(
                    symbol=symbol,
                    domestic=x['trade_price'],
                    foreign=foreign,
                    converted=foreign * fx,
                    premium=(x['trade_price'] / (foreign * fx) - 1) * 100,
                    change=x.get('signed_change_rate', 0) * 100,
                    exchange_timestamp=x.get('timestamp', int(time.time() * 1000))
                ))
            result = {
                'rows': rows,
                'fx': fx,
                'fx_label': 'USDT/KRW 기준',
                'received_at': int(time.time() * 1000),
                'stale': False,
                'source': source_name
            }
            cache.update(at=time.time(), data=result)
            return result
        
        # 실패 시 캐시 또는 에러 반환
        if cache['data']:
            return cache['data'] | {'stale': True}
        return {'rows': [], 'stale': True, 'received_at': None, 'source': f'외부 시세 연결 실패: {last_error}'}

history_cache = {}
def candles(symbol, period):
    key = (symbol, period)
    with lock:
        if key in history_cache and time.time() - history_cache[key]['at'] < 60:
            return history_cache[key]['points']
    path = {'1H': 'minutes/1', '24H': 'minutes/30', '7D': 'days'}[period]
    count = {'1H': 60, '24H': 48, '7D': 7}[period]
    try:
        r = session.get('https://api.upbit.com/v1/candles/' + path, params={'market': 'KRW-' + symbol, 'count': count}, timeout=5)
        r.raise_for_status()
        points = [{'time': x['candle_date_time_kst'], 'price': x['trade_price']} for x in reversed(r.json())]
        with lock:
            history_cache[key] = {'at': time.time(), 'points': points}
        return points
    except Exception:
        return []
