import re
from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from .collection import collect
from .store import index_documents,retrieve
from .llm import available,model
from .prompts import GENERATE
class State(TypedDict,total=False):
    item:dict
    question:str
    k:int
    mode:str
    evidence:list
    answer:str
    citations:list
    cache_hit:bool
    status:str

def retrieve_node(s):
    # Serialize reconciliation and retrieval so another query cannot replace the corpus midway.
    from .store import lock
    with lock:
        gathered=collect(s['item'],s['question']);index_documents(s['item'],gathered['documents'])
        return {'evidence':retrieve(s['item'],s['question'],s['k'],s['mode']),'cache_hit':gathered['cache_hit']}


def requires_live_data(question):
    # API documentation examples are never a source of live quotes or wallet status.
    live = re.search(r'(지금|현재|오늘|실시간).*(가격|시세|출금|입금|입출금|거래.?가능)', question)
    forecast = re.search(r'(내일|미래|앞으로|다음.?주).*(가격|시세|오르|올라|내리|하락|상승|수익)', question)
    return bool(live or forecast)


def generate_node(s):
    if requires_live_data(s['question']):
        return {'answer':'저장된 문서와 API 응답 예시로는 현재 가격이나 입출금 가능 여부를 확인할 수 없습니다. 현재 가격은 별도의 시세 화면에서, 입출금 상태는 거래소의 최신 안내에서 확인하세요. 미래 가격과 수익도 예측하지 않습니다.','citations':[],'status':'unsupported_live_query'}
    if not available():return {'answer':'생성 모델 API 키가 설정되지 않았습니다. 아래는 실제 의미 검색으로 찾은 문서이며, 생성 답변의 인용은 아닙니다. 서버 환경변수 OPENAI_API_KEY 설정 후 근거 기반 답변을 사용할 수 있습니다.','citations':[],'status':'missing_key'}
    context='\n\n'.join(f"[{i+1}] {e['source_type']} | {e['title']}\n{e['text']}" for i,e in enumerate(s['evidence']))
    answer=model().invoke([('system',GENERATE),('human',f"질문: {s['question']}\n선택 항목: {s['item']['name']}\n근거:\n{context}")]).content
    numbers={int(x) for x in re.findall(r'\[(\d+)\]',str(answer))}
    if any(n<1 or n>len(s['evidence']) for n in numbers):return {'answer':'생성 답변의 인용을 검증하지 못했습니다. 원문을 확인하거나 다시 질문해 주세요.','citations':[],'status':'citation_error'}
    citations=[dict(number=i+1,**e) for i,e in enumerate(s['evidence']) if i+1 in numbers]
    if not citations and not any(w in str(answer) for w in ['확인','부족','없','모르']):answer='제공된 문서에서 검증 가능한 답변을 찾지 못했습니다.'
    return {'answer':str(answer),'citations':citations,'status':'ok'}

def graph():
    g=StateGraph(State);g.add_node('retrieve',retrieve_node);g.add_node('generate',generate_node);g.add_edge(START,'retrieve');g.add_edge('retrieve','generate');g.add_edge('generate',END);return g.compile()
