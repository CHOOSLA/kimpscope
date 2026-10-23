"""Public Bithumb notice polling; official metadata and fetched HTML kept distinct."""
import json,time,threading,os,re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from . import notices
health={'state':'idle','last_poll_at':None,'error':None,'changed':0}
guard=threading.Lock()

def connect():
    c=notices.connect()
    c.execute('CREATE TABLE IF NOT EXISTS bithumb_notices (url TEXT PRIMARY KEY, revision TEXT NOT NULL, payload TEXT NOT NULL)')
    return c

def valid_url(url):
    p=urlparse(url)
    return p.scheme=='https' and p.hostname=='feed.bithumb.com' and bool(re.fullmatch(r'/notice/\d+',p.path)) and not p.query and not p.fragment

def save(meta,body):
    url=meta.get('pc_url','');revision=meta.get('modified_at') or meta.get('published_at')
    if not valid_url(url) or not revision or not meta.get('title'):raise ValueError('Invalid official metadata')
    payload={**meta,'body':body,'received_at':int(time.time()*1000)}
    with connect() as c:
        old=c.execute('SELECT revision,payload FROM bithumb_notices WHERE url=?',(url,)).fetchone()
        if old and (old[0]>revision or (old[0]==revision and json.loads(old[1]).get('body')==body)):return False
        c.execute('INSERT INTO bithumb_notices VALUES (?,?,?) ON CONFLICT(url) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',(url,revision,json.dumps(payload,ensure_ascii=False)))
    return True

def records():
    with connect() as c:rows=c.execute('SELECT payload FROM bithumb_notices ORDER BY revision DESC').fetchall()
    return [json.loads(r[0]) for r in rows]

def documents(symbol):
    result=[]
    for e in records():
        body=e.get('body')
        if not body or not re.search(r'(?<![A-Z0-9])'+re.escape(symbol)+r'(?![A-Z0-9])',e['title']+' '+body,re.I):continue
        result.append(dict(id='bithumb-'+urlparse(e['pc_url']).path.rsplit('/',1)[1],title=e['title'],body=body,source=e['pc_url'],source_type='빗썸 공지 원문 (업비트 상태 아님)',exchange='Bithumb',verified=True,symbols=[symbol],published_at=e['published_at'],updated_at=e.get('modified_at',''),revision=e.get('modified_at') or e['published_at'],collected_at=e['received_at'],own=False))
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
        previous={e['pc_url']:e for e in records()};changed=0
        for meta in rows:
            url=meta.get('pc_url','')
            if not valid_url(url):continue
            old=previous.get(url);revision=meta.get('modified_at') or meta.get('published_at','')
            if old and old.get('body') and (old.get('modified_at') or old['published_at'])>=revision:continue
            wait(1.1)
            body=None
            try:
                page=session.get(url,timeout=15,allow_redirects=False);page.raise_for_status()
                if page.status_code==200:body=extract_body(page.content)
            except requests.RequestException:pass
            changed+=save(meta,body)
        health.update(state='ready',last_poll_at=int(time.time()*1000),changed=changed)
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
