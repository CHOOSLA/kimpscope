"""거래소 입출금 현황·경보 수집. 김프의 원인(입출금 중지, 시세 차이 경보)을 RAG 근거로 쓰기 위한 상태 기록.

수집 대상 (모두 키 불필요)
  빗썸 입출금 현황  public/assetsstatus/multichain/ALL  구버전 공개 API. 0/1 의미는 실측 추론(1=가능)이며 중단될 수 있다.
  빗썸 경보제       v1/market/virtual_asset_warning     가격 급등락·글로벌 시세 차이·입금량 급등 등
  업비트 유의·주의  v1/market/all?is_details=true       market_event.warning / caution

불변조건
  - 같은 응답을 여러 번 저장해도 행이 늘지 않는다. 바뀐 순간만 *_changes에 남고 현재값은 *_latest에 있다.
  - 경보는 '현재 활성 전체'로 받는다. 응답에서 빠진 경보는 종료(ended_at)로 기록한다.
  - 그래서 호출 실패를 빈 목록으로 넘기면 안 된다. 실패는 예외로 올려 저장 단계에 닿지 않게 한다.
  - 빗썸 경보와 업비트 지정은 거래소별로 따로 관리되어 서로를 종료시키지 않는다.
시각은 KST ISO 8601. observed_at은 수집기가 관찰한 시각이지 거래소가 바꾼 시각이 아니다.
"""
import json,time
from datetime import datetime,timedelta,timezone
import requests
from . import notices

KST=timezone(timedelta(hours=9))
BITHUMB='https://api.bithumb.com'
UPBIT='https://api.upbit.com/v1'
health={}

class FetchError(RuntimeError):pass

def now_kst():return datetime.now(KST).isoformat(timespec='seconds')

def connect():
    c=notices.connect()
    c.execute('CREATE TABLE IF NOT EXISTS notice_sync_state (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS exchange_status_latest (exchange TEXT NOT NULL, currency TEXT NOT NULL, net_type TEXT NOT NULL, deposit INTEGER, withdrawal INTEGER, since TEXT NOT NULL, last_seen_at TEXT NOT NULL, PRIMARY KEY(exchange,currency,net_type))')
    c.execute('CREATE TABLE IF NOT EXISTS exchange_status_changes (exchange TEXT NOT NULL, currency TEXT NOT NULL, net_type TEXT NOT NULL, deposit INTEGER, withdrawal INTEGER, prev_deposit INTEGER, prev_withdrawal INTEGER, observed_at TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS exchange_warnings_latest (exchange TEXT NOT NULL, market TEXT NOT NULL, warning_type TEXT NOT NULL, step TEXT, end_date TEXT, since TEXT NOT NULL, last_seen_at TEXT NOT NULL, ended_at TEXT, PRIMARY KEY(exchange,market,warning_type))')
    c.execute('CREATE TABLE IF NOT EXISTS exchange_warning_changes (exchange TEXT NOT NULL, market TEXT NOT NULL, warning_type TEXT NOT NULL, change TEXT NOT NULL, step TEXT, prev_step TEXT, end_date TEXT, observed_at TEXT NOT NULL)')
    return c

def _int(v):
    try:return None if v in (None,'') else int(v)
    except (TypeError,ValueError):return None

def _get(session,url,params=None):
    try:
        r=session.get(url,params=params,timeout=15);r.raise_for_status();return r.json()
    except (requests.RequestException,ValueError) as e:raise FetchError(f'{url.split("/",3)[2]} {type(e).__name__}') from None

# ---------------------------------------------------------------- 수집

def fetch_bithumb_status(session):
    data=_get(session,BITHUMB+'/public/assetsstatus/multichain/ALL')
    if not isinstance(data,dict) or data.get('status')!='0000' or not isinstance(data.get('data'),list):raise FetchError(f"bithumb assetsstatus status={data.get('status') if isinstance(data,dict) else type(data).__name__}")
    return [dict(currency=str(r['currency']),net_type=str(r.get('net_type') or r['currency']),deposit=_int(r.get('deposit_status')),withdrawal=_int(r.get('withdrawal_status'))) for r in data['data'] if r.get('currency')]

