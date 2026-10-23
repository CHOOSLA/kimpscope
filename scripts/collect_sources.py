"""허용 목록의 공식 문서 4건 중 저장소에 없는 것을 받아 저장한다(backend/official_docs.py).

저장 위치는 공지와 같다: DATABASE_URL이 있으면 PostgreSQL, 없으면 data/notices.sqlite3.
실행: python -m scripts.collect_sources
"""
import json,sys
from backend import official_docs

if __name__=='__main__':
    failures=official_docs.fetch_missing()
    print(json.dumps({'stored':len(official_docs.stored()),'failures':failures},ensure_ascii=False))
    sys.exit(1 if failures and not official_docs.stored() else 0)
