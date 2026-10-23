"""Public Bithumb notice polling; official metadata and fetched HTML kept distinct."""
import json,time,threading,os,re,hashlib
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from . import notices
health={'state':'idle','last_poll_at':None,'error':None,'changed':0}
guard=threading.Lock()

def connect():
    c=notices.connect()
    c.execute('CREATE TABLE IF NOT EXISTS notice_sync_state (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS bithumb_notices (url TEXT PRIMARY KEY, revision TEXT NOT NULL, payload TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS bithumb_notice_versions (url TEXT NOT NULL, revision TEXT NOT NULL, fingerprint TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(url,revision,fingerprint))')
    return c

def valid_url(url):
    p=urlparse(url)
    return p.scheme=='https' and p.hostname=='feed.bithumb.com' and bool(re.fullmatch(r'/notice/\d+',p.path)) and not p.query and not p.fragment

def fingerprint(payload):
    content={k:v for k,v in payload.items() if k!='received_at'}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def archive(c,payload):
    revision=payload.get('modified_at') or payload['published_at']
    c.execute('INSERT INTO bithumb_notice_versions VALUES (?,?,?,?) ON CONFLICT DO NOTHING',
              (payload['pc_url'],revision,fingerprint(payload),json.dumps(payload,ensure_ascii=False)))


def save(meta,body):
    url=meta.get('pc_url','');revision=meta.get('modified_at') or meta.get('published_at')
    if not valid_url(url) or not revision or not meta.get('title'):raise ValueError('Invalid official metadata')
    payload={**meta,'body':body,'received_at':int(time.time()*1000)}
    with connect() as c:
        # Lock before reading to keep history and latest pointer atomic across workers.
        if c.postgres:c.execute('SELECT pg_advisory_xact_lock(hashtextextended(?,0))',(url,))
        else:c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT revision,payload FROM bithumb_notices WHERE url=?',(url,)).fetchone()
        if old:
            previous=json.loads(old[1])
            archive(c,previous) # Seed history for pre-existing records without rewriting them.
            if old[0]>revision:return False
            if old[0]==revision and (fingerprint(previous)==fingerprint(payload) or (previous.get('body') and body is None)):return False
        result=c.execute('INSERT INTO bithumb_notices VALUES (?,?,?) ON CONFLICT(url) DO UPDATE SET revision=excluded.revision,payload=excluded.payload WHERE excluded.revision >= bithumb_notices.revision',(url,revision,json.dumps(payload,ensure_ascii=False)))
        if result.rowcount:archive(c,payload)
    return result.rowcount==1


def versions(notice_id):
    if not str(notice_id).isdigit():raise ValueError('Invalid notice id')
    url='https://feed.bithumb.com/notice/'+str(notice_id)
    with connect() as c:
        rows=c.execute('SELECT payload,fingerprint FROM bithumb_notice_versions WHERE url=? ORDER BY revision DESC,fingerprint',(url,)).fetchall()
    return [{**json.loads(payload),'fingerprint':digest} for payload,digest in rows]


def relay(url,html):
    """서버 위치에서 본문 페이지가 막힐 때(Render → feed.bithumb.com 403), 사용자 브라우저가 받은 원본 HTML로 본문을 채운다.
    이미 공식 목록 API로 받은 공지만 대상으로 하고, 본문 추출은 서버 수집과 같은 extract_body를 쓴다."""
    entry=next((e for e in records() if e.get('pc_url')==url),None)
    if not entry:raise ValueError('목록에 없는 공지')
    body=extract_body(html.encode() if isinstance(html,str) else html)
    if body is None:raise ValueError('본문 구조 없음')
    meta={k:v for k,v in entry.items() if k not in ('body','received_at')}|{'body_via':'browser_relay'}
    return save(meta,body)

def records():
    with connect() as c:rows=c.execute('SELECT payload FROM bithumb_notices ORDER BY revision DESC').fetchall()
    return [json.loads(r[0]) for r in rows]