def fetch_bithumb_warnings(session):
    data=_get(session,BITHUMB+'/v1/market/virtual_asset_warning')
    if not isinstance(data,list):raise FetchError('bithumb warnings 형식 불일치')
    return [dict(market=r['market'],warning_type=r['warning_type'],step=r.get('warning_step'),end_date=r.get('end_date')) for r in data if r.get('market') and r.get('warning_type')]

def fetch_upbit_events(session):
    data=_get(session,UPBIT+'/market/all',{'is_details':'true'})
    if not isinstance(data,list):raise FetchError('upbit market 형식 불일치')
    out=[]
    for m in data:
        market=str(m.get('market',''));event=m.get('market_event') or {}
        if not market.startswith('KRW-'):continue
        if event.get('warning') is True:out.append(dict(market=market,warning_type='INVESTMENT_WARNING',step='WARNING',end_date=None))
        for flag,on in (event.get('caution') or {}).items():
            if on is True:out.append(dict(market=market,warning_type=flag,step='CAUTION',end_date=None))
    return out

# ---------------------------------------------------------------- 저장

def record_status(exchange,rows,now):
    changes=0
    with connect() as c:
        for r in rows:
            key=(exchange,r['currency'],r['net_type']);cur=(r['deposit'],r['withdrawal'])
            prev=c.execute('SELECT deposit,withdrawal FROM exchange_status_latest WHERE exchange=? AND currency=? AND net_type=?',key).fetchone()
            if prev is not None and tuple(prev)==cur:
                c.execute('UPDATE exchange_status_latest SET last_seen_at=? WHERE exchange=? AND currency=? AND net_type=?',(now,*key));continue
            c.execute('INSERT INTO exchange_status_changes VALUES (?,?,?,?,?,?,?,?)',(*key,*cur,prev[0] if prev else None,prev[1] if prev else None,now))
            c.execute('INSERT INTO exchange_status_latest VALUES (?,?,?,?,?,?,?) ON CONFLICT(exchange,currency,net_type) DO UPDATE SET deposit=excluded.deposit,withdrawal=excluded.withdrawal,since=excluded.since,last_seen_at=excluded.last_seen_at',(*key,*cur,now,now))
            changes+=1
    return changes

def record_warnings(exchange,rows,now):
    """rows는 현재 활성 경보 전체여야 한다."""
    changes=0;seen=set()
    with connect() as c:
        for r in rows:
            key=(exchange,r['market'],r['warning_type']);seen.add(key)
            prev=c.execute('SELECT step,ended_at FROM exchange_warnings_latest WHERE exchange=? AND market=? AND warning_type=?',key).fetchone()
            if prev is None or prev[1] is not None:change,prev_step='started',None
            elif prev[0]!=r['step']:change,prev_step='step_changed',prev[0]
            else:
                c.execute('UPDATE exchange_warnings_latest SET end_date=?,last_seen_at=? WHERE exchange=? AND market=? AND warning_type=?',(r['end_date'],now,*key));continue
            c.execute('INSERT INTO exchange_warning_changes VALUES (?,?,?,?,?,?,?,?)',(*key,change,r['step'],prev_step,r['end_date'],now))
            c.execute('INSERT INTO exchange_warnings_latest VALUES (?,?,?,?,?,?,?,NULL) ON CONFLICT(exchange,market,warning_type) DO UPDATE SET step=excluded.step,end_date=excluded.end_date,since=excluded.since,last_seen_at=excluded.last_seen_at,ended_at=NULL',(*key,r['step'],r['end_date'],now,now))
            changes+=1
        for market,warning_type,step in c.execute('SELECT market,warning_type,step FROM exchange_warnings_latest WHERE exchange=? AND ended_at IS NULL',(exchange,)).fetchall():
            if (exchange,market,warning_type) in seen:continue
            c.execute('INSERT INTO exchange_warning_changes VALUES (?,?,?,?,?,?,?,?)',(exchange,market,warning_type,'ended',None,step,None,now))
            c.execute('UPDATE exchange_warnings_latest SET ended_at=? WHERE exchange=? AND market=? AND warning_type=?',(now,exchange,market,warning_type))
            changes+=1
    return changes

