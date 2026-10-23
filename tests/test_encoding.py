"""한글 원문과 질문 캐시의 Windows UTF-8 회귀 검증."""
import json
from backend import collection as source_collection
from backend.catalog import get_item


def test_korean_source_and_cache_round_trip(tmp_path, monkeypatch):
    (tmp_path / 'documents.json').write_text(json.dumps([
        {'id': 'ko-guide', 'title': '전송 확인', 'body': '주소와 수수료를 확인하세요.',
         'source': 'https://example.com/guide', 'source_type': '테스트', 'verified': True, 'symbols': ['BTC']}
    ], ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(source_collection, 'DATA', tmp_path)
    monkeypatch.setattr(source_collection, 'CACHE', tmp_path / 'query-cache.json')
    monkeypatch.setattr(source_collection, 'available', lambda: False)
    first = source_collection.collect(get_item('BTC'), '전송 전에 무엇을 확인하나요?')
    second = source_collection.collect(get_item('BTC'), '전송 전에 무엇을 확인하나요?')
    assert first['cache_hit'] is False
    assert second['cache_hit'] is True
    assert any(d['body'] == '주소와 수수료를 확인하세요.' for d in second['documents'])
    cached = json.loads((tmp_path / 'query-cache.json').read_text(encoding='utf-8'))
    assert cached
