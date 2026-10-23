"""허용 목록의 공식 문서(고정 URL 4건)를 받아 공지 저장소(PostgreSQL/SQLite)에 보관한다.

배포마다 비워지는 디스크 대신 공지와 같은 저장소에 두어, 한 번 받은 원문이 재배포 뒤에도 남는다.
서버 시작 시 비어 있는 문서만 받는다. 서버 위치에서 막히면 실패 사유를 health에 남긴다.
재귀 수집 없음. 요청 사이 1초, 429·5xx는 최대 3회 백오프 재시도(Retry-After 존중).
"""
import json,time,threading,hashlib,logging
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from . import notices

log=logging.getLogger(__name__)
UA='KimpScope-EducationalResearch/0.3 (no recursive crawler)'
SOURCES=[  # (제목, URL, 출처 종류, 관련 심볼 — 비어 있으면 모든 코인)
    ('업비트 거래 페어 안내','https://docs.upbit.com/kr/reference/list-trading-pairs','거래소 API 문서',[]),
    ('업비트 현재가 데이터 필드','https://docs.upbit.com/kr/reference/websocket-ticker','거래소 API 문서',[]),
    ('비트코인 기초','https://bitcoin.org/en/how-it-works','프로젝트 공식 가이드',['BTC']),
    ('이더리움 가스와 수수료','https://ethereum.org/en/developers/docs/gas/','프로젝트 공식 가이드',['ETH']),
]
BY_URL={s[1]:s for s in SOURCES}
MIN_CHARS=200
health={'state':'idle','stored':None,'failures':{}}

def connect():
    c=notices.connect()
    c.execute('CREATE TABLE IF NOT EXISTS official_documents (url TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    return c

def extract(html):
    soup=BeautifulSoup(html,'html.parser')
    for n in soup(['script','style','nav','footer','header']):n.decompose()
    main=soup.find('article') or soup.find('main') or soup.find(id='content') or soup
    text=main.get_text(' ',strip=True)
    return text if len(text)>=MIN_CHARS else None

def save(url,html,via='server'):
    """원문 HTML에서 본문을 뽑아 저장. 허용 목록 밖 URL이나 본문이 짧으면 ValueError."""
    if url not in BY_URL:raise ValueError('허용 목록에 없는 문서')
    title,_,kind,symbols=BY_URL[url]
    text=extract(html)
    if text is None:raise ValueError(f'본문 {MIN_CHARS}자 미만')
    doc=dict(id=hashlib.sha256(url.encode()).hexdigest()[:16],title=title,body=text,source=url,source_type=kind,symbols=symbols,
             verified=True,collected_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),collected_via=via,own=False)
    with connect() as c:
        c.execute('INSERT INTO official_documents VALUES (?,?) ON CONFLICT(url) DO UPDATE SET payload=excluded.payload',(url,json.dumps(doc,ensure_ascii=False)))
    return len(text)

def stored():
    with connect() as c:return [json.loads(r[0]) for r in c.execute('SELECT payload FROM official_documents ORDER BY url').fetchall()]

def documents(symbol):
    try:docs=stored()
    except Exception as e:
        log.warning('공식 문서 조회 실패: %s',type(e).__name__);return []
    return [d for d in docs if not d['symbols'] or symbol in d['symbols']]

def fetch_missing(session=None,wait=time.sleep):
    session=session or requests.Session();session.headers['User-Agent']=UA
    session.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504],respect_retry_after_header=True)))
    have={d['source'] for d in stored()};failures={}
    for title,url,_,_ in SOURCES:
        if url in have:continue
        try:
            r=session.get(url,timeout=30);r.raise_for_status();save(url,r.content)
        except Exception as e:
            failures[url]=f"HTTP {getattr(getattr(e,'response',None),'status_code',None)}" if isinstance(e,requests.HTTPError) else (str(e) if isinstance(e,ValueError) else type(e).__name__)
        wait(1)
    health.update(state='ready',stored=len(stored()),failures=failures)
    return failures

def start():
    def run():
        health['state']='fetching'
        try:fetch_missing()
        except Exception as e:health.update(state='error',failures={'storage':type(e).__name__})
    threading.Thread(target=run,daemon=True).start()
