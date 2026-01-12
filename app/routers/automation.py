"""
简化的自动化API
"""
import os
import json
import uuid
import time
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.models import TaskEvent, AutomationTask, TaskCreateRequest, TaskExecuteRequest

router = APIRouter()

# 任务存储目录
TASKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "automation_tasks")
os.makedirs(TASKS_DIR, exist_ok=True)

# 全局录制状态
_recording_state = {
    "is_recording": False,
    "task_id": None,
    "events": [],
    "start_time": None,
    "recorder": None
}

# 全局播放器实例
_player = None

@router.get("/api/automation/tasks")
async def list_tasks():
    """获取所有任务列表"""
    tasks = []
    if os.path.exists(TASKS_DIR):
        for filename in os.listdir(TASKS_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(TASKS_DIR, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        task = json.load(f)
                        tasks.append({
                            "id": task.get("id"),
                            "name": task.get("name"),
                            "created_at": task.get("created_at"),
                            "duration": task.get("duration"),
                            "event_count": len(task.get("events", []))
                        })
                except:
                    pass
    
    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"tasks": tasks}

@router.get("/api/automation/task/{task_id}")
async def get_task(task_id: str):
    """获取特定任务详情"""
    filepath = os.path.join(TASKS_DIR, f"{task_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        task = json.load(f)
    return task

@router.post("/api/automation/start-recording")
async def start_recording(req: TaskCreateRequest = None):
    """开始录制"""
    global _recording_state
    
    if _recording_state["is_recording"]:
        raise HTTPException(status_code=400, detail="已经在录制中")
    
    # 生成任务ID
    task_id = str(uuid.uuid4())[:8]
    
    # 是否记录鼠标移动轨迹
    record_mouse_move = req.record_mouse_move if req else False
    
    # 导入录制器（每次创建新实例，避免状态残留）
    from app.utils.simple_recorder import SimpleRecorder
    recorder = SimpleRecorder()
    
    # 初始化录制状态
    _recording_state = {
        "is_recording": True,
        "task_id": task_id,
        "events": [],
        "start_time": time.time(),
        "recorder": recorder,
        "record_mouse_move": record_mouse_move
    }
    
    # 启动录制（在后台线程中启动监听器）
    def run_recording():
        recorder.start(record_mouse_move=record_mouse_move)
        # 注意：start() 会启动监听器但不会阻塞
    
    threading.Thread(target=run_recording, daemon=True).start()
    
    return {
        "status": "recording",
        "task_id": task_id,
        "record_mouse_move": record_mouse_move
    }

@router.post("/api/automation/stop-recording")
async def stop_recording():
    """停止录制并保存任务"""
    global _recording_state
    
    recorder = _recording_state.get("recorder")
    task_id = _recording_state.get("task_id")
    
    if not task_id:
        raise HTTPException(status_code=400, detail="没有正在进行的录制")
    
    # 停止录制器
    events = []
    if recorder:
        if recorder.is_recording:
            result = recorder.stop()
            if result:
                events = result.get("events", [])
        else:
            # 录制器已停止（可能是ESC键停止的）
            events = recorder.events
    
    # 计算时长
    duration = 0
    if _recording_state["start_time"]:
        duration = time.time() - _recording_state["start_time"]
    
    # 保存任务
    task = {
        "id": task_id,
        "name": f"任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.now().isoformat(),
        "duration": round(duration, 2),
        "events": events
    }
    
    filepath = os.path.join(TASKS_DIR, f"{task['id']}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    
    # 重置录制状态
    _recording_state = {
        "is_recording": False,
        "task_id": None,
        "events": [],
        "start_time": None,
        "recorder": None
    }
    
    return {
        "status": "saved",
        "task_id": task["id"],
        "task": task
    }

@router.get("/api/automation/recording-status")
async def get_recording_status():
    """获取录制状态 - 用于前端轮询"""
    global _recording_state
    
    recorder = _recording_state.get("recorder")
    task_id = _recording_state.get("task_id")
    
    # 检查录制器是否已停止（ESC键停止）
    if recorder and not recorder.is_recording and task_id:
        # ESC键停止了录制，自动保存任务
        events = recorder.events
        
        # 计算时长
        duration = 0
        if _recording_state["start_time"]:
            duration = time.time() - _recording_state["start_time"]
        
        # 保存任务
        task = {
            "id": task_id,
            "name": f"任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "created_at": datetime.now().isoformat(),
            "duration": round(duration, 2),
            "events": events
        }
        
        filepath = os.path.join(TASKS_DIR, f"{task['id']}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        
        # 保存任务信息
        saved_task = task.copy()
        
        # 重置录制状态
        _recording_state = {
            "is_recording": False,
            "task_id": None,
            "events": [],
            "start_time": None,
            "recorder": None
        }
        
        return {
            "is_recording": False,
            "task_id": None,
            "event_count": len(events),
            "just_saved": True,
            "saved_task": saved_task
        }
    
    # 正常返回当前状态
    event_count = len(recorder.events) if recorder else 0
    is_recording = recorder.is_recording if recorder else False
    
    return {
        "is_recording": is_recording,
        "task_id": task_id if is_recording else None,
        "event_count": event_count,
        "just_saved": False
    }

@router.post("/api/automation/task/{task_id}/execute")
async def execute_task(task_id: str, req: TaskExecuteRequest = None):
    """执行任务"""
    global _player
    
    # 读取任务文件
    filepath = os.path.join(TASKS_DIR, f"{task_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        task = json.load(f)
    
    # 导入播放器（每次创建新实例）
    from app.utils.simple_player import SimplePlayer
    _player = SimplePlayer()
    
    # 获取参数
    speed = req.speed if req else 1.0
    loop_count = req.loop_count if req else 1
    
    # 开始播放
    _player.play(task["events"], speed, loop_count)
    
    return {
        "status": "executing",
        "task_id": task_id,
        "event_count": len(task["events"]),
        "speed": speed,
        "loop_count": loop_count
    }

@router.put("/api/automation/task/{task_id}/rename")
async def rename_task(task_id: str, req: TaskCreateRequest):
    """重命名任务"""
    filepath = os.path.join(TASKS_DIR, f"{task_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        task = json.load(f)
    
    task["name"] = req.name
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    
    return {
        "status": "renamed",
        "task_id": task_id,
        "name": req.name
    }

@router.put("/api/automation/task/{task_id}")
async def update_task(task_id: str, task_data: dict):
    """更新任务（完整更新）"""
    filepath = os.path.join(TASKS_DIR, f"{task_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 保留原有的 id 和 created_at
    with open(filepath, 'r', encoding='utf-8') as f:
        old_task = json.load(f)
    
    # 更新任务数据
    task = {
        "id": task_id,
        "name": task_data.get("name", old_task.get("name")),
        "created_at": old_task.get("created_at"),
        "duration": task_data.get("duration", old_task.get("duration")),
        "events": task_data.get("events", [])
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    
    return {
        "status": "updated",
        "task_id": task_id
    }

@router.delete("/api/automation/task/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    filepath = os.path.join(TASKS_DIR, f"{task_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    os.remove(filepath)
    return {
        "status": "deleted",
        "task_id": task_id
    }