import hashlib,threading,os
import chromadb
from filelock import FileLock
import numpy as np
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .config import DB_PATH,EMBED_MODEL,CHUNK_SIZE,CHUNK_OVERLAP
from .catalog import items,item_text
lock=threading.RLock()
_encoder=None
_client=None

def client():
    global _client
    if _client is None:_client=chromadb.PersistentClient(path=DB_PATH)
    return _client

def collection(name):return client().get_or_create_collection(name,metadata={'hnsw:space':'cosine'})
def embed(texts):
    global _encoder
    with lock:
        if _encoder is None:_encoder=OpenAIEmbeddings(model=EMBED_MODEL,base_url=os.getenv('OPENAI_BASE_URL') or None,max_retries=2,request_timeout=40,check_embedding_ctx_length=False)
        return _encoder.embed_documents(texts)

def index_metadata():
    data=items();texts=[item_text(x) for x in data]
    with lock, FileLock(DB_PATH+'.index.lock'):collection('items').upsert(ids=[x['id'] for x in data],documents=texts,embeddings=embed(texts),metadatas=data)
    return collection('items').count()

def index_documents(item,docs):
    splitter=RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE,chunk_overlap=CHUNK_OVERLAP)
    with lock, FileLock(DB_PATH+'.index.lock'):
        col=collection('documents')
        for d in docs:
            group=item['id']+':'+d['id'];fingerprint=hashlib.sha256((d['body']+str(CHUNK_SIZE)+str(CHUNK_OVERLAP)).encode()).hexdigest()
            old=col.get(where={'group':group})
            if old['metadatas'] and all(m.get('fingerprint')==fingerprint for m in old['metadatas']):continue
            chunks=splitter.split_text(d['body']) or [d['title']]
            ids=[group+':'+str(i) for i in range(len(chunks))]
            metas=[dict(item_id=item['id'],group=group,fingerprint=fingerprint,title=d['title'],source=d['source'],source_type=d['source_type'],own=bool(d.get('own')),chunk_index=i) for i in range(len(chunks))]
            col.upsert(ids=ids,documents=chunks,metadatas=metas,embeddings=embed(chunks))
            obsolete=list(set(old['ids'])-set(ids))
            if obsolete:col.delete(ids=obsolete)
        return col.count()

def retrieve(item,question,k=5,mode='similarity'):
    base=collection('items').get(ids=[item['id']])
    if not base['ids']:raise ValueError('NO_INDEX')
    result=[dict(id=item['id'],text=base['documents'][0],title=item['name']+' 메タ데이터',source=item['source'],source_type='항목 메타데이터',score=1.0)]
    col=collection('documents')
    total=len(col.get(where={'item_id':item['id']})['ids'])
    if total:
        q=embed([question])[0]
        found=col.query(query_embeddings=[q],where={'item_id':item['id']},n_results=min(max(k*3,10),total),include=['documents','metadatas','distances','embeddings'])
        vectors=np.array(found['embeddings'][0]);scores=1-np.array(found['distances'][0]);chosen=[]
        remaining=list(range(len(scores)))
        while remaining and len(chosen)<k:
            index=max(remaining,key=lambda i:float(scores[i]) if mode!='mmr' or not chosen else .7*float(scores[i])-.3*max(float(np.dot(vectors[i],vectors[j])) for j in chosen))
            chosen.append(index);remaining.remove(index)
        seen={result[0]['text']}
        for i in chosen:
            text=found['documents'][0][i];meta=found['metadatas'][0][i]
            if text in seen:continue
            seen.add(text);result.append(dict(id=found['ids'][0][i],text=text,score=float(scores[i]),**meta))
    return result
