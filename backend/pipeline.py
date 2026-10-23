import re
from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from .collection import collect
from .store import index_documents,retrieve
from .llm import available,model
from .prompts import GENERATE
from . import live
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
        evidence=retrieve(s['item'],s['question'],s['k'],s['mode'])
    # 실시간 근거는 색인하지 않는다. 검색되는 순간 지난 값이 되기 때문이다. 질문마다 새로 만들어 메타데이터 다음에 둔다.
    evidence=evidence[:1]+live.evidence(s['item'])+evidence[1:]
    return {'evidence':evidence,'cache_hit':gathered['cache_hit']}


def requires_live_data(question):
    """현재 값이나 예측을 요구하는 질문인가. 문서 속 API 예시나 과거 공지는 이런 질문의 근거가 될 수 없다."""
    return bool(live.needs(question))

KIND_LABEL={'market':'현재 시세·김프','state':'현재 입출금·경보 상태'}

def generate_node(s):
    needed=live.needs(s['question'])
    if 'forecast' in needed:
        return {'answer':'미래 가격·수익이나 매매 판단은 예측하지 않습니다. 현재 시세와 김치 프리미엄은 기준 시각과 함께 확인할 수 있습니다.','citations':[],'status':'unsupported_live_query'}
    evidence=s.get('evidence') or []
    fresh={e['live'] for e in evidence if e.get('live') and not e.get('stale')}
    missing=needed-fresh
    if missing:
        # 최신 실시간 근거가 없으면 문서 속 숫자로 대신 답하지 않는다(API 예시 가격을 현재가로 답한 오류 재발 방지).
        what='·'.join(KIND_LABEL[k] for k in sorted(missing))
        return {'answer':f'{what}을(를) 확인할 최신 실시간 근거가 없어 답하지 않습니다. 저장된 문서나 API 예시의 숫자는 현재 값이 아닙니다. 시세 화면 또는 거래소 최신 안내를 확인하세요.','citations':[],'status':'unsupported_live_query'}
    if not available():return {'answer':'생성 모델 API 키가 설정되지 않았습니다. 아래는 실제 의미 검색으로 찾은 문서이며, 생성 답변의 인용은 아닙니다. 서버 환경변수 OPENAI_API_KEY 설정 후 근거 기반 답변을 사용할 수 있습니다.','citations':[],'status':'missing_key'}
    context='\n\n'.join(f"[{i+1}] {e['source_type']} | {e['title']} | 거래소: {e.get('exchange','미상')} | 게시: {e.get('published_at','미상')} | 개정: {e.get('revision','미상')}\n{e['text']}" for i,e in enumerate(evidence))
    answer=model().invoke([('system',GENERATE),('human',f"질문: {s['question']}\n선택 항목: {s['item']['name']}\n근거:\n{context}")]).content
    numbers={int(x) for x in re.findall(r'\[(\d+)\]',str(answer))}
    if any(n<1 or n>len(evidence) for n in numbers):return {'answer':'생성 답변의 인용을 검증하지 못했습니다. 원문을 확인하거나 다시 질문해 주세요.','citations':[],'status':'citation_error'}
    citations=[dict(number=i+1,**e) for i,e in enumerate(evidence) if i+1 in numbers]
    if needed-{c['live'] for c in citations if c.get('live')}:
        # 규칙 판정: 현재 값 질문인데 실시간 근거를 인용하지 않은 답은 쓰지 않는다
        return {'answer':'생성 답변이 실시간 근거를 인용하지 않아 현재 값으로 제시하지 않습니다. 다시 질문해 주세요.','citations':[],'status':'live_citation_missing'}
    if not citations and not any(w in str(answer) for w in ['확인','부족','없','모르']):answer='제공된 문서에서 검증 가능한 답변을 찾지 못했습니다.'
    return {'answer':str(answer),'citations':citations,'status':'ok'}

def graph():
    g=StateGraph(State);g.add_node('retrieve',retrieve_node);g.add_node('generate',generate_node);g.add_edge(START,'retrieve');g.add_edge('retrieve','generate');g.add_edge('generate',END);return g.compile()
