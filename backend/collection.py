"""Offline source pack is explicit. No arbitrary user URL fetching / SSRF."""
import hashlib,json,threading
from filelock import FileLock
from .config import DATA
from .catalog import item_text
from .llm import available,structured,Keywords,Selection
from .prompts import KEYWORDS,SELECT
CACHE=DATA/'query-cache.json'
lock=threading.RLock()

def candidates(item):
    own=dict(id='own-'+item['id'],title=item['name']+' 거래소 메타데이터',body=item_text(item),source=item['source'],source_type='거래소 메타데이터',own=True)
    pack=json.loads((DATA/'documents.json').read_text(encoding="utf-8")) if (DATA/'documents.json').exists() else []
    return [own]+[d for d in pack if not d.get('symbols') or item['symbol'] in d['symbols']]

def collect(item,question):
    docs=candidates(item)
    # Versioned cache invalidates when source body changes; own document is unconditional.
    version=hashlib.sha256(json.dumps(docs,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    key=hashlib.sha256((item['id']+question.strip().lower()+version+str(available())+'selector-v2').encode()).hexdigest()
    with lock, FileLock(str(CACHE)+'.lock'):
        cache=json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        if key in cache:return cache[key]|{'cache_hit':True}
        keywords=[item['name'],item['symbol'],question]
        selected=docs
        if available():
            keywords=structured(KEYWORDS,json.dumps({'item':item,'question':question},ensure_ascii=False),Keywords).keywords
            keywords=list(dict.fromkeys([item['name'],item['symbol']]+keywords))
            choice=structured(SELECT,json.dumps({'question':question,'candidates':[{**{k:d.get(k) for k in ['id','title','own']},'summary':d['body'][:1800]} for d in docs]},ensure_ascii=False),Selection)
            selected=[d for d in docs if d.get('own') or d['id'] in choice.selected]
        result={'keywords':keywords,'documents':selected,'cache_hit':False,'selection_mode':'llm' if available() else 'offline-pack-all'}
        cache[key]=result
        tmp=CACHE.with_suffix('.tmp');tmp.write_text(json.dumps(cache,ensure_ascii=False),encoding="utf-8");tmp.replace(CACHE)
        return result
