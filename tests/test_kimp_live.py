"""김프 계산·실시간 근거·거래소 상태 수집 회귀 시험. 2026-10-23 실측 응답과 같은 모양의 모의 데이터를 쓴다."""
import json
from datetime import datetime,timedelta
import pytest
from backend import fx,market,live,exchange_status,pipeline

class Resp:
    def __init__(self,data,status=200):self._d,self.status_code=data,status
    def json(self):return self._d
    def raise_for_status(self):
        if self.status_code>=400:
            import requests
            raise requests.HTTPError(str(self.status_code))

class Session:
    def __init__(self,routes):self.routes,self.calls,self.headers=routes,[],{}
    def get(self,url,params=None,timeout=None,**kw):
        self.calls.append((url,params))
        for key,value in self.routes.items():
            if key in url:
                value=value(params) if callable(value) else value
                return value if isinstance(value,Resp) else Resp(value)
        import requests
        raise requests.ConnectionError('blocked '+url)

# ---------------------------------------------------------------- 환율

@pytest.fixture(autouse=True)
def reset_caches(monkeypatch):
    fx.cache.update(at=0,value=None,error=None)
    market.cache.update(at=0,data=None);market.trading_cache.update(at=0,symbols=None)
    monkeypatch.delenv('KOREAEXIM_API_KEY',raising=False)
    monkeypatch.setattr(exchange_status.time,'sleep',lambda s:None)

def test_exim_skips_holiday_and_parses_comma(monkeypatch):
    monkeypatch.setenv('KOREAEXIM_API_KEY','k')
    days={'20271115':[], '20271114':[{'cur_unit':'JPY(100)','deal_bas_r':'950.1'},{'cur_unit':'USD','deal_bas_r':'1,400.50'}]}
    s=Session({'koreaexim':lambda p:days.get(p['searchdate'],[])})
    v=fx.from_exim('k',s,today=datetime(2027,11,15,10,0,tzinfo=fx.KST))
    assert v=={'rate':1400.5,'date':'2027-11-14','source':'한국수출입은행 매매기준율'}

def test_frankfurter_used_without_key_and_cached():
    s=Session({'frankfurter':{'date':'2026-10-22','base':'USD','quote':'KRW','rate':1325.13}})
    assert fx.usd_krw(session=s)['rate']==1325.13
    fx.usd_krw(session=s)
    assert len(s.calls)==1

def test_no_fixed_rate_when_all_sources_fail():
    assert fx.usd_krw(session=Session({}))is None
    assert 'Frankfurter' in fx.cache['error']

# ---------------------------------------------------------------- 시세·김프

UPBIT=[{'market':'KRW-BTC','trade_price':150_000_000,'signed_change_rate':0.01,'timestamp':1},
       {'market':'KRW-DATA','trade_price':200,'signed_change_rate':0,'timestamp':1},
       {'market':'KRW-USDT','trade_price':1420,'signed_change_rate':0,'timestamp':1}]
BINANCE=[{'symbol':'BTCUSDT','price':'100000'},{'symbol':'DATAUSDT','price':'0.0000085'}]  # DATA: 거래 중단 심볼의 남은 가격
INFO={'symbols':[{'symbol':'BTCUSDT','baseAsset':'BTC','quoteAsset':'USDT','status':'TRADING'},
                 {'symbol':'DATAUSDT','baseAsset':'DATA','quoteAsset':'USDT','status':'BREAK'}]}

def market_session():
    return Session({'exchangeInfo':INFO,'ticker/price':BINANCE,'api.upbit.com/v1/ticker/all':UPBIT})

def test_kimp_uses_official_rate_and_filters_break(monkeypatch):
    monkeypatch.setattr(market,'session',market_session())
    monkeypatch.setattr(market.fx_rates,'usd_krw',lambda:{'rate':1400.0,'date':'2026-10-22','source':'테스트 환율'})
    data=market.full_snapshot()
    assert set(data['all_rows'])=={'BTC'}  # BREAK인 DATA는 빠진다
    btc=data['all_rows']['BTC']
    assert btc['premium']==pytest.approx((150_000_000/(100000*1400)-1)*100)   # +7.14%
    assert btc['premium_usdt']==pytest.approx((150_000_000/(100000*1420)-1)*100)  # 테더 기준은 더 작다
    assert data['tether_premium']==pytest.approx((1420/1400-1)*100)
    assert market.snapshot()['rows'][0]['symbol']=='BTC' and 'all_rows' not in market.snapshot()

def test_premium_withheld_without_fx(monkeypatch):
    monkeypatch.setattr(market,'session',market_session())
    monkeypatch.setattr(market.fx_rates,'usd_krw',lambda:None)
    row=market.snapshot()['rows'][0]
    assert row['premium'] is None and row['converted'] is None
    assert '미확보' in market.snapshot()['fx_label']

