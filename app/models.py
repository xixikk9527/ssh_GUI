from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime

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
    mode: str = "intersection"
    remove_duplicates: bool = False

class TaskEvent(BaseModel):
    type: str
    time: float
    x: int = None
    y: int = None
    button: str = None
    pressed: bool = None
    dx: int = None
    dy: int = None
    key: str = None

class AutomationTask(BaseModel):
    id: str
    name: str
    created_at: str
    duration: float
    events: List[TaskEvent]

class TaskCreateRequest(BaseModel):
    name: str = None
    record_mouse_move: bool = False  # 是否记录鼠标移动轨迹

class TaskExecuteRequest(BaseModel):
    speed: float = 1.0  # 播放速度 0.5/1/2/5
    loop_count: int = 1  # 循环次数