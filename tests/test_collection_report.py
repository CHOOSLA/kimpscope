"""F2003·F2004: 검색어 목록과 선별 결과(색인 / 제외)를 응답에서 확인할 수 있다."""
import json
from backend import collection as source_collection
from backend.catalog import get_item
from backend.llm import Keywords, Selection


def test_selection_reports_kept_and_discarded(tmp_path, monkeypatch):
    (tmp_path / 'documents.json').write_text(json.dumps([
        {'id': 'net', 'title': '비트코인 네트워크 점검', 'body': '점검 중 입출금 중지', 'source': 'https://example.com/a',
         'source_type': '테스트', 'verified': True, 'symbols': ['BTC']},
        {'id': 'event', 'title': '에어드랍 이벤트', 'body': '이벤트 안내', 'source': 'https://example.com/b',
         'source_type': '테스트', 'verified': True, 'symbols': ['BTC']},
    ], ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(source_collection, 'DATA', tmp_path)
    monkeypatch.setattr(source_collection, 'CACHE', tmp_path / 'query-cache.json')
    monkeypatch.setattr(source_collection, 'available', lambda: True)
    calls = []

    def fake_structured(prompt, text, schema):
        calls.append(schema)
        # 프롬프트 2가 자체 문서를 빼먹어도 자체 문서는 남아야 한다
        return Keywords(keywords=['입출금 중지', '점검']) if schema is Keywords else Selection(selected=['net'])
    monkeypatch.setattr(source_collection, 'structured', fake_structured)

    item = get_item('BTC')
    first = source_collection.collect(item, '입금이 왜 막혔어?')
    assert first['keywords'][:2] == ['비트코인', 'BTC'] and '입출금 중지' in first['keywords']
    kept = {d['id'] for d in first['documents']}
    assert kept == {'own-KRW-BTC', 'net'}
    assert [d['id'] for d in first['discarded']] == ['event']
    second = source_collection.collect(item, '입금이 왜 막혔어?')
    assert second['cache_hit'] is True and second['discarded'] == first['discarded']
    assert len(calls) == 2  # 두 번째 질문은 프롬프트 1·2를 다시 부르지 않는다
