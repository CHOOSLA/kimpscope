"""실시간 근거. 시세·김프 스냅샷과 거래소 입출금·경보 상태를 '기준 시각이 붙은 검색 근거'로 만든다.

문서 속 숫자(API 예시 가격, 과거 공지의 수치)를 현재 값으로 답하던 오류를 막기 위해,
현재 수치를 묻는 질문은 이 근거가 있을 때만 답하고 그 근거를 인용해야 한다(pipeline.generate_node가 검사).
"""
import re,time
from datetime import datetime,timedelta,timezone

KST=timezone(timedelta(hours=9))
MARKET_MAX_AGE_S=60        # 시세는 5초 캐시. 1분 넘게 갱신되지 않으면 현재 값으로 쓰지 않는다
STATE_MAX_AGE_S=45*60      # 상태 수집은 15분 크론. 세 번 연속 놓치면 오래된 값으로 본다
WARNING_LABELS={
    'INVESTMENT_WARNING':'투자유의 종목 지정','PRICE_FLUCTUATIONS':'가격 급등락','TRADING_VOLUME_SOARING':'거래량 급증',
    'DEPOSIT_AMOUNT_SOARING':'입금량 급증','GLOBAL_PRICE_DIFFERENCES':'글로벌 시세 차이','CONCENTRATION_OF_SMALL_ACCOUNTS':'소수 계정 거래 집중',
    'PRICE_SUDDEN_FLUCTUATION':'가격 급등락','PRICE_DIFFERENCE_HIGH':'글로벌 시세 차이','SPECIFIC_ACCOUNT_HIGH_TRANSACTION':'소수 계정 거래 집중',
    'TRADING_VOLUME_SUDDEN_FLUCTUATION':'거래량 급증','DEPOSIT_AMOUNT_SUDDEN_FLUCTUATION':'입금량 급증',
}
STEP_LABELS={'CAUTION':'주의','WARNING':'경고','DANGER':'위험'}

def _kst(ms):return datetime.fromtimestamp(ms/1000,KST).strftime('%Y-%m-%d %H:%M:%S KST') if ms else '미상'
def _age_s(iso):
    try:return (datetime.now(KST)-datetime.fromisoformat(iso)).total_seconds()
    except (TypeError,ValueError):return None
def _won(n):return f'{n:,.0f}원' if n>=100 else f'{n:,.4f}'.rstrip('0').rstrip('.')+'원'  # 소액 코인은 소수점까지

def market_evidence(item,quote=None,now_ms=None):
    from .market import quote as load
    q=quote if quote is not None else load(item['symbol'])
    if not q:return None
    now_ms=now_ms or int(time.time()*1000)
    stale=bool(q.get('stale')) or not q.get('received_at') or now_ms-q['received_at']>MARKET_MAX_AGE_S*1000
    parts=[f"{item['name']}({item['symbol']}) 시세 스냅샷, 기준 시각 {_kst(q.get('received_at'))}.",
           f"업비트 원화가 {_won(q['domestic'])}, {q.get('foreign_source') or '해외'} {q['foreign']:g} USDT."]
    if q.get('premium') is not None:
        parts.append(f"원/달러 {q['fx']:,.2f}원({q['fx_source']}, 고시일 {q['fx_date']}) 기준 김치 프리미엄 {q['premium']:+.2f}%.")
    else:
        parts.append('원/달러 기준 환율을 확보하지 못해 김치 프리미엄은 산출하지 않았다.')
    if q.get('tether_premium') is not None:
        parts.append(f"업비트 USDT/KRW {q['usdt_krw']:,.0f}원, 테더 프리미엄 {q['tether_premium']:+.2f}%.")
    parts.append('거래소 체결가이며 거래소마다 수신 시각이 다를 수 있다. 수수료·전송 시간은 반영하지 않았다.')
    if stale:parts.append('주의: 이 스냅샷은 최신이 아니다(갱신 실패 또는 지연). 현재 값으로 쓰지 않는다.')
    return dict(id='live-market-'+item['symbol'],title=item['name']+' 실시간 시세·김프',text=' '.join(parts),
                source='업비트 /v1/ticker/all · '+(q.get('foreign_source') or '해외')+' USDT 현물 · '+(q.get('fx_source') or '환율 미확보'),
                source_type='실시간 시세 스냅샷',exchange='Upbit/'+(q.get('foreign_source') or '해외'),revision=_kst(q.get('received_at')),
                published_at=_kst(q.get('received_at')),live='market',stale=stale,score=1.0)

