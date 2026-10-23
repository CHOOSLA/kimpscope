"""허용 목록의 공식 문서 4건을 받아 data/documents.json(검색 후보 문서 팩)을 만든다.

고정 URL만 받는다(재귀 수집 없음). 요청 사이 1초, 429·5xx는 최대 3회 백오프 재시도(Retry-After 존중).
실제로 받은 원문만 verified=true로 표시한다. 검색 후보(collection.candidates)는 verified=true인 문서만 쓴다.
실행: python -m scripts.collect_sources   (거래소·공식 문서 사이트에 접속되는 PC에서)
"""
import json,time,hashlib
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
ROOT=Path(__file__).resolve().parents[1]
s=requests.Session();s.headers['User-Agent']='KimpScope-EducationalResearch/0.2 (local development; no recursive crawler)'
s.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504],respect_retry_after_header=True)))
sources=[('업비트 거래 페어 안내','https://docs.upbit.com/kr/reference/list-trading-pairs','거래소 API 문서',[]),('업비트 현재가 데이터 필드','https://docs.upbit.com/kr/reference/websocket-ticker','거래소 API 문서',[]),('비트코인 기초','https://bitcoin.org/en/how-it-works','프로젝트 공식 가이드',['BTC']),('이더리움 가스와 수수료','https://ethereum.org/en/developers/docs/gas/','프로젝트 공식 가이드',['ETH'])]
pack=[]
for title,url,kind,symbols in sources:
 r=s.get(url,timeout=30);r.raise_for_status();soup=BeautifulSoup(r.content,'html.parser')
 for n in soup(['script','style','nav','footer','header']):n.decompose()
 main=soup.find('article') or soup.find('main') or soup.find(id='content') or soup
 text=main.get_text(' ',strip=True)
 pack.append(dict(id=hashlib.sha256(url.encode()).hexdigest()[:16],title=title,body=text,source=url,source_type=kind,symbols=symbols,verified=True,collected_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),own=False))
 if len(text)<200:raise SystemExit(f'{title}: 본문이 너무 짧습니다({len(text)}자). 페이지 구조가 바뀌었을 수 있어 저장하지 않습니다.')
 print(title,len(text));time.sleep(1)
(ROOT/'data/documents.json').write_text(json.dumps(pack,ensure_ascii=False,indent=2),encoding="utf-8")
