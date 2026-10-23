"""Notice-only storage adapter. SQL strings are application-owned constants."""
import os,sqlite3

class Connection:
    def __init__(self,connection,postgres=False):
        self.raw=connection
        self.postgres=postgres
    def execute(self,sql,params=()):
        return self.raw.execute(sql.replace('?', '%s') if self.postgres else sql,params)
    def __enter__(self):return self
    def __exit__(self,kind,value,traceback):
        try:
            if kind:self.raw.rollback()
            else:self.raw.commit()
        finally:self.raw.close()

def connect(path):
    url=os.getenv('DATABASE_URL')
    if url:
        import psycopg
        # External storage failures must not silently create a new local database.
        try:return Connection(psycopg.connect(url,connect_timeout=10),True)
        except psycopg.Error:raise RuntimeError('공지 PostgreSQL 연결 실패. 서버 DB 설정을 확인하세요.') from None
    path.parent.mkdir(parents=True,exist_ok=True)
    return Connection(sqlite3.connect(path,timeout=15))

def mode():return 'postgresql' if os.getenv('DATABASE_URL') else 'sqlite'
