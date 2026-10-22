import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from backend.store import collection, client
from backend.catalog import get_item
from backend.pipeline import graph

# 캐시 초기화
p = pathlib.Path('data/query-cache.json')
if p.exists():
    p.unlink()

# 기존 documents 컬렉션 리셋
try:
    client().delete_collection('documents')
except Exception:
    pass

print("=== 1. 리플(XRP) 공시 질의 테스트 ===")
xrp = get_item('XRP')
res = graph().invoke({
    'item': xrp,
    'question': '리플(XRP) 최근에 SEC 소송이나 입출금 관련해서 어떤 공시가 있었나요?',
    'k': 4,
    'mode': 'similarity'
})
print("상태:", res.get('status'))
print("답변:\n", res.get('answer'))
print("\n인용된 문서:")
for c in res.get('citations', []):
    print(f"  [{c.get('number')}] {c.get('title')} ({c.get('source_type')})")

print("\n=== 2. 솔라나(SOL) 메인넷 업그레이드 질의 테스트 ===")
sol = get_item('SOL')
res2 = graph().invoke({
    'item': sol,
    'question': '솔라나 최근 메인넷 업데이트나 트랜잭션 혼잡 관련 공시는 무엇인가요?',
    'k': 4,
    'mode': 'similarity'
})
print("상태:", res2.get('status'))
print("답변:\n", res2.get('answer'))
print("\n인용된 문서:")
for c in res2.get('citations', []):
    print(f"  [{c.get('number')}] {c.get('title')} ({c.get('source_type')})")
