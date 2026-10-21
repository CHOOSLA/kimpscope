"""Allowlisted official documents; modest rate/retry. No recursive scraping."""
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
 r=s.get(url,timeout=30);r.raise_for_status();soup=BeautifulSoup(r.text,'html.parser')
 for n in soup(['script','style','nav','footer','header']):n.decompose()
 main=soup.find('article') or soup.find('main') or soup
 text=main.get_text(' ',strip=True)
 pack.append(dict(id=hashlib.sha256(url.encode()).hexdigest()[:16],title=title,body=text,source=url,source_type=kind,symbols=symbols,collected_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),own=False))
 print(title,len(text));time.sleep(1)
(ROOT/'data/documents.json').write_text(json.dumps(pack,ensure_ascii=False,indent=2))
