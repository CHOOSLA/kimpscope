import json,time
from pathlib import Path
from backend.store import index_metadata,collection,index_documents,retrieve
from backend.catalog import get_item
from backend.collection import collect
from backend.pipeline import graph
start=time.monotonic()
before=collection('items').count();after=index_metadata();assert after>=100
repeated=index_metadata();assert repeated==after
item=get_item('BTC');q='비트코인 트랜잭션은 어떻게 검증되나요?'
a=collect(item,q);b=collect(item,q);assert b['cache_hit'];assert any(d.get('own') for d in b['documents'])
index_documents(item,a['documents']);count=collection('documents').count();index_documents(item,a['documents']);assert count==collection('documents').count()
sim=retrieve(item,q,5,'similarity');mmr=retrieve(item,q,5,'mmr');assert sim[0]['id']==item['id'];assert len({x['text'] for x in sim})==len(sim)
eth=get_item('ETH');index_documents(eth,collect(eth,'가스비란?')['documents']);btc_ids=collection('documents').get(where={'item_id':item['id']})['ids'];eth_ids=collection('documents').get(where={'item_id':eth['id']})['ids'];assert not set(btc_ids)&set(eth_ids)
result={'metadata_before':before,'metadata_after':after,'metadata_repeated':repeated,'idempotent_documents':True,'cache_hit':b['cache_hit'],'own_document_included':True,'item_scoped_ids':True,'similarity_ids':[x['id'] for x in sim],'mmr_ids':[x['id'] for x in mmr],'graph_nodes':list(graph().get_graph().nodes),'elapsed_seconds':round(time.monotonic()-start,2)}
Path('docs/pipeline-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(result,ensure_ascii=False))
