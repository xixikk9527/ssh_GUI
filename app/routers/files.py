import os
import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from io import BytesIO
from app.core.ssh_manager import manager
from app.models import FileSaveRequest

router = APIRouter()

@router.get("/api/files/list")
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

@router.get("/api/files/content")
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

@router.get("/api/files/search")
async def search_files(session_id: str, path: str, query: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Use SSH exec_command 'find' instead of SFTP recursive (TOO SLOW)
    client = session["client"]
    # sftp = session["sftp"] # Used for is_dir check if needed, or we can parse find output
    
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

@router.post("/api/files/save")
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

@router.post("/api/files/upload")
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

@router.get("/api/files/download")
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
