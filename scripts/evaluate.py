"""Five-question comparison. Missing credentials remain BLOCKED, never fake scores."""
import json,time
from pathlib import Path
from backend.catalog import get_item
from backend.pipeline import graph
from backend.llm import available,model
questions=[('BTC','비트코인 트랜잭션은 어떻게 검증되나요?'),('ETH','이더리움 가스비는 무엇인가요?'),('ETH','수수료는 왜 필요한가요?'),('BTC','업비트 ticker에서 현재가와 거래 시각 필드는 무엇인가요?'),('BTC','지금 출금할 수 있고 내일 가격이 오르나요?')]
rows=[]
for symbol,q in questions:
 start=time.monotonic();result=graph().invoke({'item':get_item(symbol),'question':q,'k':5,'mode':'similarity'})
 without=model().invoke(q).content if available() else None
 rows.append(dict(symbol=symbol,question=q,without_rag=without,with_rag=result['answer'],status=result['status'],citations=result['citations'],elapsed_seconds=round(time.monotonic()-start,2),review='사실 정확성·근거 적합성 사람 검토 필요' if available() else 'BLOCKED: OPENAI_API_KEY 미설정'))
Path('docs/evaluation.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print(json.dumps({'questions':len(rows),'generation_verified':available()},ensure_ascii=False))