def _mark(source,ok,now,detail):
    state={'ok':ok,'at':now,**detail}
    health[source]=state
    try:
        with connect() as c:c.execute('INSERT INTO notice_sync_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload',('exchange_status:'+source,json.dumps(state,ensure_ascii=False)))
    except Exception:pass  # 상태 기록 실패가 수집 결과를 바꾸지 않는다

JOBS={
    'bithumb.status':(fetch_bithumb_status,lambda rows,now:record_status('bithumb',rows,now)),
    'bithumb.warnings':(fetch_bithumb_warnings,lambda rows,now:record_warnings('bithumb',rows,now)),
    'upbit.events':(fetch_upbit_events,lambda rows,now:record_warnings('upbit',rows,now)),
}

def sync_once(session=None):
    """각 소스를 독립적으로 수집한다. 한 소스의 실패가 다른 소스를 막지 않는다. {소스: 결과}를 돌려준다."""
    session=session or requests.Session();session.headers['User-Agent']='KimpScope-EducationalResearch/0.3'
    results={}
    for source,(fetch,record) in JOBS.items():
        now=now_kst()
        try:
            rows=fetch(session);changes=record(rows,now)
            results[source]={'ok':True,'items':len(rows),'changes':changes}
        except Exception as e:
            results[source]={'ok':False,'error':f'{type(e).__name__}: {e}'[:300]}
        _mark(source,results[source]['ok'],now,{k:v for k,v in results[source].items() if k!='ok'})
        time.sleep(1.1)  # 빗썸 공개 API 간격
    return results

# ---------------------------------------------------------------- RAG 근거용 조회

def coin_state(symbol):
    """한 코인의 최신 입출금 현황(빗썸)과 활성 경보(빗썸·업비트). 수집 이력이 없으면 None 필드."""
    market='KRW-'+symbol
    with connect() as c:
        status=c.execute('SELECT net_type,deposit,withdrawal,since,last_seen_at FROM exchange_status_latest WHERE exchange=? AND currency=? ORDER BY net_type',('bithumb',symbol)).fetchall()
        warnings=c.execute('SELECT exchange,warning_type,step,end_date,since,last_seen_at FROM exchange_warnings_latest WHERE market=? AND ended_at IS NULL ORDER BY exchange,warning_type',(market,)).fetchall()
        # LIKE 패턴은 인자로 넘긴다. Postgres 드라이버는 SQL 안의 % 문자를 자리표시자로 해석한다
        sync=dict(c.execute('SELECT key,payload FROM notice_sync_state WHERE key LIKE ?',('exchange_status:%',)).fetchall())
    return {
        'status':[dict(zip(('net_type','deposit','withdrawal','since','last_seen_at'),r)) for r in status],
        'warnings':[dict(zip(('exchange','warning_type','step','end_date','since','last_seen_at'),r)) for r in warnings],
        'sync':{k.split(':',1)[1]:json.loads(v) for k,v in sync.items()},
    }

def sync_summary():
    """소스별 마지막 수집 결과(크론이 기록). 상태 API용. 기록이 없으면 빈 dict."""
    try:
        with connect() as c:rows=c.execute('SELECT key,payload FROM notice_sync_state WHERE key LIKE ?',('exchange_status:%',)).fetchall()
    except Exception:
        return {'error':'상태 조회 실패'}
    return {k.split(':',1)[1]:json.loads(v) for k,v in rows}
