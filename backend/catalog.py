import json
from .config import DATA

def items():
    return [dict(id=x['market'],symbol=x['market'].split('-')[1],name=x['korean_name'],english_name=x['english_name'],quote='KRW',exchange='Upbit',warning=bool(x.get('market_event',{}).get('warning',False)),source='https://api.upbit.com/v1/market/all') for x in json.loads((DATA/'markets.json').read_text(encoding="utf-8"))]

def item_text(x):
    return f"{x['name']} ({x['english_name']}, {x['symbol']}). 거래소 {x['exchange']}, 거래 페어 {x['id']}, 기준 통화 {x['quote']}, 유의종목 {'예' if x['warning'] else '아니오'}. 이 정보는 수집 시점의 거래소 메타데이터이며 현재 입출금 가능 여부는 제공하지 않는다."

def get_item(symbol):
    return next((x for x in items() if x['symbol']==symbol or x['id']==symbol),None)
