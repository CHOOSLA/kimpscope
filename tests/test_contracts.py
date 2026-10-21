import re
from backend.catalog import items,get_item
from backend.collection import candidates
from backend.main import app
from fastapi.testclient import TestClient
client=TestClient(app)
def test_catalog_unique_and_large():
    data=items();assert len(data)>=100;assert len({x['id'] for x in data})==len(data)
def test_own_document_unconditional():
    for symbol in ['BTC','ETH']:
        docs=candidates(get_item(symbol));assert docs[0]['own'];assert symbol in docs[0]['body']
def test_filter_excludes_nonmatching():
    r=client.post('/api/explore',json={'query':'유의종목이 아닌 비트코인'}).json()
    assert r['conditions']=={'warning':False,'symbol':'BTC'}
    assert all(x['symbol']=='BTC' and not x['warning'] for x in r['items'])
def test_unsupported_filter_abstains():
    assert client.post('/api/explore',json={'query':'가격 100원 이하'}).json()['items']==[]
def test_unknown_item():
    assert client.post('/api/query',json={'symbol':'UNKNOWN','question':'질문'}).status_code==404
def test_limits():
    assert client.post('/api/query',json={'symbol':'BTC','question':'질문','k':999}).status_code==422
