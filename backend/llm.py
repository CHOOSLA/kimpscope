import os
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from .config import MODEL,ROOT
from dotenv import load_dotenv
class Keywords(BaseModel): keywords:list[str]=Field(max_length=5)
class Selection(BaseModel): selected:list[str]
class Conditions(BaseModel):
    symbol:str|None=None
    warning:bool|None=None
    name_contains:str|None=None

def available():
    load_dotenv(ROOT/'.env',override=True)
    return bool(os.getenv('OPENAI_API_KEY'))
def model():return ChatOpenAI(model=MODEL,base_url=os.getenv('OPENAI_BASE_URL') or None,temperature=0,timeout=40,max_retries=2)
def structured(prompt,payload,schema):
    return model().with_structured_output(schema).invoke([('system',prompt),('human',payload)])
