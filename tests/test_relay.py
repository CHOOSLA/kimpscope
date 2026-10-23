"""서버 위치에서 막힌 원문(빗썸 공지 본문 403)을 관리자 브라우저가 넘기는 경로와 공식 문서 저장."""
import json
import pytest
from fastapi.testclient import TestClient
from backend import bithumb_notices as b, official_docs, collection
from backend.catalog import get_item
from backend.main import app

client = TestClient(app)
META = {'title': '솔라나(SOL) 네트워크 입출금 일시 중지 안내', 'pc_url': 'https://feed.bithumb.com/notice/1655299',
        'published_at': '2026-10-20 15:15:00', 'modified_at': '2026-10-22 12:07:48'}
PAGE = '<html><body><nav>메뉴</nav><main>네트워크 업그레이드로 인해 일시 중지된 솔라나(SOL) 네트워크 관련 가상자산의 입출금 서비스를 재개합니다. ' + '대상 가상자산 안내. ' * 10 + '</main></body></html>'
DOC = '<html><body><header>h</header><article>' + 'All transactions are broadcast to the network and usually receive their first confirmation. ' * 4 + '</article></body></html>'


def post(**data):
    return client.post('/api/admin/relay', content=json.dumps(data), headers={'Content-Type': 'text/plain', 'Origin': 'https://feed.bithumb.com'})


def test_relay_disabled_without_token(monkeypatch):
    monkeypatch.delenv('RELAY_TOKEN', raising=False)
    assert post(token='', kind='bithumb', url=META['pc_url'], html=PAGE).status_code == 404


def test_relay_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv('RELAY_TOKEN', 'secret-token')
    assert post(token='nope', kind='bithumb', url=META['pc_url'], html=PAGE).status_code == 404


def test_relay_fills_missing_bithumb_body(monkeypatch):
    monkeypatch.setenv('RELAY_TOKEN', 'secret-token')
    b.save(META, None)  # 서버 수집에서 403으로 본문을 못 받은 상태
    assert not b.documents('SOL')
    r = post(token='secret-token', kind='bithumb', url=META['pc_url'], html=PAGE)
    assert r.json() == {'ok': True, 'changed': True}
    assert r.headers['access-control-allow-origin'] == 'https://feed.bithumb.com'
    doc = b.documents('SOL')[0]
    assert '재개합니다' in doc['body'] and '메뉴' not in doc['body']
    assert b.records()[0]['body_via'] == 'browser_relay'


def test_relay_only_for_listed_notices_and_real_bodies(monkeypatch):
    monkeypatch.setenv('RELAY_TOKEN', 'secret-token')
    assert post(token='secret-token', kind='bithumb', url='https://feed.bithumb.com/notice/1', html=PAGE).json() == {'ok': False, 'reason': '목록에 없는 공지'}
    b.save(META, None)
    assert post(token='secret-token', kind='bithumb', url=META['pc_url'], html='<html>login</html>').json()['ok'] is False


def test_official_docs_allowlist_and_candidates(monkeypatch):
    monkeypatch.setenv('RELAY_TOKEN', 'secret-token')
    assert post(token='secret-token', kind='official', url='https://evil.example/', html=DOC).json() == {'ok': False, 'reason': '허용 목록에 없는 문서'}
    assert post(token='secret-token', kind='official', url='https://bitcoin.org/en/how-it-works', html=DOC).json()['ok'] is True
    btc = [d for d in collection.candidates(get_item('BTC')) if d.get('source') == 'https://bitcoin.org/en/how-it-works']
    assert btc and btc[0]['verified'] and btc[0]['collected_via'] == 'browser_relay'
    assert not [d for d in collection.candidates(get_item('ETH')) if d.get('source') == 'https://bitcoin.org/en/how-it-works']


def test_server_fetch_records_blocked_reason():
    class Blocked:
        status_code = 403
        def raise_for_status(self):
            import requests
            raise requests.HTTPError('403', response=self)
    class Session:
        headers = {}
        def mount(self, *a): pass
        def get(self, url, **kw): return Blocked()
    failures = official_docs.fetch_missing(session=Session(), wait=lambda s: None)
    assert set(failures.values()) == {'HTTP 403'} and official_docs.health['stored'] == 0