def state_evidence(item,state=None):
    from .exchange_status import coin_state
    s=state if state is not None else coin_state(item['symbol'])
    status_sync=(s.get('sync') or {}).get('bithumb.status') or {}
    if not s.get('status') and not s.get('warnings'):
        return None
    last=status_sync.get('at') if status_sync.get('ok') else None
    age=_age_s(last)
    stale=age is None or age>STATE_MAX_AGE_S
    parts=[f"{item['name']}({item['symbol']}) 거래소 상태, 마지막 수집 {last or '미상'}."]
    if s.get('status'):
        nets=[]
        for r in s['status']:
            dep={1:'입금 가능',0:'입금 중지'}.get(r['deposit'],'입금 상태 미상');wd={1:'출금 가능',0:'출금 중지'}.get(r['withdrawal'],'출금 상태 미상')
            nets.append(f"{r['net_type']} 네트워크 {dep}·{wd}(이 상태 관측 시작 {r['since']})")
        parts.append('빗썸 입출금 현황(빗썸 기준이며 업비트 상태가 아니다): '+'; '.join(nets)+'.')
    if s.get('warnings'):
        ws=[]
        for w in s['warnings']:
            ex='업비트' if w['exchange']=='upbit' else '빗썸'
            label=WARNING_LABELS.get(w['warning_type'],w['warning_type'])
            step=STEP_LABELS.get(w['step'],w['step'] or '')
            until=f", 종료 예정 {w['end_date']}" if w.get('end_date') else ''
            ws.append(f"{ex} {label}({step}, 관측 시작 {w['since']}{until})")
        parts.append('활성 경보: '+'; '.join(ws)+'.')
    else:
        parts.append('활성 경보 없음.')
    parts.append('수집기가 관찰한 시각 기준이며 거래소가 바꾼 시각과 다를 수 있다. 업비트 입출금 현황은 수집하지 않는다.')
    if stale:parts.append('주의: 상태 수집이 최근에 성공하지 않았다. 현재 상태로 단정하지 않는다.')
    return dict(id='live-state-'+item['symbol'],title=item['name']+' 입출금·경보 상태',text=' '.join(parts),
                source='빗썸 /public/assetsstatus · 빗썸 /v1/market/virtual_asset_warning · 업비트 /v1/market/all',
                source_type='거래소 상태 스냅샷',exchange='Bithumb/Upbit',revision=last or '미상',published_at=last or '미상',
                live='state',stale=stale,score=1.0)

def evidence(item):
    """실패해도 RAG를 멈추지 않는다. 만들 수 있는 근거만 돌려준다."""
    out=[]
    for build in (market_evidence,state_evidence):
        try:
            e=build(item)
            if e:out.append(e)
        except Exception:
            pass
    return out

# ---------------------------------------------------------------- 질문 분류

NOW=r'(지금|현재|오늘|실시간|요즘)'
PAST=r'(적 ?있|했었|됐었|되었었|였던|지난|과거|이력|기록|최근에.*(있었|됐|되었|했))'  # 지난 일은 공지 문서로 답한다
PRICE=r'(가격|시세|김프|김치.?프리미엄|프리미엄|환율|얼마)'
STATE=r'(출금|입금|입출금|거래.?가능|유의|경보|주의.?종목|막혔|막힌|중지|중단)'
FORECAST=r'(내일|미래|앞으로|다음.?(주|달)|전망|예측).*(가격|시세|오르|올라|내리|하락|상승|수익|김프)|(오를까|내릴까|살까|팔까|사도 될까|팔아야)'

def needs(question):
    """질문이 현재 값을 요구하면 필요한 실시간 근거 종류 집합. 예측 질문이면 'forecast'."""
    q=question.strip()
    if re.search(FORECAST,q):return {'forecast'}
    kinds=set()
    if re.search(PAST,q) and not re.search(NOW,q):return kinds
    if re.search(NOW+r'.*'+PRICE,q) or re.search(PRICE+r'.*'+NOW,q):kinds.add('market')
    if re.search(NOW+r'.*'+STATE,q) or re.search(STATE+r'.*'+NOW,q) or re.search(r'(출금|입금|입출금).*(돼|되나|가능|할 수)',q):kinds.add('state')
    return kinds
