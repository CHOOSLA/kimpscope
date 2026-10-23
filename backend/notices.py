"""Official announcement event persistence. No synthesized notice bodies."""
import hashlib,json,os,re,sqlite3,time,threading,base64,hmac,uuid
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from .config import DATA
DB=Path(os.getenv('NOTICE_DB_PATH',str(DATA/'notices.sqlite3')))
health={'state':'disabled','last_received_at':None,'error':None}

def connect():
    from .notice_db import connect as storage_connect
    c=storage_connect(DB)
    c.execute('CREATE TABLE IF NOT EXISTS notices (id TEXT PRIMARY KEY, timestamp BIGINT NOT NULL, payload TEXT NOT NULL)')
    return c

def accept(event):
    if event.get('type')!='announcement' or event.get('event_type') not in ('CREATED','UPDATED'):raise ValueError('Invalid event')
    url=urlparse(event.get('url',''))
    if url.scheme!='https' or url.hostname not in ('upbit.com','www.upbit.com') or url.path!='/service_center/notice' or not parse_qs(url.query).get('id'):raise ValueError('Invalid source')
    if not event.get('uuid') or not event.get('title') or not isinstance(event.get('timestamp'),int):raise ValueError('Invalid identity')
    event={**event,'received_at':int(time.time()*1000)}
    with connect() as c:
        result=c.execute('INSERT INTO notices VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET timestamp=excluded.timestamp,payload=excluded.payload WHERE excluded.timestamp > notices.timestamp',(str(event['uuid']),event['timestamp'],json.dumps(event,ensure_ascii=False)))
        return result.rowcount==1

def documents(symbol):
    with connect() as c:rows=c.execute('SELECT payload FROM notices ORDER BY timestamp DESC').fetchall()
    result=[]
    for row in rows:
        e=json.loads(row[0]);body=e.get('body')
        # Only explicit symbol associations; unmatched notices remain stored for review.
        if not body or not re.search(r'(?<![A-Z0-9])'+re.escape(symbol)+r'(?![A-Z0-9])',e['title']+' '+body,re.I):continue
        result.append(dict(id='upbit-'+str(e['uuid']),title=e['title'],body=body,source=e['url'],source_type='업비트 공지 원문',symbols=[symbol],verified=True,published_at=e.get('first_listed_at',''),updated_at=e.get('listed_at',''),collected_at=e['received_at'],revision=e['timestamp'],own=False))
    return result

def token():
    enc=lambda x:base64.urlsafe_b64encode(x).rstrip(b'=')
    head=enc(b'{"alg":"HS512","typ":"JWT"}')  # 업비트 공식 문서 권장 서명 알고리즘
    body=enc(json.dumps({'access_key':os.environ['UPBIT_ACCESS_KEY'],'nonce':str(uuid.uuid4())}).encode())
    message=head+b'.'+body
    return (message+b'.'+enc(hmac.new(os.environ['UPBIT_SECRET_KEY'].encode(),message,hashlib.sha512).digest())).decode()

def run(stop):
    from websockets.sync.client import connect as websocket
    delay=1
    while not stop.is_set():
        try:
            health.update(state='connecting',error=None)
            with websocket('wss://api.upbit.com/websocket/v1/private',additional_headers={'Authorization':'Bearer '+token()},open_timeout=15) as ws:
                ws.send(json.dumps([{'ticket':str(uuid.uuid4())},{'type':'announcement','include_body':True}]))
                health.update(state='connected');delay=1
                while not stop.is_set():
                    try:raw=ws.recv(timeout=2)
                    except TimeoutError:continue
                    event=json.loads(raw)
                    if 'error' in event:raise ValueError('Subscription rejected')
                    accept(event);health['last_received_at']=int(time.time()*1000)
        except Exception:
            health.update(state='reconnecting',error='공지 연결 실패. 인증·허용 IP·네트워크를 확인하세요.')
            stop.wait(delay);delay=min(delay*2,60)
    health['state']='stopped'

def start():
    stop=threading.Event()
    if os.getenv('UPBIT_ACCESS_KEY') and os.getenv('UPBIT_SECRET_KEY'):
        threading.Thread(target=run,args=(stop,),daemon=True).start()
    return stop