def test_stale_response_carries_failure_reason(monkeypatch):
    monkeypatch.setattr(market,'session',market_session())
    monkeypatch.setattr(market.fx_rates,'usd_krw',lambda:{'rate':1400.0,'date':'d','source':'s'})
    market.full_snapshot()
    monkeypatch.setattr(market,'session',Session({}))
    market.cache['at']=0
    out=market.snapshot()
    assert out['stale'] is True and 'Binance' in out['error']

def test_trading_filter_unavailable_falls_back_to_featured(monkeypatch):
    s=Session({'ticker/price':BINANCE,'api.upbit.com/v1/ticker/all':UPBIT})  # exchangeInfo 실패
    monkeypatch.setattr(market,'session',s)
    monkeypatch.setattr(market.fx_rates,'usd_krw',lambda:{'rate':1400.0,'date':'d','source':'s'})
    data=market.full_snapshot()
    assert set(data['all_rows'])=={'BTC'} and data['trading_filter']=='featured_only'

# ---------------------------------------------------------------- 거래소 상태 수집

STATUS={'status':'0000','data':[{'currency':'BTC','net_type':'BTC','deposit_status':1,'withdrawal_status':1},
                                {'currency':'EGLD','net_type':'EGLD','deposit_status':0,'withdrawal_status':1}]}
WARN=[{'market':'KRW-EGLD','warning_type':'PRICE_DIFFERENCE_HIGH','warning_step':'CAUTION','end_date':'2026-10-24 01:59:59'}]
UPBIT_MARKETS=[{'market':'KRW-EGLD','market_event':{'warning':True,'caution':{'TRADING_VOLUME_SOARING':True}}},
               {'market':'BTC-ETH','market_event':{'warning':True}}]

def state_session(**override):
    routes={'assetsstatus':STATUS,'virtual_asset_warning':WARN,'market/all':UPBIT_MARKETS};routes.update(override)
    return Session({k:v for k,v in routes.items() if v is not None})

def count(sql,params=()):
    with exchange_status.connect() as c:return c.execute(sql,params).fetchone()[0]

def test_status_sync_idempotent_and_records_transitions():
    r=exchange_status.sync_once(state_session())
    assert all(x['ok'] for x in r.values()) and r['bithumb.status']['changes']==2
    assert exchange_status.sync_once(state_session())['bithumb.status']['changes']==0
    reopened={'status':'0000','data':[dict(STATUS['data'][0]),dict(STATUS['data'][1],deposit_status='1')]}  # 문자열 '1'도 같은 값으로 본다
    assert exchange_status.sync_once(state_session(assetsstatus=reopened))['bithumb.status']['changes']==1
    assert count('SELECT COUNT(*) FROM exchange_status_changes WHERE currency=?',('EGLD',))==2

@pytest.mark.parametrize('broken',[None,{'error':{'name':'server_error','message':'점검'}}],ids=['connection_failure','malformed_200'])
def test_failed_warning_fetch_does_not_end_active_warnings(broken):
    exchange_status.sync_once(state_session())
    # None: 연결 실패. dict: 200 응답이지만 목록이 아님. 둘 다 '경보 0건'으로 처리되면 안 된다
    r=exchange_status.sync_once(state_session(virtual_asset_warning=broken))
    assert r['bithumb.warnings']['ok'] is False
    assert count("SELECT COUNT(*) FROM exchange_warnings_latest WHERE exchange='bithumb' AND ended_at IS NULL")==1

def test_warning_ends_when_absent_and_exchanges_are_independent():
    exchange_status.sync_once(state_session())
    exchange_status.sync_once(state_session(virtual_asset_warning=[]))
    assert count("SELECT COUNT(*) FROM exchange_warning_changes WHERE exchange='bithumb' AND change='ended'")==1
    assert count("SELECT COUNT(*) FROM exchange_warnings_latest WHERE exchange='upbit' AND ended_at IS NULL")==2

def test_coin_state_and_state_evidence():
    exchange_status.sync_once(state_session())
    s=exchange_status.coin_state('EGLD')
    assert s['status'][0]['deposit']==0 and s['sync']['bithumb.status']['ok'] is True
    e=live.state_evidence({'name':'멀티버스엑스','symbol':'EGLD'},s)
    assert e['stale'] is False and '입금 중지' in e['text'] and '빗썸 기준' in e['text']
    assert '투자유의 종목 지정' in e['text'] and '글로벌 시세 차이' in e['text']

def test_state_evidence_is_stale_when_sync_old():
    old=(datetime.now(live.KST)-timedelta(hours=2)).isoformat(timespec='seconds')
    s={'status':[{'net_type':'EGLD','deposit':0,'withdrawal':1,'since':old,'last_seen_at':old}],'warnings':[],'sync':{'bithumb.status':{'ok':True,'at':old}}}
    e=live.state_evidence({'name':'멀티버스엑스','symbol':'EGLD'},s)
    assert e['stale'] is True and '단정하지 않는다' in e['text']