def sync_status():
    with connect() as c:
        row=c.execute("SELECT payload FROM notice_sync_state WHERE key='bithumb'").fetchone()
        count=c.execute('SELECT COUNT(*) FROM bithumb_notices').fetchone()[0]
    return {**(json.loads(row[0]) if row else {}),**health,'stored':count,'history_complete':False}


def documents(symbol):
    result=[]
    for e in records():
        body=e.get('body')
        if not body or not re.search(r'(?<![A-Z0-9])'+re.escape(symbol)+r'(?![A-Z0-9])',e['title']+' '+body,re.I):continue
        result.append(dict(id='bithumb-'+urlparse(e['pc_url']).path.rsplit('/',1)[1],title=e['title'],body=body,source=e['pc_url'],source_type='빗썸 공지 원문 (업비트 상태 아님)',exchange='Bithumb',verified=True,symbols=[symbol],published_at=e['published_at'],updated_at=e.get('modified_at',''),revision=e.get('modified_at') or e['published_at'],fingerprint=fingerprint(e),collected_at=e['received_at'],own=False))
    return result

def extract_body(html):
    soup=BeautifulSoup(html,'html.parser')
    main=soup.find('main')
    if not main:return None
    for x in main.select('script,style,nav,button'):x.decompose()
    text=main.get_text('\n',strip=True)
    return text if len(text)>100 else None

def sync_once(count=20,session=None,wait=time.sleep):
    if not guard.acquire(blocking=False):return 0
    session=session or requests.Session();session.headers['User-Agent']='KimpScope-EducationalResearch/0.3'
    try:
        health.update(state='polling',error=None)
        r=session.get('https://api.bithumb.com/v1/notices',params={'count':count},timeout=15);r.raise_for_status();rows=r.json()
        if not isinstance(rows,list):raise ValueError('Invalid notice list')
        previous={e['pc_url']:e for e in records()};changed=0;failures=[]
        for meta in rows:
            url=meta.get('pc_url','')
            if not valid_url(url):continue
            old=previous.get(url);revision=meta.get('modified_at') or meta.get('published_at','')
            if old and old.get('body') and (old.get('modified_at') or old['published_at'])>=revision:continue
            wait(1.1)
            body=None
            try:
                page=session.get(url,timeout=15,allow_redirects=False);page.raise_for_status()
                if page.status_code!=200:failures.append(f'HTTP {page.status_code}')
                else:
                    body=extract_body(page.content)
                    if body is None:failures.append(f'본문 구조 없음 ({len(page.content)}B)')
            except requests.RequestException as e:
                failures.append(f"HTTP {getattr(e.response,'status_code',None) or type(e).__name__}")
            changed+=save(meta,body)
        urls={e.get('pc_url') for e in rows}
        coverage={'possible_gap':bool(previous and urls and not urls.intersection(previous)),'last_successful_poll_at':int(time.time()*1000),'oldest_visible_published_at':min((e.get('published_at','') for e in rows),default=None),
                  # 본문을 못 받은 이유를 남긴다(운영에서 본문 21건이 모두 비어 있었는데 원인이 기록되지 않았다)
                  'body_failures':len(failures),'body_failure_last':failures[-1] if failures else None}
        with connect() as c:c.execute('INSERT INTO notice_sync_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload',('bithumb',json.dumps(coverage)))
        health.update(state='ready',last_poll_at=coverage['last_successful_poll_at'],changed=changed)
        return changed
    except Exception:
        health.update(state='error',error='빗썸 공지 수집 실패. 다음 주기에 재시도합니다.')
        raise
    finally:guard.release()

def run(stop):
    interval=max(60,int(os.getenv('NOTICE_POLL_SECONDS','300')))
    while not stop.is_set():
        try:sync_once(wait=lambda seconds:stop.wait(seconds))
        except Exception:pass
        stop.wait(interval)

def start():
    stop=threading.Event()
    if os.getenv('BITHUMB_NOTICES_ENABLED','true').lower()=='true':threading.Thread(target=run,args=(stop,),daemon=True).start()
    return stop
