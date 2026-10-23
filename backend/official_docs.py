"""허용 목록의 공식 문서(고정 URL 7건)를 받아 공지 저장소(PostgreSQL/SQLite)에 보관한다.

배포마다 비워지는 디스크 대신 공지와 같은 저장소에 두어, 한 번 받은 원문이 재배포 뒤에도 남는다.
서버 시작 시 비어 있는 문서만 받는다. 서버 위치에서 막히면 실패 사유를 health에 남긴다.
재귀 수집 없음. 요청 사이 1초, 429·5xx는 최대 3회 백오프 재시도(Retry-After 존중).
"""
import io,json,re,time,threading,hashlib,logging
from urllib.parse import urlparse
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
    # 김프의 제도적 배경(해외송금 한도, 해외 이전 규제, 법인 참여 제한). 모든 코인에 공통으로 걸린다
    ('외국환거래규정 개정 행정예고: 무증빙 해외송금 한도 연 10만 달러 (기획재정부, 2023-06-08)','https://www.korea.kr/briefing/pressReleaseView.do?newsId=156574043','정부 보도자료',[]),
    ('특정금융정보법 시행령 개정: 트래블룰 전체 거래 확대·해외 이전 제한 (금융위원회, 2026-08-11)','https://www.korea.kr/news/policyNewsView.do?newsId=148969860','정부 보도자료',[]),
    ('제3차 가상자산위원회 브리핑: 법인의 가상자산시장 참여 단계적 허용 (금융위원회, 2025-02-14)','https://www.korea.kr/briefing/policyBriefingView.do?newsId=156674299','정부 보도자료',[]),
]
BY_URL={s[1]:s for s in SOURCES}
# 본문이 페이지가 아니라 첨부 PDF에만 있는 문서. 인용 주소는 페이지, 본문은 첨부에서 받는다
# (156574043 페이지 본문은 "보도자료를 전재" 한 줄 38자뿐이다. 2026-10-23 실측)
ATTACHMENTS={'https://www.korea.kr/briefing/pressReleaseView.do?newsId=156574043':'https://www.korea.kr/common/download.do?fileId=197357191&tblKey=GMN'}
# 사이트별 본문 위치. 공통 규칙으로 찾으면 메뉴·관련기사가 섞인다(korea.kr <main> 5,128자 중 본문 2,261자)
BODY_SELECTORS={'www.korea.kr':'.view_cont'}
# 사이트별 이용 조건. 각 페이지에 표시된 문구를 확인해 적었다(2026-10-23)
LICENSES={'www.korea.kr':'공공누리 제1유형(출처표시) — 텍스트에 한함. 출처: 대한민국 정책브리핑(www.korea.kr)'}
MIN_CHARS=200
CONTACT=re.compile(r'[\w.+-]+@[\w-]+(\.[\w-]+)+|\(?0\d{1,2}\)?[-\s.]?\d{3,4}[-\s.]\d{4}')
health={'state':'idle','stored':None,'failures':{}}

def connect():
    c=notices.connect()
    c.execute('CREATE TABLE IF NOT EXISTS official_documents (url TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    return c

def scrub(text):
    # 보도자료 끝의 담당자 이메일·전화번호는 근거로 쓸 일이 없고 개인 연락처라 저장하지 않는다
    return re.sub(r'\s+',' ',CONTACT.sub('',text)).strip()

def extract(html,url=None):
    soup=BeautifulSoup(html,'html.parser')
    for n in soup(['script','style','nav','footer','header']):n.decompose()
    selector=BODY_SELECTORS.get(urlparse(url or '').netloc)
    # 본문 위치를 아는 사이트는 그 위치만 쓴다. 못 찾으면 페이지 전체로 대신하지 않는다(메뉴를 본문으로 저장하지 않게)
    main=soup.select_one(selector) if selector else soup.find('article') or soup.find('main') or soup.find(id='content') or soup
    if main is None:return None
    text=scrub(main.get_text(' ',strip=True))
    return text if len(text)>=MIN_CHARS else None

def extract_pdf(content):
    from pypdf import PdfReader
    try:text=' '.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(content)).pages)
    except Exception:return None
    text=scrub(text)
    return text if len(text)>=MIN_CHARS else None

def save(url,html,via='server',pdf=None):
    """원문 HTML(또는 ATTACHMENTS 문서는 첨부 PDF)에서 본문을 뽑아 저장. 허용 목록 밖 URL이나 본문이 짧으면 ValueError."""
    if url not in BY_URL:raise ValueError('허용 목록에 없는 문서')
    title,_,kind,symbols=BY_URL[url]
    if url in ATTACHMENTS:
        if pdf is None:raise ValueError('본문은 첨부 PDF에 있음')
        text=extract_pdf(pdf)
    else:text=extract(html,url)
    if text is None:raise ValueError(f'본문 {MIN_CHARS}자 미만')
    doc=dict(id=hashlib.sha256(url.encode()).hexdigest()[:16],title=title,body=text,source=url,source_type=kind,symbols=symbols,
             verified=True,collected_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),collected_via=via,own=False,
             **({'license':LICENSES[urlparse(url).netloc]} if urlparse(url).netloc in LICENSES else {}))
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
            if url in ATTACHMENTS:
                r=session.get(ATTACHMENTS[url],timeout=30,allow_redirects=False);r.raise_for_status()
                if not r.content.startswith(b'%PDF'):raise ValueError('첨부가 PDF가 아님')
                save(url,None,pdf=r.content)
            else:
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
