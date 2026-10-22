import pytest
from backend import pipeline


@pytest.mark.parametrize('question', [
    '지금 출금할 수 있고 내일 가격이 오르나요?',
    '현재 비트코인 가격이 얼마인가요?',
    '내일 가격이 상승할까요?',
])
def test_document_examples_cannot_answer_live_queries(question, monkeypatch):
    def forbidden():
        raise AssertionError('실시간 질문에 문서 기반 생성 모델을 호출하면 안 됩니다.')
    monkeypatch.setattr(pipeline, 'model', forbidden)
    result = pipeline.generate_node({
        'question': question, 'item': {'name': '비트코인'},
        'evidence': [{'title': 'API 예시', 'source_type': 'API 문서', 'text': 'trade_price: 3428000'}],
    })
    assert result['status'] == 'unsupported_live_query'
    assert result['citations'] == []
    assert '3428000' not in result['answer']


def test_current_price_field_documentation_is_still_allowed():
    assert not pipeline.requires_live_data('업비트 ticker에서 현재가와 거래 시각 필드는 무엇인가요?')
