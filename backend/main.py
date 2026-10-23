import json,re,time,threading
from fastapi import FastAPI,HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .config import ROOT,TOP_K
from .catalog import items,get_item
from .store import collection,index_metadata
from .collection import candidates
from .pipeline import graph
from .llm import available,structured,Conditions
from contextlib import asynccontextmanager
from . import notices,bithumb_notices
@asynccontextmanager
async def lifespan(app):
    stop=notices.start()
    bithumb_stop=bithumb_notices.start()
    yield
    stop.set()
    bithumb_stop.set()
app=FastAPI(title='KimpScope Research API',lifespan=lifespan)
@app.get('/api/notices/status')
def notice_status():return {'upbit':notices.health,'bithumb':bithumb_notices.sync_status(),'history_complete':False,'indexing':'on_query'}

state={'state':'idle','message':'색인 준비 전'};guard=threading.Lock()
class Query(BaseModel):
    symbol:str=Field(min_length=1,max_length=30)
    question:str=Field(min_length=1,max_length=1000)
    k:int=Field(default=TOP_K,ge=1,le=12)
    mode:str=Field(default='similarity',pattern='^(similarity|mmr)$')
class Explore(BaseModel):query:str=Field(min_length=1,max_length=300)
@app.get('/api/status')
def status():return dict(**state,items=len(items()),indexed=collection('items').count(),chunks=collection('documents').count(),llm_ready=available())
@app.get('/api/items')
def catalog():return items()
@app.get('/api/documents/{symbol}')
def documents(symbol:str):
    item=get_item(symbol)
    if not item:raise HTTPException(404,'항목을 찾을 수 없습니다.')
    return candidates(item)
@app.post('/api/index')
def index():
    if not guard.acquire(blocking=False):return state
    def run():
        state.update(state='indexing',message='다국어 임베딩 및 메타데이터 색인 중')
        try:n=index_metadata();state.update(state='ready',message=f'{n}건 색인 완료')
        except Exception:state.update(state='error',message='색인에 실패했습니다. 모델 다운로드 연결과 서버 로그를 확인하세요.')
        finally:guard.release()
    threading.Thread(target=run,daemon=True).start();return state
@app.post('/api/query')
def query(q:Query):
    item=get_item(q.symbol)
    if not item:raise HTTPException(404,'선택 항목이 없습니다.')
    if not collection('items').get(ids=[item['id']])['ids']:raise HTTPException(409,'검색 색인이 없습니다. 데이터 색인을 먼저 실행하세요.')
    try:
        start=time.monotonic();out=graph().invoke({'item':item,'question':q.question,'k':q.k,'mode':q.mode})
        return {k:out.get(k) for k in ['answer','citations','evidence','cache_hit','status']}|{'elapsed_ms':round((time.monotonic()-start)*1000)}
    except Exception:raise HTTPException(503,'검색 또는 생성 서비스가 응답하지 않습니다. 잠시 후 다시 시도하세요.')
@app.post('/api/explore')
def explore(q:Explore):
    text=q.query.strip();condition={}
    if available():
        try:condition=structured('조건을 symbol, warning, name_contains로 추출한다. 유의종목이 아니면 warning=false. 없는 조건은 null. 시장 가격 조건은 지원하지 않는다.',text,Conditions).model_dump(exclude_none=True)
        except Exception:raise HTTPException(503,'조건 해석을 완료하지 못했습니다.')
    else:
        if re.search(r'가격|이상|이하|프리미엄|거래량',text):return {'items':[],'conditions':{},'message':'현재 조건 탐색은 이름·심볼·유의종목 여부를 지원합니다. 가격 조건은 시세표 필터를 사용하세요.'}
        if '유의' in text:condition['warning']=not any(w in text for w in ['아닌','아니','제외','없는'])
        matches=[x for x in items() if x['name'] in text or re.search(r'\b'+re.escape(x['symbol'])+r'\b',text,re.I)]
        if matches:condition['symbol']=matches[0]['symbol']
        if not condition:return {'items':[],'conditions':{},'message':'이름·심볼 또는 유의종목 조건을 입력해 주세요. 예: 유의종목이 아닌 비트코인'}
    found=[x for x in items() if all(x.get(k)==v if k!='name_contains' else v.lower() in (x['name']+' '+x['english_name']).lower() for k,v in condition.items())]
    return {'items':found,'conditions':condition,'message':f'{len(found)}개 항목 일치'}
@app.get('/api/market')
def market():
    from .market import snapshot
    return snapshot()
@app.get('/api/candles/{symbol}')
def candles(symbol:str,period:str='1H'):
    if not get_item(symbol) or period not in ['1H','24H','7D']:raise HTTPException(400,'유효하지 않은 조회 조건입니다.')
    try:
        from .market import candles as load
        return load(symbol,period)
    except Exception:raise HTTPException(503,'캔들 데이터를 불러오지 못했습니다.')
app.mount('/',StaticFiles(directory=ROOT/'dist',html=True),name='frontend')
