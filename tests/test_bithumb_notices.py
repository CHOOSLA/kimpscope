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
