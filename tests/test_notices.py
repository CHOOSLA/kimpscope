import pytest
from backend import notices

@pytest.fixture
def event_db(tmp_path,monkeypatch):
    monkeypatch.setattr(notices,'DB',tmp_path/'events.sqlite3')
    return {'type':'announcement','event_type':'CREATED','uuid':'42','timestamp':100,'title':'BTC 입출금 안내','url':'https://upbit.com/service_center/notice?id=42','body':'BTC 출금 중단'}

def test_duplicate_and_out_of_order(event_db):
    e=event_db
    assert notices.accept(e)
    assert not notices.accept(e)
    assert not notices.accept({**e,'timestamp':99,'body':'BTC 오래된 내용'})
    assert notices.accept({**e,'event_type':'UPDATED','timestamp':101,'body':'BTC 재개'})
    assert notices.documents('BTC')[0]['body']=='BTC 재개'
    assert not notices.documents('ETH')

def test_missing_updated_body_hides_previous_version(event_db):
    notices.accept(event_db)
    notices.accept({**event_db,'timestamp':101,'body':None})
    assert notices.documents('BTC')==[]

def test_reject_nonofficial_source(event_db):
    with pytest.raises(ValueError):notices.accept({**event_db,'url':'https://evil.example/notice?id=42'})

def test_unverified_pack_excluded(tmp_path,monkeypatch,event_db):
    import json
    from backend import collection
    from backend.catalog import get_item
    (tmp_path/'documents.json').write_text(json.dumps([{'id':'bad','body':'invented','symbols':['BTC']}]),encoding='utf-8')
    monkeypatch.setattr(collection,'DATA',tmp_path)
    assert all(d['id']!='bad' for d in collection.candidates(get_item('BTC')))

def test_update_invalidates_question_cache(tmp_path,monkeypatch,event_db):
    from backend import collection
    from backend.catalog import get_item
    monkeypatch.setattr(collection,'DATA',tmp_path)
    monkeypatch.setattr(collection,'CACHE',tmp_path/'cache.json')
    monkeypatch.setattr(collection,'available',lambda:False)
    notices.accept(event_db)
    first=collection.collect(get_item('BTC'),'안내')
    assert collection.collect(get_item('BTC'),'안내')['cache_hit']
    notices.accept({**event_db,'timestamp':102,'body':'BTC 재개'})
    updated=collection.collect(get_item('BTC'),'안내')
    assert not updated['cache_hit']
    assert first['documents']!=updated['documents']
