import os
import uuid
import json
import aiofiles
import pandas as pd
from io import BytesIO
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from app.models import JsonParseRequest, ExcelGenerateRequest, DiffRunRequest

router = APIRouter()

# Note: Using a temp directory inside app structure might be cleaner, 
# but let's stick to the relative path logic or use a fixed temp path.
# Since we are in app/routers/doc.py, __file__ is deeper.
# Let's use a standard temp location or keep it relative to project root.
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMP_DIR = os.path.join(base_dir, "temp_doc")
os.makedirs(TEMP_DIR, exist_ok=True)

@router.post("/api/doc/json/parse")
async def parse_json(req: JsonParseRequest):
    try:
        content = req.content.strip()
        data = []
        
        # Attempt 1: Standard JSON Parse
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                data = [parsed]
            elif isinstance(parsed, list):
                data = parsed
            else:
                raise ValueError("Parsed JSON is neither list nor dict")
        except json.JSONDecodeError:
            # Attempt 2: JSON Lines (NDJSON) Parse
            # Try splitting by lines and parsing each line
            lines = content.splitlines()
            valid_lines = []
            for line in lines:
                line = line.strip()
                if not line: continue
                try:
                    valid_lines.append(json.loads(line))
                except:
                    pass # Ignore invalid lines or re-raise later if empty
            
            if valid_lines:
                data = valid_lines
            else:
                raise ValueError("Invalid JSON format. Please provide a JSON Array, Object, or JSON Lines.")

        if not data:
             raise ValueError("No valid JSON data found")

        # Use json_normalize to flatten nested structures (e.g. {"a": {"b": 1}} -> col "a.b")
        df = pd.json_normalize(data)
        
        # Handle NaN/None for JSON serialization
        df = df.where(pd.notnull(df), None)
        
        return {
            "headers": list(df.columns),
            "rows": df.to_dict(orient='records'),
            "total_count": len(df)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/doc/excel/generate")
async def generate_excel(req: ExcelGenerateRequest):
    try:
        # Reconstruct DataFrame with specific column order
        df = pd.DataFrame(req.rows)
        # Add missing columns if any row didn't have it (though req.rows usually complete)
        # and Reorder
        for col in req.headers:
            if col not in df.columns:
                df[col] = None
        df = df[req.headers]
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        
        return StreamingResponse(
            output, 
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": "attachment; filename=converted.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.concurrency import run_in_threadpool

def read_file_to_df(path, sheet_name=None, nrows=None):
    print(f"DEBUG: Reading file {path}, sheet={sheet_name}, nrows={nrows}")
    ext = os.path.splitext(path)[1].lower()
    df = None
    try:
        if ext == '.csv':
            try:
                df = pd.read_csv(path, nrows=nrows, encoding='utf-8')
            except UnicodeDecodeError:
                print("DEBUG: UTF-8 failed, trying GBK")
                df = pd.read_csv(path, nrows=nrows, encoding='gbk')
        elif ext == '.xls':
            df = pd.read_excel(path, sheet_name=sheet_name, engine='xlrd', nrows=nrows)
        else:
            df = pd.read_excel(path, sheet_name=sheet_name, engine='openpyxl', nrows=nrows)
        
        # Clean headers: Convert to string and strip whitespace
        df.columns = df.columns.astype(str).str.strip()
        print(f"DEBUG: Read success. Columns: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"DEBUG: Read failed: {e}")
        import traceback
        traceback.print_exc()
        raise ValueError(f"读取文件失败 ({os.path.basename(path)}): {str(e)}")

@router.post("/api/doc/excel/upload")
async def upload_excel_doc(file: UploadFile = File(...)):
    try:
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1].lower()
        file_path = os.path.join(TEMP_DIR, f"{file_id}{ext}")
        print(f"Uploading file to: {file_path}")
        
        # Optimize upload with chunked write
        async with aiofiles.open(file_path, 'wb') as f:
            while content := await file.read(1024 * 1024): # 1MB chunks
                await f.write(content)
            
        print(f"File saved. Size: {os.path.getsize(file_path)}")

        def process_preview():
            import numpy as np
            sheets = []
            preview = {}
            
            # Use read_file_to_df for consistency, but we need sheet names first for Excel
            if ext == '.csv':
                sheets = ['data']
                df = read_file_to_df(file_path, nrows=50)
                df = df.replace({np.nan: None})
                preview['data'] = {
                    "headers": list(df.columns),
                    "rows": df.to_dict(orient='records')
                }
            elif ext == '.xls':
                with pd.ExcelFile(file_path, engine='xlrd') as xl:
                    sheets = xl.sheet_names
                    for sheet in sheets:
                        df = read_file_to_df(file_path, sheet_name=sheet, nrows=50)
                        df = df.replace({np.nan: None})
                        preview[sheet] = {
                            "headers": list(df.columns),
                            "rows": df.to_dict(orient='records')
                        }
            else:
                with pd.ExcelFile(file_path, engine='openpyxl') as xl:
                    sheets = xl.sheet_names
                    for sheet in sheets:
                        df = read_file_to_df(file_path, sheet_name=sheet, nrows=50)
                        df = df.replace({np.nan: None})
                        preview[sheet] = {
                            "headers": list(df.columns),
                            "rows": df.to_dict(orient='records')
                        }
            return sheets, preview

        sheets, preview = await run_in_threadpool(process_preview)
                
        return {"file_id": file_id, "sheets": sheets, "preview": preview}
    except Exception as e:
        import traceback
        print("Error in upload_excel_doc:")
        traceback.print_exc()
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")

def find_file_by_id(file_id):
    # Find file with matching ID and any extension
    for f in os.listdir(TEMP_DIR):
        if f.startswith(file_id) and not f.startswith("diff_result"):
            # Check exact match excluding extension
            name, _ = os.path.splitext(f)
            if name == file_id:
                return os.path.join(TEMP_DIR, f)
    return None

@router.post("/api/doc/diff/run")
async def run_diff(req: DiffRunRequest):
    try:
        print(f"DEBUG: run_diff started. A={req.file_id_a}, B={req.file_id_b}")
        path_a = find_file_by_id(req.file_id_a)
        path_b = find_file_by_id(req.file_id_b)
        print(f"DEBUG: Paths found: A={path_a}, B={path_b}")
        
        if not path_a or not path_b:
            raise HTTPException(status_code=404, detail="文件已过期或不存在")
            
        # Run diff logic in threadpool to avoid blocking
        def process_diff():
            print("DEBUG: process_diff start")
            df_a = read_file_to_df(path_a, req.sheet_a)
            df_b = read_file_to_df(path_b, req.sheet_b)
            print(f"DEBUG: DF Loaded. A shape={df_a.shape}, B shape={df_b.shape}")
            
            equals_conds = [c for c in req.conditions if c.op == 'equals']
            other_conds = [c for c in req.conditions if c.op != 'equals']
            
            print(f"DEBUG: Equals conds: {equals_conds}")
            print(f"DEBUG: Other conds: {other_conds}")

            if not equals_conds:
                 raise ValueError("至少需要一个'等于'条件")
                 
            left_on = [c.col_a for c in equals_conds]
            right_on = [c.col_b for c in equals_conds]
            
            # Ensure merge columns are present and convert to string for robust matching
            for col in left_on:
                if col not in df_a.columns:
                    print(f"DEBUG: ERROR Col {col} not in A columns: {df_a.columns}")
                    raise KeyError(f"源文件(A)中找不到列: {col}")
                df_a[col] = df_a[col].astype(str).str.strip()
                
            for col in right_on:
                if col not in df_b.columns:
                    print(f"DEBUG: ERROR Col {col} not in B columns: {df_b.columns}")
                    raise KeyError(f"目标文件(B)中找不到列: {col}")
                df_b[col] = df_b[col].astype(str).str.strip()
            
            # Inner Merge (Base on equals)
            print("DEBUG: Merging...")
            merged = pd.merge(df_a, df_b, left_on=left_on, right_on=right_on, suffixes=('_A', '_B'))
            print(f"DEBUG: Merge done. Result shape={merged.shape}")
            
            # Apply other conditions (Filter)
            if other_conds:
                for c in other_conds:
                    print(f"DEBUG: Processing condition: {c}")
                    col_a = c.col_a + '_A' if c.col_a in merged.columns and c.col_a + '_A' in merged.columns else c.col_a
                    col_b = c.col_b + '_B' if c.col_b in merged.columns and c.col_b + '_B' in merged.columns else c.col_b
                    
                    # If column name not changed by merge (unique), use original
                    if col_a not in merged.columns and c.col_a in merged.columns: col_a = c.col_a
                    if col_b not in merged.columns and c.col_b in merged.columns: col_b = c.col_b
                    
                    print(f"DEBUG: Mapped cols: {col_a} vs {col_b}")
                    if col_a in merged.columns and col_b in merged.columns:
                        if c.op == 'not_equals':
                            merged = merged[merged[col_a] != merged[col_b]]
                        elif c.op == 'contains':
                            # Ensure string for contains
                            merged = merged[merged[col_a].astype(str).str.contains(merged[col_b].astype(str), na=False)]
                        elif c.op == 'not_contains':
                            merged = merged[~merged[col_a].astype(str).str.contains(merged[col_b].astype(str), na=False)]
                    else:
                         print(f"DEBUG: Warning - Cols not found for condition {c}")

            # Replace NaN for JSON
            import numpy as np
            merged = merged.replace({np.nan: None})
            
            # Save Result as Pickle (Fast!)
            result_id = str(uuid.uuid4())
            result_path = os.path.join(TEMP_DIR, f"diff_result_{result_id}.pkl")
            
            merged.to_pickle(result_path)
                
            # Preview (first 1000 rows)
            preview_df = merged.head(1000)
            
            return {
                "result_id": result_id,
                "total_rows": len(merged),
                "preview": {
                    "headers": list(preview_df.columns),
                    "rows": preview_df.to_dict(orient='records')
                }
            }

        return await run_in_threadpool(process_diff)
        
    except Exception as e:
        import traceback
        print("DEBUG: run_diff exception:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/doc/diff/download/{result_id}")
async def download_diff_result(result_id: str):
    pkl_path = os.path.join(TEMP_DIR, f"diff_result_{result_id}.pkl")
    if not os.path.exists(pkl_path):
        raise HTTPException(status_code=404, detail="结果文件已过期")
    
    # Run export in threadpool
    def export_excel():
        df = pd.read_pickle(pkl_path)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return output

    output = await run_in_threadpool(export_excel)
        
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={"Content-Disposition": "attachment; filename=diff_result.xlsx"}
    )
