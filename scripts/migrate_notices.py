"""Copy a stopped collector's local SQLite records into configured PostgreSQL.
Run: python -m scripts.migrate_notices
No deletion; existing destination records are preserved.
"""
import os,sqlite3
from backend.notices import DB
from backend.bithumb_notices import connect

def main():
    if not os.getenv('DATABASE_URL'):raise SystemExit('DATABASE_URL이 필요합니다.')
    if not DB.exists():raise SystemExit('이전할 SQLite 파일이 없습니다.')
    # Backup API gives a consistent source snapshot, with no source writes.
    source=sqlite3.connect('file:'+DB.as_posix()+'?mode=ro',uri=True)
    snapshot=sqlite3.connect(':memory:')
    try:source.backup(snapshot)
    finally:source.close()
    tables={r[0] for r in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    counts={}
    try:
        with connect() as target:
            for table in ('notices','bithumb_notices','notice_sync_state'):
                if table not in tables:continue
                rows=snapshot.execute('SELECT * FROM '+table).fetchall()
                placeholders=','.join('?' for _ in (rows[0] if rows else []))
                count=0
                for row in rows:
                    count+=target.execute('INSERT INTO '+table+' VALUES ('+placeholders+') ON CONFLICT DO NOTHING',row).rowcount
                counts[table]=count
    finally:snapshot.close()
    print({'inserted':counts,'existing_destination_records':'preserved'})
if __name__=='__main__':main()
