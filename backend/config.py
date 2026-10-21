import os
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
DATA=ROOT/'data'
CHUNK_SIZE=int(os.getenv('CHUNK_SIZE','800'))
CHUNK_OVERLAP=int(os.getenv('CHUNK_OVERLAP','120'))
TOP_K=int(os.getenv('TOP_K','5'))
MODEL=os.getenv('CHAT_MODEL','gpt-4.1-mini')
EMBED_MODEL=os.getenv('EMBED_MODEL','text-embedding-3-small')
DB_PATH=os.getenv('CHROMA_PATH',str(DATA/'chroma'))
if not 0<=CHUNK_OVERLAP<CHUNK_SIZE: raise ValueError('Invalid chunk configuration')
