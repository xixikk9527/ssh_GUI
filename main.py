import uvicorn
import paramiko
import asyncio
import uuid
import json
import os
import glob
import aiofiles
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Optional, List
from io import BytesIO

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# Session Storage
# session_id -> {"client": SSHClient, "sftp": SFTPClient}
sessions: Dict[str, Dict] = {}
HISTORY_FILE = "data/history.json"

class ConnectionRequest(BaseModel):
    hostname: str
    username: str
    password: str
    port: int = 22

class FileSaveRequest(BaseModel):
    session_id: str
    path: str
    content: str

# ... SSHManager and connection APIs ...

# History API
@app.get("/api/history")
async def get_history():
    if os.path.exists(HISTORY_FILE):
        try:
            async with aiofiles.open(HISTORY_FILE, mode='r') as f:
                content = await f.read()
                return json.loads(content)
        except:
            return {}
    return {}

@app.post("/api/history")
async def save_history(data: ConnectionRequest):
    os.makedirs("data", exist_ok=True)
    async with aiofiles.open(HISTORY_FILE, mode='w') as f:
        await f.write(json.dumps(data.dict()))
    return {"status": "success"}

# Command Config API
@app.get("/api/config/commands")
async def get_commands():
    commands = []
    # 获取 config 目录的绝对路径，确保在任何启动方式下都能找到
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    
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

class SSHManager:
    def __init__(self):
        pass

    def create_session(self, host, user, password, port=22):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=host, port=port, username=user, password=password)
            sftp = client.open_sftp()
            session_id = str(uuid.uuid4())
            sessions[session_id] = {
                "client": client,
                "sftp": sftp,
                "host": host,
                "user": user
            }
            return session_id
        except Exception as e:
            print(f"Connection failed: {e}")
            return None

    def get_session(self, session_id):
        return sessions.get(session_id)

    def close_session(self, session_id):
        if session_id in sessions:
            try:
                sessions[session_id]["sftp"].close()
                sessions[session_id]["client"].close()
            except:
                pass
            del sessions[session_id]

manager = SSHManager()

@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/connect")
async def connect_ssh(data: ConnectionRequest):
    session_id = manager.create_session(data.hostname, data.username, data.password, data.port)
    if session_id:
        return {"status": "success", "session_id": session_id}
    else:
        raise HTTPException(status_code=400, detail="Connection failed")

import threading

# ... (imports)

@app.websocket("/ws/ssh/{session_id}")
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


# SFTP APIs

@app.get("/api/files/list")
async def list_files(session_id: str, path: str = "."):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    sftp = session["sftp"]
    try:
        # Resolve path
        if path == ".":
            path = sftp.normalize(".")
        else:
            try:
                path = sftp.normalize(path)
            except:
                pass # Keep original path if normalize fails
            
        file_list = []
        attrs = sftp.listdir_attr(path)
        for attr in attrs:
            file_list.append({
                "name": attr.filename,
                "is_dir": attr.st_mode is not None and (attr.st_mode & 0o40000),
                "size": attr.st_size,
                "mtime": attr.st_mtime
            })
        
        # Sort: directories first, then files
        file_list.sort(key=lambda x: (not x["is_dir"], x["name"]))
        
        return {"current_path": path, "files": file_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/content")
async def get_file_content(session_id: str, path: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    sftp = session["sftp"]
    try:
        # Check file size
        attr = sftp.stat(path)
        if attr.st_size > 1024 * 1024: # 1MB limit
            raise HTTPException(status_code=400, detail="File too large to preview (limit 1MB). Please download it.")

        with sftp.open(path, 'r') as f:
            content = f.read().decode('utf-8') # Limit to text files for now
        return {"content": content}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Binary file cannot be previewed as text")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/search")
async def search_files(session_id: str, path: str, query: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Use SSH exec_command 'find' instead of SFTP recursive (TOO SLOW)
    client = session["client"]
    sftp = session["sftp"] # Used for is_dir check if needed, or we can parse find output
    
    # Secure query to prevent injection (basic)
    import shlex
    safe_query = shlex.quote(query)
    
    # Construct find command
    # find / -name "*query*" -not -path "/proc/*" ... | head -n 1000
    # Use -iname for case insensitive
    # Exclude heavy directories
    excludes = "-not -path '/proc/*' -not -path '/sys/*' -not -path '/dev/*' -not -path '/run/*' -not -path '/tmp/*'"
    
    # If query is very short, limit depth? No, user wants global.
    # Just limit output lines.
    
    # We want to know if it's a directory. 
    # find command can print type: find ... -printf "%p|%y\n" -> /path/to/file|f or /path/to/dir|d
    
    cmd = f"find / {excludes} -iname '*{safe_query}*' -printf '%p|%y\\n' 2>/dev/null | head -n 500"
    
    if query == "/" or query == "\\":
         # Special case: just list root
         cmd = "find / -maxdepth 1 -printf '%p|%y\\n' 2>/dev/null | head -n 500"

    print(f"Executing search command: {cmd}")

    results = []
    
    def run_find():
        try:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
            output = stdout.read().decode('utf-8', errors='ignore')
            return output
        except Exception as e:
            print(f"Find command failed: {e}")
            return ""

    output = await asyncio.to_thread(run_find)
    
    lines = output.strip().split('\n')
    for line in lines:
        if not line: continue
        try:
            parts = line.rsplit('|', 1)
            if len(parts) != 2: continue
            
            full_path = parts[0]
            type_char = parts[1]
            
            filename = os.path.basename(full_path)
            if not filename: filename = full_path # Root case
            
            results.append({
                "name": filename,
                "path": full_path,
                "is_dir": (type_char == 'd'),
                "parent": os.path.dirname(full_path)
            })
        except:
            pass

    return results

@app.post("/api/files/save")
async def save_file(req: FileSaveRequest):
    session = manager.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    sftp = session["sftp"]
    try:
        with sftp.open(req.path, 'w') as f:
            f.write(req.content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/upload")
async def upload_file(session_id: str = Form(...), path: str = Form(...), file: UploadFile = File(...)):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    sftp = session["sftp"]
    try:
        # Determine remote path
        remote_file_path = os.path.join(path, file.filename).replace("\\", "/")
        
        # Read content from upload
        content = await file.read()
        
        with sftp.open(remote_file_path, 'wb') as f:
            f.write(content)
            
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/download")
async def download_file(session_id: str, path: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    sftp = session["sftp"]
    try:
        # Read file into memory (warning: large files issue)
        # For better implementation, use a generator/iterator
        
        file_obj = BytesIO()
        sftp.getfo(path, file_obj)
        file_obj.seek(0)
        
        filename = os.path.basename(path)
        return StreamingResponse(
            file_obj, 
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
