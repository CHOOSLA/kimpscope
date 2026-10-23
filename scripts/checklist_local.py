"""체크리스트 1·2·5·7·13번(F2001·F2002·F2005·F2007·F2012) 로컬 증빙.

외부 모델을 부르지 않도록 임베딩을 결정적 스텁(텍스트 해시 → 벡터)으로 바꿔 실행한다.
항목 수·청크 수·재색인 결과·그래프 구조는 임베딩 값과 무관하므로 실제 색인 코드(store.py)를 그대로 검증한다.
검색 품질(Top-k·MMR 결과)은 실제 임베딩이 필요해 운영 API로 따로 확인한다.

실행: python -m scripts.checklist_local  →  docs/checklist/evidence/local_index.json
"""
import hashlib,json,os,sys,tempfile,time
from pathlib import Path

tmp=tempfile.mkdtemp(prefix='kimpscope-checklist-')
os.environ['CHROMA_PATH']=str(Path(tmp)/'chroma')
os.environ.pop('OPENAI_API_KEY',None)  # 수집 단계도 모델 없이(제공 문서 팩 전체) 돈다

from backend import store
from backend.catalog import items,item_text,get_item
from backend.collection import candidates
from backend.pipeline import graph

def stub_embed(texts):
    out=[]
    for t in texts:
        h=hashlib.sha256(t.encode()).digest()
        v=[(b-127.5)/127.5 for b in h*12][:384]
        n=sum(x*x for x in v)**.5
        out.append([x/n for x in v])
    return out
store.embed=stub_embed

def chunk_count(item):
    return len(store.collection('documents').get(where={'item_id':item['id']})['ids'])

def main():
    started=time.time();r={'embedding':'결정적 스텁(외부 호출 없음). 수량 검증 전용','chroma_path':'임시 폴더'}
    loaded=items()
    from fastapi.testclient import TestClient
    from backend.main import app
    api=TestClient(app)  # lifespan(공지 수집 스레드)은 돌리지 않는다
    # F2012: 색인이 없을 때 안내
    no_index=api.post('/api/query',json={'symbol':'BTC','question':'비트코인 전송 전에 확인할 것은?'})
    r['F2012']={'no_index':{'http':no_index.status_code,'message':no_index.json().get('detail')}}
    # F2001: 로드 건수 = 컬렉션 건수, 항목 1건의 색인 텍스트
    first=store.index_metadata()
    btc=get_item('BTC');saved=store.collection('items').get(ids=[btc['id']])
    text=saved['documents'][0]
    attrs={'한글명':btc['name'],'영문명':btc['english_name'],'심볼':btc['symbol'],'거래 페어':btc['id'],'기준 통화':btc['quote'],'거래소':btc['exchange']}
    r['F2001']={'loaded_items':len(loaded),'items_collection_count':first,'equal':len(loaded)==first,
                'sample_id':btc['id'],'sample_text':text,
                'attributes_in_text':{k:(v in text) for k,v in attrs.items()}|{'유의종목 여부':'유의종목' in text}}
    # F2002: 두 번 색인해도 늘지 않는다 (메타데이터, 외부 문서 모두)
    second=store.index_metadata()
    docs=candidates(btc)
    store.index_documents(btc,docs);c1=chunk_count(btc)
    store.index_documents(btc,docs);c2=chunk_count(btc)
    r['F2002']={'items_first':first,'items_second':second,'documents_first':c1,'documents_second':c2,'unchanged':first==second and c1==c2}
    # F2005: 청크 설정을 바꾸면 청크 수가 달라진다 (지문에 청크 설정이 들어 있어 자동 재색인)
    base=(store.CHUNK_SIZE,store.CHUNK_OVERLAP);runs=[]
    for size,overlap in [base,(400,60),(1200,200)]:
        store.CHUNK_SIZE,store.CHUNK_OVERLAP=size,overlap
        store.index_documents(btc,docs);runs.append({'chunk_size':size,'chunk_overlap':overlap,'chunks':chunk_count(btc)})
    store.CHUNK_SIZE,store.CHUNK_OVERLAP=base
    r['F2005']={'item':btc['id'],'documents':len(docs),'source_types':sorted({d['source_type'] for d in docs}),'runs':runs,
                'differs':len({x['chunks'] for x in runs})==len(runs)}
    # F2005 ID 충돌: 같은 문서가 다른 항목에 색인돼도 덮어쓰지 않는다
    eth=get_item('ETH');store.index_documents(eth,candidates(eth))
    b=set(store.collection('documents').get(where={'item_id':btc['id']})['ids']);e=set(store.collection('documents').get(where={'item_id':eth['id']})['ids'])
    r['F2005']['id_scheme']='항목ID:문서ID:청크순번';r['F2005']['btc_eth_overlap_ids']=len(b&e)
    # F2012: 모델 키가 없을 때 안내 (색인은 있는 상태)
    no_key=api.post('/api/query',json={'symbol':'BTC','question':'비트코인 전송 전에 확인할 것은?'}).json()
    r['F2012']['no_key']={'status':no_key.get('status'),'answer':no_key.get('answer'),'evidence_shown':len(no_key.get('evidence') or [])}
    # F2007: LangGraph 노드
    r['F2007']={'nodes':list(graph().get_graph().nodes),'edges':[(x.source,x.target) for x in graph().get_graph().edges]}
    r['elapsed_s']=round(time.time()-started,2)
    out=Path('docs/checklist/evidence/local_index.json');out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False,indent=2))
    ok=r['F2012']['no_index']['http']==409 and r['F2012']['no_key']['status']=='missing_key' and r['F2001']['equal'] and all(r['F2001']['attributes_in_text'].values()) and r['F2002']['unchanged'] and r['F2005']['differs'] and not r['F2005']['btc_eth_overlap_ids']
    return 0 if ok else 1

if __name__=='__main__':sys.exit(main())
