"""원/달러 기준 환율. 김치 프리미엄은 이 값을 기준으로 계산한다.

업비트 USDT/KRW 체결가를 환율로 쓰면 테더에 이미 붙은 국내 프리미엄이 상쇄되어 김프가 0에 가깝게 나온다.
(2026-10-23 운영 응답: USDT 기준 BTC −0.01%, 10개 코인 모두 ±0.8% 이내)

출처 우선순위
  1. KOREAEXIM_API_KEY가 있으면 한국수출입은행 매매기준율(고시 시점 값). 휴일·고시 전에는 최근 영업일까지 거슬러 간다.
  2. 없거나 실패하면 Frankfurter 공개 기준환율(중앙은행 고시 혼합, 일 단위, 키 불필요).
  3. 둘 다 실패하면 None. 고정 환율로 대체하지 않는다.
"""
import os,time,threading
from datetime import datetime,timedelta,timezone
import requests

KST=timezone(timedelta(hours=9))
EXIM_URL='https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON'
FRANKFURTER_URL='https://api.frankfurter.dev/v2/rate/usd/krw'
TTL=3600  # 일 단위 고시값이므로 1시간 캐시로 충분하다
FAIL_TTL=300  # 실패 후 재시도 간격
lock=threading.Lock()
cache={'at':0,'value':None,'error':None}

def _number(value):
    try:return float(str(value).replace(',',''))
    except (TypeError,ValueError):return None

def from_exim(key,session,today=None,back_days=7):
    today=today or datetime.now(KST)
    for back in range(back_days+1):
        day=(today-timedelta(days=back)).strftime('%Y%m%d')
        r=session.get(EXIM_URL,params={'authkey':key,'searchdate':day,'data':'AP01'},timeout=10);r.raise_for_status()
        rows=r.json()
        if not isinstance(rows,list):continue
        for row in rows:
            if str(row.get('cur_unit','')).upper().startswith('USD'):
                rate=_number(row.get('deal_bas_r'))
                if rate:return {'rate':rate,'date':f'{day[:4]}-{day[4:6]}-{day[6:]}','source':'한국수출입은행 매매기준율'}
    return None

def from_frankfurter(session):
    r=session.get(FRANKFURTER_URL,timeout=10);r.raise_for_status();data=r.json()
    rate=_number(data.get('rate'))
    if not rate or data.get('base')!='USD' or data.get('quote')!='KRW':raise ValueError('Unexpected FX response')
    return {'rate':rate,'date':data.get('date'),'source':'Frankfurter 공개 기준환율'}

def usd_krw(session=None,now=time.time):
    """{'rate','date','source'} 또는 None. 실패 원인은 cache['error']에 남는다(키 값은 남기지 않는다)."""
    with lock:
        age=now()-cache['at']
        if cache['value'] and age<TTL:return cache['value']
        if not cache['value'] and cache['error'] and age<FAIL_TTL:return None
        session=session or requests.Session();errors=[]
        key=os.getenv('KOREAEXIM_API_KEY','').strip()
        value=None
        if key:
            try:value=from_exim(key,session)
            except Exception as e:errors.append(f'수출입은행 {type(e).__name__}')
        if not value:
            try:value=from_frankfurter(session)
            except Exception as e:errors.append(f'Frankfurter {type(e).__name__}')
        if value:
            cache.update(at=now(),value=value,error=None)
        else:
            # 예전 값이 있으면 유지하되, 오래됐다는 사실은 date로 드러난다
            cache.update(at=now(),error=' / '.join(errors) or '환율 없음')
        return cache['value']
