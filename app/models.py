from pydantic import BaseModel
from typing import List, Dict, Any

class ConnectionRequest(BaseModel):
    hostname: str
    username: str
    password: str
    port: int = 22

class FileSaveRequest(BaseModel):
    session_id: str
    path: str
    content: str

class JsonParseRequest(BaseModel):
    content: str

class ExcelGenerateRequest(BaseModel):
    headers: List[str]
    rows: List[Dict[str, Any]]

class DiffCondition(BaseModel):
    col_a: str
    op: str
    col_b: str

class DiffRunRequest(BaseModel):
    file_id_a: str
    sheet_a: str
    file_id_b: str
    sheet_b: str
    conditions: List[DiffCondition]
    mode: str = "intersection" # intersection, difference_a, difference_b
