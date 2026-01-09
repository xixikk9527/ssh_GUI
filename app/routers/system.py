import os
import json
import glob
import aiofiles
import asyncio
import threading
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from app.core.ssh_manager import manager
from app.models import ConnectionRequest

router = APIRouter()

HISTORY_FILE = "data/history.json"

# History API
@router.get("/api/history")
async def get_history():
    if os.path.exists(HISTORY_FILE):
        try:
            async with aiofiles.open(HISTORY_FILE, mode='r') as f:
                content = await f.read()
                return json.loads(content)
        except:
            return {}
    return {}

@router.post("/api/history")
async def save_history(data: ConnectionRequest):
    os.makedirs("data", exist_ok=True)
    async with aiofiles.open(HISTORY_FILE, mode='w') as f:
        await f.write(json.dumps(data.dict()))
    return {"status": "success"}

# Command Config API
@router.get("/api/config/commands")
async def get_commands():
    commands = []
    # 获取 config 目录的绝对路径，确保在任何启动方式下都能找到
    # Note: We need to go up two levels from app/routers/system.py to reach root, then config
    # But __file__ here is inside app/routers
    # Root is ../../
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_dir = os.path.join(base_dir, "config")
    
    if not os.path.exists(config_dir):
        print(f"Config directory not found: {config_dir}")
        return []

    json_files = glob.glob(os.path.join(config_dir, "*.json"))
    print(f"Loading commands from: {config_dir}, Found: {len(json_files)} files")
    
    for file_path in json_files:
        try:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
                if isinstance(data, list):
                    commands.extend(data)
                elif isinstance(data, dict):
                    # Handle Dictionary structure: {"Category": [{"name": "...", "command": "..."}]}
                    for category, items in data.items():
                        if isinstance(items, list):
                            for item in items:
                                # Normalize fields
                                normalized_item = {
                                    "category": category,
                                    "command": item.get("command", ""),
                                    "description": item.get("description", item.get("name", ""))
                                }
                                commands.append(normalized_item)
                else:
                    print(f"Warning: {file_path} does not contain a list or dict")
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    return commands

@router.post("/api/connect")
async def connect_ssh(data: ConnectionRequest):
    session_id = manager.create_session(data.hostname, data.username, data.password, data.port)
    if session_id:
        return {"status": "success", "session_id": session_id}
    else:
        raise HTTPException(status_code=400, detail="Connection failed")

@router.websocket("/ws/ssh/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = manager.get_session(session_id)
    
    if not session:
        await websocket.close(code=1008)
        return

    client = session["client"]
    try:
        # Open a new channel for the terminal
        # Invoke shell with a default size, will be resized by frontend immediately
        channel = client.invoke_shell(term='xterm', width=80, height=24)
    except Exception as e:
        await websocket.send_text(f"Error opening shell: {str(e)}")
        await websocket.close()
        return

    # Queue for passing data from thread to async loop
    output_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def ssh_reader():
        """Thread function to read from SSH channel"""
        try:
            while not channel.closed:
                # Blocking read is safe in a separate thread
                data = channel.recv(4096)
                if not data:
                    break
                asyncio.run_coroutine_threadsafe(output_queue.put(data), loop)
        except Exception as e:
            print(f"SSH Reader Error: {e}")
        finally:
            asyncio.run_coroutine_threadsafe(output_queue.put(None), loop)

    # Start SSH reader thread
    reader_thread = threading.Thread(target=ssh_reader, daemon=True)
    reader_thread.start()

    async def forward_output():
        """Task to forward data from queue to WebSocket"""
        try:
            while True:
                data = await output_queue.get()
                if data is None: # EOF signal
                    break
                await websocket.send_text(data.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"WebSocket Send Error: {e}")
        finally:
            try:
                await websocket.close()
            except:
                pass

    output_task = asyncio.create_task(forward_output())

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if 'type' in msg and msg['type'] == 'resize':
                    channel.resize_pty(width=msg['cols'], height=msg['rows'])
                    continue
            except json.JSONDecodeError:
                pass
            
            # Send data to SSH channel
            channel.send(data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket Receive Error: {e}")
    finally:
        output_task.cancel()
        # channel.close() # Optional: closing channel might be handled by thread logic
