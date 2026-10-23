"""Render 크론 진입점: 빗썸 공지 동기화 + 거래소 입출금·경보 수집을 한 번 실행하고 끝난다.

무료 웹 서비스는 잠들면 내부 수집 스레드도 멈춘다. 이 작업이 그 사이를 메운다.
웹 서비스의 수집 스레드와 동시에 돌아도 된다: 공지 저장은 URL 단위 잠금(Postgres 자문 잠금)으로 묶여 있다.

실행: python -m scripts.cron_collect
의존성: requirements-cron.txt (Chroma·LangChain·torch를 불러오지 않는다)
종료 코드: 모든 소스가 실패하면 1, 하나라도 성공하면 0. 결과는 한 줄 JSON으로 출력한다(키 값은 출력하지 않는다).
"""
import json,sys,time
from backend import bithumb_notices,exchange_status
from backend.notice_db import mode

def main():
    started=time.time();results={}
    try:
        results['bithumb.notices']={'ok':True,'changes':bithumb_notices.sync_once(wait=time.sleep)}
    except Exception as e:
        results['bithumb.notices']={'ok':False,'error':f'{type(e).__name__}: {e}'[:300]}
    results.update(exchange_status.sync_once())
    print(json.dumps({'storage':mode(),'elapsed_s':round(time.time()-started,1),'results':results},ensure_ascii=False),flush=True)
    return 0 if any(r['ok'] for r in results.values()) else 1

if __name__=='__main__':sys.exit(main())
