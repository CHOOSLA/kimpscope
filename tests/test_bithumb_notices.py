import pytest
from backend import bithumb_notices as b,notices

@pytest.fixture
def meta(tmp_path,monkeypatch):
    monkeypatch.setattr(notices,'DB',tmp_path/'events.sqlite3')
    return {'title':'온톨로지(ONT) 안내','pc_url':'https://feed.bithumb.com/notice/123','published_at':'2026-10-23 12:00:00','modified_at':'2026-10-23 12:00:00'}

def test_revision_duplicate_and_scope(meta):
    assert b.save(meta,'ONT 출금 중지')
    assert not b.save(meta,'ONT 출금 중지')
    assert b.documents('ONT')[0]['exchange']=='Bithumb'
    assert not b.documents('BTC')
    assert b.save({**meta,'modified_at':'2026-10-23 13:00:00'},'ONT 재개')
    assert not b.save(meta,'ONT 과거 중지')
    assert b.documents('ONT')[0]['body']=='ONT 재개'

def test_missing_body_excluded_and_retryable(meta):
    b.save(meta,None)
    assert not b.documents('ONT')
    assert b.save(meta,'ONT 원문 확보')
    assert b.documents('ONT')

def test_redirect_and_unknown_markup_rejected(meta):
    with pytest.raises(ValueError):b.save({**meta,'pc_url':'https://evil.example/notice/123'},'ONT')
    assert b.extract_body(b'<html><body>login page</body></html>') is None

def test_poll_uses_metadata_and_skips_unchanged_body(meta):
    class Response:
        status_code=200
        content=('<main>ONT '+('official notice '*15)+'</main>').encode()
        def raise_for_status(self):pass
        def json(self):return [meta]
    class Session:
        headers={}
        calls=[]
        def get(self,url,**kwargs):self.calls.append(url);return Response()
    s=Session()
    assert b.sync_once(session=s,wait=lambda _:None)==1
    assert b.sync_once(session=s,wait=lambda _:None)==0
    assert sum('feed.bithumb' in url for url in s.calls)==1

def test_gap_status_survives_memory_reset(meta):
    b.save(meta,'ONT old notice')
    fresh={**meta,'pc_url':'https://feed.bithumb.com/notice/999','modified_at':'2026-10-24 00:00:00'}
    class Response:
        status_code=200
        content=('<main>ONT '+('notice '*25)+'</main>').encode()
        def raise_for_status(self):pass
        def json(self):return [fresh]
    class Session:
        headers={}
        def get(self,*args,**kwargs):return Response()
    b.sync_once(session=Session(),wait=lambda _:None)
    assert b.sync_status()['possible_gap'] is True
    assert b.sync_status()['last_successful_poll_at']
    assert b.sync_status()['history_complete'] is False

def test_versions_preserved_latest_only(meta):
    b.save(meta,'BTC 중지')
    newer={**meta,'modified_at':'2026-10-23 13:00:00'}
    b.save(newer,'BTC 재개')
    assert len(b.versions('123'))==2
    assert not b.save(newer,'BTC 재개')
    assert len(b.versions('123'))==2
    assert not b.save(meta,'BTC 과거 이벤트')
    assert b.documents('BTC')[0]['body']=='BTC 재개'
    assert b.documents('BTC')[0]['fingerprint']

def test_same_revision_failed_fetch_keeps_valid_body(meta):
    b.save(meta,'BTC 원문')
    assert not b.save(meta,None)
    assert b.documents('BTC')[0]['body']=='BTC 원문'

def test_concurrent_versions_do_not_regress(meta):
    from concurrent.futures import ThreadPoolExecutor
    def write(n):
        return b.save({**meta,'modified_at':f'2026-10-23 13:{n:02d}:00'},f'BTC version {n}')
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(write,[3,1,4,2]))
    assert b.documents('BTC')[0]['body']=='BTC version 4'
    assert b.versions('123')

def test_history_api_rejects_bad_ids(meta):
    from fastapi.testclient import TestClient
    from backend.main import app
    b.save(meta,'BTC current')
    client=TestClient(app)
    assert client.get('/api/notices/bithumb/invalid/versions').status_code==400
    r=client.get('/api/notices/bithumb/123/versions')
    assert r.status_code==200
    assert len(r.json()['versions'])==1
    assert r.json()['history_complete'] is False

def test_index_uses_latest_revision_only(meta,tmp_path,monkeypatch):
    import chromadb
    from backend import store
    monkeypatch.setattr(store,'_client',chromadb.PersistentClient(path=str(tmp_path/'vectors')))
    monkeypatch.setattr(store,'DB_PATH',str(tmp_path/'vectors'))
    monkeypatch.setattr(store,'embed',lambda texts:[[0.5,0.5] for _ in texts])
    item={'id':'KRW-BTC'}
    b.save(meta,'BTC old body '*150)
    store.index_documents(item,b.documents('BTC'))
    old_count=store.collection('documents').count()
    b.save({**meta,'modified_at':'2026-10-23 14:00:00'},'BTC new body')
    current=b.documents('BTC')
    store.index_documents(item,current)
    found=store.collection('documents').get()
    assert len(found['ids'])<old_count
    assert found['documents']==['BTC new body']
    assert found['metadatas'][0]['source_fingerprint']==current[0]['fingerprint']
    assert len(b.versions('123'))==2

def test_body_failure_reason_is_recorded(meta):
    # 운영(2026-10-23): 공지 21건 모두 본문이 비어 있었지만 이유가 어디에도 남지 않았다
    class Listing:
        status_code=200
        def raise_for_status(self):pass
        def json(self):return [meta]
    class Blocked:
        status_code=302
        content=b''
        def raise_for_status(self):pass
    class Session:
        headers={}
        def get(self,url,**kwargs):return Listing() if 'api.bithumb' in url else Blocked()
    b.sync_once(session=Session(),wait=lambda _:None)
    st=b.sync_status()
    assert st['body_failures']==1 and st['body_failure_last']=='HTTP 302'
    assert not b.documents('ONT')
