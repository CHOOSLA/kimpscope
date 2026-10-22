import json
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from backend.main import app
from backend.market import snapshot
from backend.llm import available
from backend.store import collection
from backend.pipeline import graph
from backend.catalog import get_item

print("=== 1. 기본 설정 및 색인 상태 ===")
print("LLM 사용 가능 여부 (API Key):", available())
items_cnt = collection('items').count()
docs_cnt = collection('documents').count()
print(f"ChromaDB 메타데이터 색인: {items_cnt}건")
print(f"ChromaDB 문서 청크 색인: {docs_cnt}건")

print("\n=== 2. 실제 거래소 시세 API 연동 테스트 ===")
try:
    data = snapshot()
    rows = data.get('rows', [])
    print(f"시세 연동 성공! 조회된 종목 수: {len(rows)}개 (출처: {data.get('source')}, stale: {data.get('stale')})")
    for r in rows[:3]:
        symbol = r.get('symbol')
        domestic = r.get('domestic', 0)
        foreign = r.get('foreign', 0)
        premium = r.get('premium', 0)
        print(f"  - [{symbol}] 국내(업비트): {domestic:,}원 | 해외(바이낸스): ${foreign} | 김프: {premium:.2f}%")
except Exception as e:
    print("시세 연동 에러:", e)

print("\n=== 3. RAG 파이프라인 실제 질의 테스트 ===")
try:
    btc = get_item('BTC')
    res = graph().invoke({
        'item': btc,
        'question': '비트코인의 주요 특징과 발행 방식은 무엇인가요?',
        'k': 3,
        'mode': 'similarity'
    })
    print("RAG 질의응답 성공!")
    print("  답변 상태:", res.get('status'))
    print("  답변 내용 (일부):", res.get('answer', '')[:150], "...")
    print("  인용 출처 수:", len(res.get('citations', [])))
except Exception as e:
    print("RAG 질의 에러:", e)
