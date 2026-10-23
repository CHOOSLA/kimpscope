"""국내·해외 시세와 김치 프리미엄.

김프(%) = 국내 원화가 / (바이낸스 USDT가 × 원/달러 기준 환율) − 1.
USDT/KRW 체결가 기준 차이(premium_usdt)와 테더 프리미엄(tether_premium)은 따로 둔다. 둘을 곱하면 김프와 같아진다.

대상은 업비트 KRW 마켓 ∩ 바이낸스 USDT 현물 중 거래 상태가 TRADING인 코인이다.
거래가 멈춘(BREAK) 심볼도 현재가 응답에 마지막 가격이 남아 있어, 걸러내지 않으면 김프가 수천 %로 나온다
(2026-10-23 실측: DATA +16,826%, PROS +1,540%, WAVES −75.8%).
화면(/api/market)에는 FEATURED 코인만 보내고, 전체는 RAG 근거(quote)에서 쓴다.
"""
import logging,time,threading,requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from . import fx as fx_rates

log=logging.getLogger(__name__)
lock = threading.Lock()
cache = {'at': 0, 'data': None}
trading_cache = {'at': 0, 'symbols': None}
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'application/json',
})
session.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 502, 503], respect_retry_after_header=True)))

FEATURED = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'AVAX', 'LINK', 'DOT', 'TRX']
SYMBOLS = FEATURED  # 하위 호환
BINANCE_HOSTS = ['https://api.binance.com', 'https://api1.binance.com', 'https://data-api.binance.vision']
TRADING_TTL = 3600

def _binance(path, params=None, timeout=5):
    last_err = None
    for host in BINANCE_HOSTS:
        try:
            r = session.get(host + path, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
    raise last_err or RuntimeError("모든 바이낸스 엔드포인트 응답 없음")

def get_binance_prices():
    return {x['symbol']: float(x['price']) for x in _binance('/api/v3/ticker/price')}

def binance_trading_bases():
    """거래 중인 USDT 현물의 기준 코인 집합. 조회 실패 시 None (호출 측은 FEATURED로 좁힌다)."""
    if trading_cache['symbols'] is not None and time.time() - trading_cache['at'] < TRADING_TTL:
        return trading_cache['symbols']
    try:
        info = _binance('/api/v3/exchangeInfo', {'permissions': 'SPOT'}, timeout=15)
        bases = {s['baseAsset'] for s in info.get('symbols', []) if s.get('status') == 'TRADING' and s.get('quoteAsset') == 'USDT'}
        if bases:
            trading_cache.update(at=time.time(), symbols=bases)
    except Exception as e:
        log.warning('바이낸스 거래 상태 조회 실패: %s', type(e).__name__)
    return trading_cache['symbols']

def _upbit_krw():
    u = session.get('https://api.upbit.com/v1/ticker/all', params={'quote_currencies': 'KRW'}, timeout=5)
    u.raise_for_status()
    return {x['market'][4:]: x for x in u.json()}

def _bithumb_krw():
    b_res = session.get('https://api.bithumb.com/public/ticker/ALL_KRW', timeout=5)
    b_res.raise_for_status()
    out = {}
    for s, row in b_res.json().get('data', {}).items():
        if isinstance(row, dict) and row.get('closing_price'):
            out[s] = {'trade_price': float(row['closing_price']), 'signed_change_rate': float(row.get('fluctate_rate_24H', 0)) / 100.0, 'timestamp': int(time.time() * 1000)}
    return out

def _compute():
    last_error = []
    try:
        bn = get_binance_prices()
    except Exception as e:
        bn = None
        last_error.append(f"Binance {type(e).__name__}")
    if not bn:
        return None, last_error

    source_name = "Upbit + Binance"
    try:
        domestic = _upbit_krw()
    except Exception as e:
        last_error.append(f"Upbit {type(e).__name__}")
        domestic = None
    if not domestic:
        try:
            domestic = _bithumb_krw()
            source_name = "Bithumb + Binance (업비트 응답 실패 대체)"
        except Exception as e:
            last_error.append(f"Bithumb {type(e).__name__}")
            return None, last_error

    trading = binance_trading_bases()
    candidates = [s for s in domestic if s != 'USDT' and (s in trading if trading is not None else s in FEATURED)]
    usdt_krw = (domestic.get('USDT') or {}).get('trade_price')
    official = fx_rates.usd_krw()
    rate = official['rate'] if official else None

    rows = {}
    for symbol in candidates:
        x = domestic[symbol]
        foreign = bn.get(symbol + 'USDT')
        if not foreign:
            continue
        rows[symbol] = dict(
            symbol=symbol,
            domestic=x['trade_price'],
            foreign=foreign,
            converted=foreign * rate if rate else None,
            premium=(x['trade_price'] / (foreign * rate) - 1) * 100 if rate else None,
            premium_usdt=(x['trade_price'] / (foreign * usdt_krw) - 1) * 100 if usdt_krw else None,
            change=x.get('signed_change_rate', 0) * 100,
            exchange_timestamp=x.get('timestamp', int(time.time() * 1000)),
        )
    result = {
        'all_rows': rows,
        'fx': rate,
        'fx_source': official['source'] if official else None,
        'fx_date': official['date'] if official else None,
        'fx_label': f"원/달러 {official['source']} ({official['date']})" if official else '원/달러 환율 미확보 · 김프 산출 보류',
        'usdt_krw': usdt_krw,
        'tether_premium': (usdt_krw / rate - 1) * 100 if usdt_krw and rate else None,
        'trading_filter': 'binance_trading' if trading is not None else 'featured_only',
        'received_at': int(time.time() * 1000),
        'stale': False,
        'source': source_name,
        'error': None if official else (fx_rates.cache.get('error') or '환율 없음'),
    }
    return result, last_error

def _public(data):
    """화면용: FEATURED 순서의 행만. 전체 행 수는 available로 알린다."""
    rows = [data['all_rows'][s] for s in FEATURED if s in data['all_rows']]
    return {k: v for k, v in data.items() if k != 'all_rows'} | {'rows': rows, 'available': len(data['all_rows'])}

def full_snapshot():
    with lock:
        if cache['data'] and time.time() - cache['at'] < 5:
            return cache['data']
        data, errors = _compute()
        if data:
            cache.update(at=time.time(), data=data)
            return data
        message = ' / '.join(errors) or '알 수 없는 오류'
        log.warning('시세 갱신 실패: %s', message)
        if cache['data']:
            # 이전 값을 돌려주되, 지연됐다는 사실과 이번 실패 원인을 함께 알린다
            return cache['data'] | {'stale': True, 'error': message}
        return {'all_rows': {}, 'stale': True, 'received_at': None, 'source': '외부 시세 연결 실패', 'error': message, 'fx': None, 'fx_label': '원/달러 환율 미확보'}

def snapshot():
    return _public(full_snapshot())

def quote(symbol):
    """RAG 근거용 단일 코인 시세. 없으면 None."""
    data = full_snapshot()
    row = data.get('all_rows', {}).get(symbol)
    if not row:
        return None
    return {**row, **{k: data.get(k) for k in ('fx', 'fx_source', 'fx_date', 'usdt_krw', 'tether_premium', 'received_at', 'stale', 'source', 'error')}}

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
