"""정부 보도자료(korea.kr) 수집: 사이트별 본문 위치, 첨부 PDF 본문, 이용 조건 기록, 담당자 연락처 제거."""
import pytest
from backend import official_docs as o, collection
from backend.catalog import get_item

PAGE_URL = 'https://www.korea.kr/news/policyNewsView.do?newsId=148969860'
PDF_URL = 'https://www.korea.kr/briefing/pressReleaseView.do?newsId=156574043'
BODY = '가상자산 이전 시 정보제공의무(트래블룰)가 현재 100만 원 이상에서 전체 거래로 확대된다. ' * 4
# 실측 구조(2026-10-23): main 안에 메뉴·공유 버튼·관련기사가 있고 본문은 div.view_cont 하나다
PAGE = ('<html><body><main id="main"><div class="breadcrumb">홈 뉴스 정책뉴스 공유하기 페이스북 X</div>'
        '<div class="article_body"><div class="view_cont">' + BODY + ' 문의 담당 kim@korea.kr 044-215-4750</div></div>'
        '<div class="related">실시간 인기뉴스 다른 기사 제목</div></main></body></html>').encode()


def pdf(text):
    """한 쪽짜리 최소 PDF(Helvetica, ASCII). 실제 첨부를 저장소에 넣지 않으려고 테스트 안에서 만든다."""
    stream = f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode()
    objs = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
            b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    out, offsets = b'%PDF-1.4\n', []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out)); out += b'%d 0 obj\n' % i + body + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % x for x in offsets)
    return out + b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, xref)


PDF_TEXT = 'Remittance limit without documents raised from 50000 to 100000 USD per year. ' * 4 + 'Contact kimyj1011@korea.kr'


def test_korea_kr_uses_body_selector_and_records_license():
    o.save(PAGE_URL, PAGE)
    doc = next(d for d in o.stored() if d['source'] == PAGE_URL)
    assert doc['body'].startswith('가상자산 이전 시') and '공유하기' not in doc['body'] and '인기뉴스' not in doc['body']
    assert '@' not in doc['body'] and '044-215-4750' not in doc['body']
    assert doc['license'].startswith('공공누리 제1유형') and doc['symbols'] == []


def test_korea_kr_without_body_block_is_not_saved_as_menu():
    menu_only = ('<html><body><main>' + '홈 브리핑룸 보도자료 공유하기 ' * 30 + '</main></body></html>').encode()
    with pytest.raises(ValueError):
        o.save(PAGE_URL, menu_only)
    assert not o.stored()


def test_attachment_document_reads_pdf_not_page():
    requested = []
    class Response:
        def __init__(self, content): self.content, self.status_code = content, 200
        def raise_for_status(self): pass
    class Session:
        headers = {}
        def mount(self, *a): pass
        def get(self, url, **kw):
            requested.append(url)
            return Response(pdf(PDF_TEXT) if url == o.ATTACHMENTS[PDF_URL] else PAGE)
    failures = o.fetch_missing(session=Session(), wait=lambda s: None)
    assert PDF_URL not in requested and o.ATTACHMENTS[PDF_URL] in requested
    doc = next(d for d in o.stored() if d['source'] == PDF_URL)
    assert 'Remittance limit' in doc['body'] and '@' not in doc['body']
    assert PDF_URL not in failures


def test_attachment_that_is_not_pdf_is_reported():
    class Response:
        content, status_code = b'<html>error page</html>', 200
        def raise_for_status(self): pass
    class Session:
        headers = {}
        def mount(self, *a): pass
        def get(self, url, **kw): return Response()
    failures = o.fetch_missing(session=Session(), wait=lambda s: None)
    assert failures[PDF_URL] == '첨부가 PDF가 아님'
    with pytest.raises(ValueError, match='첨부 PDF'):
        o.save(PDF_URL, PAGE)  # 관리자 브라우저 경유(HTML)로는 첨부 문서를 채우지 않는다


def test_policy_documents_are_candidates_for_every_coin():
    o.save(PAGE_URL, PAGE)
    for symbol in ('BTC', 'SOL', 'MBL'):
        assert any(d.get('source') == PAGE_URL for d in collection.candidates(get_item(symbol)))