# ---------------------------------------------------------------- 질문 분류·생성 판정

@pytest.mark.parametrize('q,expected',[
    ('지금 비트코인 김프 몇 %야?',{'market'}),
    ('현재 가격 얼마예요?',{'market'}),
    ('EGLD 지금 입금 돼?',{'state'}),
    ('출금 가능해?',{'state'}),
    ('내일 오를까?',{'forecast'}),
    ('김프가 왜 생기나요?',set()),
    ('업비트 ticker에서 현재가와 거래 시각 필드는 무엇인가요?',set()),
])
def test_question_kinds(q,expected):
    assert live.needs(q)==expected

def live_market(stale=False):
    return dict(id='live-market-BTC',title='비트코인 실시간 시세·김프',text='김치 프리미엄 +7.14%',source='s',source_type='실시간 시세 스냅샷',live='market',stale=stale)

def run_generate(monkeypatch,question,evidence,answer):
    class Model:
        def invoke(self,messages):return type('R',(),{'content':answer})()
    monkeypatch.setattr(pipeline,'available',lambda:True)
    monkeypatch.setattr(pipeline,'model',lambda:Model())
    return pipeline.generate_node({'question':question,'item':{'name':'비트코인'},'evidence':evidence})

def test_live_question_answered_from_fresh_snapshot(monkeypatch):
    meta={'title':'메타','source_type':'항목 메타데이터','text':'BTC'}
    r=run_generate(monkeypatch,'지금 비트코인 김프 몇 %야?',[meta,live_market()],'김치 프리미엄은 +7.14%입니다[2].')
    assert r['status']=='ok' and r['citations'][0]['live']=='market'

def test_live_answer_must_cite_snapshot(monkeypatch):
    doc={'title':'API 예시','source_type':'API 문서','text':'trade_price: 3428000'}
    r=run_generate(monkeypatch,'지금 비트코인 가격 얼마야?',[doc,live_market()],'3428000원입니다[1].')
    assert r['status']=='live_citation_missing' and '3428000' not in r['answer']

def test_stale_snapshot_does_not_unlock_live_answers(monkeypatch):
    def forbidden():raise AssertionError('최신 근거 없이 모델을 호출하면 안 됩니다')
    monkeypatch.setattr(pipeline,'model',forbidden)
    r=pipeline.generate_node({'question':'지금 김프 몇 %야?','item':{'name':'비트코인'},'evidence':[live_market(stale=True)]})
    assert r['status']=='unsupported_live_query'

def test_forecast_refused_even_with_snapshot(monkeypatch):
    monkeypatch.setattr(pipeline,'model',lambda:(_ for _ in ()).throw(AssertionError('예측 질문에 모델 호출 금지')))
    r=pipeline.generate_node({'question':'내일 김프 오를까?','item':{'name':'비트코인'},'evidence':[live_market()]})
    assert r['status']=='unsupported_live_query'

def test_market_evidence_text_and_staleness():
    q={'domestic':150_000_000,'foreign':100000,'premium':7.142857,'fx':1400.0,'fx_source':'테스트 환율','fx_date':'2026-10-22',
       'usdt_krw':1420,'tether_premium':1.428571,'received_at':1_000_000,'stale':False}
    e=live.market_evidence({'name':'비트코인','symbol':'BTC'},q,now_ms=1_000_000+5_000)
    assert e['stale'] is False and '+7.14%' in e['text'] and '고시일 2026-10-22' in e['text'] and '테더 프리미엄 +1.43%' in e['text']
    assert live.market_evidence({'name':'비트코인','symbol':'BTC'},q,now_ms=1_000_000+120_000)['stale'] is True
    no_fx=live.market_evidence({'name':'비트코인','symbol':'BTC'},q|{'premium':None},now_ms=1_000_000)
    assert '산출하지 않았다' in no_fx['text']

# ---------------------------------------------------------------- 크론 진입점

def test_cron_exit_code(monkeypatch,capsys):
    from scripts import cron_collect
    monkeypatch.setattr(cron_collect.bithumb_notices,'sync_once',lambda wait:(_ for _ in ()).throw(RuntimeError('down')))
    monkeypatch.setattr(cron_collect.exchange_status,'sync_once',lambda:{'bithumb.status':{'ok':False,'error':'x'}})
    assert cron_collect.main()==1
    monkeypatch.setattr(cron_collect.exchange_status,'sync_once',lambda:{'bithumb.status':{'ok':True,'items':1,'changes':0}})
    assert cron_collect.main()==0
    line=json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line['results']['bithumb.notices']['ok'] is False

def test_status_api_reports_exchange_sync():
    from fastapi.testclient import TestClient
    from backend.main import app
    exchange_status.sync_once(state_session())
    body=TestClient(app).get('/api/notices/status').json()
    assert body['exchange_status']['bithumb.status']['ok'] is True
