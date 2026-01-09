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

import io

# Global Cache to avoid saving files to disk
FILE_CACHE = {} # {uuid: {'content': bytes, 'ext': str, 'filename': str}}
DATAFRAME_CACHE = {} # {uuid: {sheet_name: DataFrame}}

def read_file_to_df(file_source, ext, sheet_name=None, nrows=None):
    print(f"DEBUG: Reading file (in-memory), ext={ext}, sheet={sheet_name}, nrows={nrows}")
    df = None
    try:
        # Check if file_source is bytes, convert to BytesIO for pandas
        if isinstance(file_source, bytes):
            file_source = io.BytesIO(file_source)
        
        # Ensure we are at the start of the stream
        file_source.seek(0)
            
        if ext == '.csv':
            try:
                df = pd.read_csv(file_source, nrows=nrows, encoding='utf-8')
            except UnicodeDecodeError:
                print("DEBUG: UTF-8 failed, trying GBK")
                file_source.seek(0)
                df = pd.read_csv(file_source, nrows=nrows, encoding='gbk')
        elif ext == '.xls':
            df = pd.read_excel(file_source, sheet_name=sheet_name, engine='xlrd', nrows=nrows)
        else:
            df = pd.read_excel(file_source, sheet_name=sheet_name, engine='openpyxl', nrows=nrows)
        
        # Clean headers: Convert to string and strip whitespace
        df.columns = df.columns.astype(str).str.strip()
        print(f"DEBUG: Read success. Columns: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"DEBUG: Read failed: {e}")
        import traceback
        traceback.print_exc()
        raise ValueError(f"读取文件失败: {str(e)}")

@router.post("/api/doc/excel/upload")
async def upload_excel_doc(file: UploadFile = File(...)):
    try:
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1].lower()
        print(f"Uploading file (to memory): {file.filename}")
        
        # Read content into memory
        content = await file.read()
        FILE_CACHE[file_id] = {
            'content': content,
            'ext': ext,
            'filename': file.filename
        }
        print(f"File saved to memory. Size: {len(content)}")

        def process_upload():
            import numpy as np
            sheets = []
            preview = {}
            dfs = {}
            
            # Use read_file_to_df for consistency
            if ext == '.csv':
                sheets = ['data']
                # Read FULL file to support pagination and total count
                df = read_file_to_df(content, ext) 
                print(f"DEBUG: Parsed CSV. Rows: {len(df)}")
                dfs['data'] = df
                
                # Create Preview (top 50)
                preview_df = df.head(50).replace({np.nan: None})
                preview['data'] = {
                    "headers": list(df.columns),
                    "rows": preview_df.to_dict(orient='records'),
                    "total_rows": len(df)
                }
            elif ext == '.xls':
                with pd.ExcelFile(io.BytesIO(content), engine='xlrd') as xl:
                    sheets = xl.sheet_names
                    print(f"DEBUG: Found sheets in XLS: {sheets}")
                    for sheet in sheets:
                        # Read FULL file
                        df = read_file_to_df(content, ext, sheet_name=sheet)
                        print(f"DEBUG: Parsed XLS sheet '{sheet}'. Rows: {len(df)}")
                        dfs[sheet] = df
                        
                        preview_df = df.head(50).replace({np.nan: None})
                        preview[sheet] = {
                            "headers": list(df.columns),
                            "rows": preview_df.to_dict(orient='records'),
                            "total_rows": len(df)
                        }
            else:
                with pd.ExcelFile(io.BytesIO(content), engine='openpyxl') as xl:
                    sheets = xl.sheet_names
                    print(f"DEBUG: Found sheets in XLSX: {sheets}")
                    for sheet in sheets:
                        # Read FULL file
                        df = read_file_to_df(content, ext, sheet_name=sheet)
                        print(f"DEBUG: Parsed XLSX sheet '{sheet}'. Rows: {len(df)}")
                        dfs[sheet] = df
                        
                        preview_df = df.head(50).replace({np.nan: None})
                        preview[sheet] = {
                            "headers": list(df.columns),
                            "rows": preview_df.to_dict(orient='records'),
                            "total_rows": len(df)
                        }
            
            # Cache the parsed DataFrames
            DATAFRAME_CACHE[file_id] = dfs
            print(f"DEBUG: Cache updated for {file_id}. Sheets: {list(dfs.keys())}")
            return sheets, preview

        sheets, preview = await run_in_threadpool(process_upload)
                
        return {"file_id": file_id, "sheets": sheets, "preview": preview}
    except Exception as e:
        import traceback
        print("Error in upload_excel_doc:")
        traceback.print_exc()
        # Cleanup if needed (remove from cache)
        if 'file_id' in locals() and file_id in FILE_CACHE:
            del FILE_CACHE[file_id]
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")

@router.get("/api/doc/file/{file_id}/data")
async def get_file_data(file_id: str, sheet: str, page: int = 1, size: int = 50):
    try:
        print(f"DEBUG: get_file_data. ID={file_id}, Sheet={sheet}, Page={page}, Size={size}")
        
        if file_id not in DATAFRAME_CACHE:
             print(f"DEBUG: ID not in cache. Keys: {list(DATAFRAME_CACHE.keys())}")
             # Try to recover from FILE_CACHE if DataFrame cache cleared?
             # For now, just error.
             raise HTTPException(status_code=404, detail="文件已过期")
        
        dfs = DATAFRAME_CACHE[file_id]
        if sheet not in dfs:
            print(f"DEBUG: Sheet '{sheet}' not in DFS. Sheets: {list(dfs.keys())}")
            raise HTTPException(status_code=404, detail="Sheet not found")
            
        df = dfs[sheet]
        total = len(df)
        start = (page - 1) * size
        end = start + size
        
        print(f"DEBUG: Slicing DF. Total={total}, Start={start}, End={end}")
        
        # Handle slice
        subset = df.iloc[start:end]
        import numpy as np
        subset = subset.replace({np.nan: None})
        
        return {
            "page": page,
            "pageSize": size,
            "total": total,
            "rows": subset.to_dict(orient='records')
        }
    except Exception as e:
        import traceback
        print("DEBUG: get_file_data Error:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/doc/diff/stats")
async def check_diff_stats(req: DiffRunRequest):
    try:
        # Check caches
        if req.file_id_a not in DATAFRAME_CACHE and req.file_id_a not in FILE_CACHE:
             return {"steps": [0] * len(req.conditions), "total": 0}
        if req.file_id_b not in DATAFRAME_CACHE and req.file_id_b not in FILE_CACHE:
             return {"steps": [0] * len(req.conditions), "total": 0}

        def process_stats():
            # Get DFs
            if req.file_id_a in DATAFRAME_CACHE:
                 df_a = DATAFRAME_CACHE[req.file_id_a][req.sheet_a].copy()
            else:
                 file_a = FILE_CACHE[req.file_id_a]
                 df_a = read_file_to_df(file_a['content'], file_a['ext'], req.sheet_a)
            
            if req.file_id_b in DATAFRAME_CACHE:
                 df_b = DATAFRAME_CACHE[req.file_id_b][req.sheet_b].copy()
            else:
                 file_b = FILE_CACHE[req.file_id_b]
                 df_b = read_file_to_df(file_b['content'], file_b['ext'], req.sheet_b)
            
            # Prepare columns for join
            # For stats, we need to process sequentially to give feedback per step
            # But standard merge is "all at once".
            # To support "count after this step", we can do:
            # 1. Start with full cross product? NO, too big.
            # 2. Start with first condition.
            
            # Strategy:
            # - Group conditions by 'equals' vs others? 
            # - Usually 'equals' are primary keys for merge.
            # - If user puts 'contains' as first condition, it implies a cross-join filter? That's heavy.
            # - Let's assume the order in req.conditions is the display order.
            # - We MUST apply all 'equals' conditions first to get the base set.
            # - Then apply filters sequentially?
            
            # Re-evaluating user request: "In the back of current condition show matched data"
            # If Condition 1 is Equals(ID), Condition 2 is NotEquals(Name).
            # Step 1: Merge on ID. Count = 100.
            # Step 2: Filter Name!=Name. Count = 5.
            # User wants to see "100" next to Cond 1, and "5" next to Cond 2.
            
            # Implementation:
            # 1. Identify all 'equals' conditions. These form the base Merge.
            #    If no equals, we can't really do anything efficient (Cross join is dangerous).
            #    Let's assume we MERGE on ALL 'equals' first.
            
            equals_conds = [c for c in req.conditions if c.op == 'equals']
            if not equals_conds:
                return {"steps": [0] * len(req.conditions), "total": 0, "error": "需要至少一个'等于'条件来开始"}

            left_on = [c.col_a for c in equals_conds]
            right_on = [c.col_b for c in equals_conds]
            
            # Pre-process columns
            for col in left_on:
                if col in df_a.columns: df_a[col] = df_a[col].astype(str).str.strip()
            for col in right_on:
                if col in df_b.columns: df_b[col] = df_b[col].astype(str).str.strip()

            # Base Merge
            merged = pd.merge(df_a, df_b, left_on=left_on, right_on=right_on, suffixes=('_A', '_B'))
            base_count = len(merged)
            
            # Now map the counts back to the ordered conditions list
            # Logic:
            # - For 'equals' conditions: They are all applied simultaneously in the merge.
            #   So technically, their "step count" is the base_count. 
            #   (Or should we try to apply them sequentially? merge(c1) -> merge(c1+c2)? That's expensive)
            #   Let's just say for all 'equals' conditions, the count is the base merge count.
            # - For other conditions: Apply them sequentially on `merged` DF.
            
            step_counts = []
            current_df = merged
            
            # We need to track which conditions have been applied
            # But the user sees them in order.
            # If the user order is: [NotEquals, Equals, Contains]
            # This is tricky because we MUST merge on Equals first.
            # So the logical order is always: All Equals -> Then Others.
            # BUT the UI order might be different.
            
            # Compromise: 
            # - Assign `base_count` to all 'equals' rows.
            # - Then apply non-equals filters in their relative order.
            
            # Better Approach for User Experience:
            # The "Count" next to a condition should represent "How many rows satisfy constraints UP TO HERE".
            # If C1 is 'equals', C2 is 'not_equals'.
            # C1 Count = Merge(C1).
            # C2 Count = Merge(C1) + Filter(C2).
            
            # If C1 is 'equals', C2 is 'equals'.
            # C1 Count = Merge(C1).
            # C2 Count = Merge(C1, C2).
            # This requires iterative merging!
            
            # Iterative Merge Optimization:
            # Merge on C1.
            # Merge on C1, C2. (Actually just Filter C2 on previous result if it's also equals?)
            # Yes! Merge(A,B on [K1, K2]) == Merge(A,B on K1).filter(A.K2 == B.K2)
            
            # So:
            # 1. Start with Cross Product? NO.
            # 2. Find the FIRST 'equals' condition. Merge on it.
            #    If the first condition is NOT 'equals', we can't start (unless we wait for an 'equals').
            #    Let's assume valid workflow starts with 'equals' or we skip non-equals until we find one.
            
            # Revised Logic:
            # Iterate through conditions.
            # Maintain `current_df`.
            # If Cond is 'equals':
            #    If `current_df` is None (first merge):
            #        Perform pd.merge(on=Cond).
            #    Else:
            #        Filter `current_df` where col_a == col_b.
            # If Cond is others:
            #    If `current_df` is None:
            #        Skip (Count=0) or Error. (Can't filter before merge).
            #    Else:
            #        Filter `current_df`.
            
            # Handling columns: After first merge, cols get suffixes _A, _B.
            # We need to be careful with column mapping.
            
            df_curr = None
            
            # Pre-calc column presence to avoid key errors during check
            cols_a_map = {c: c for c in df_a.columns}
            cols_b_map = {c: c for c in df_b.columns}
            
            for idx, c in enumerate(req.conditions):
                try:
                    # Resolve column names based on whether we have merged yet
                    # Actually, if we haven't merged, we use df_a/df_b directly?
                    # No, we need to produce a joint set.
                    
                    if c.op == 'equals':
                        if df_curr is None:
                            # First Merge
                            # Clean cols
                            ca, cb = c.col_a, c.col_b
                            if ca in df_a.columns and cb in df_b.columns:
                                df_a[ca] = df_a[ca].astype(str).str.strip()
                                df_b[cb] = df_b[cb].astype(str).str.strip()
                                df_curr = pd.merge(df_a, df_b, left_on=ca, right_on=cb, suffixes=('_A', '_B'))
                                step_counts.append(len(df_curr))
                            else:
                                step_counts.append(0)
                        else:
                            # Already merged, just filter for equality
                            # Need to find the correct column names in df_curr
                            # When merging, pandas adds suffixes if overlap.
                            # We need a robust way to know which col is which.
                            # Hack: Re-merge is expensive. 
                            # Filter is: df_curr[ca_mapped] == df_curr[cb_mapped]
                            
                            # Mapping logic:
                            # If name unique, it's `name`.
                            # If collision, it's `name_A` / `name_B`.
                            
                            # BUT, we don't know if collision happened without checking.
                            # Let's rely on checking `col` vs `col_A`.
                            
                            ca = c.col_a
                            cb = c.col_b
                            
                            real_ca = ca
                            if ca not in df_curr.columns and f"{ca}_A" in df_curr.columns: real_ca = f"{ca}_A"
                            
                            real_cb = cb
                            if cb not in df_curr.columns and f"{cb}_B" in df_curr.columns: real_cb = f"{cb}_B"
                            
                            if real_ca in df_curr.columns and real_cb in df_curr.columns:
                                df_curr = df_curr[df_curr[real_ca].astype(str).str.strip() == df_curr[real_cb].astype(str).str.strip()]
                                step_counts.append(len(df_curr))
                            else:
                                step_counts.append(0) # Column missing?
                                
                    else:
                        # Non-equals operator
                        if df_curr is None:
                            # Cannot start with non-equals (no cross join allowed)
                            step_counts.append(0) 
                        else:
                            # Filter
                            ca = c.col_a
                            cb = c.col_b
                            real_ca = ca
                            if ca not in df_curr.columns and f"{ca}_A" in df_curr.columns: real_ca = f"{ca}_A"
                            real_cb = cb
                            if cb not in df_curr.columns and f"{cb}_B" in df_curr.columns: real_cb = f"{cb}_B"
                            
                            if real_ca in df_curr.columns and real_cb in df_curr.columns:
                                if c.op == 'not_equals':
                                    df_curr = df_curr[df_curr[real_ca] != df_curr[real_cb]]
                                elif c.op == 'contains':
                                    df_curr = df_curr[df_curr[real_ca].astype(str).str.contains(df_curr[real_cb].astype(str), na=False)]
                                elif c.op == 'not_contains':
                                    df_curr = df_curr[~df_curr[real_ca].astype(str).str.contains(df_curr[real_cb].astype(str), na=False)]
                                step_counts.append(len(df_curr))
                            else:
                                step_counts.append(0)

                except Exception as e:
                    print(f"Stats Error at step {idx}: {e}")
                    step_counts.append(0)
            
            total = len(df_curr) if df_curr is not None else 0
            return {"steps": step_counts, "total": total}

        return await run_in_threadpool(process_stats)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"steps": [], "total": 0, "error": str(e)}

@router.get("/api/doc/diff/result/{result_id}/page")
async def get_diff_result_page(result_id: str, page: int = 1, size: int = 50):
    try:
        print(f"DEBUG: get_diff_result_page. ID={result_id}, Page={page}, Size={size}")
        
        if result_id not in FILE_CACHE:
            print("DEBUG: Result ID not in cache")
            raise HTTPException(status_code=404, detail="Result expired")
        
        df = FILE_CACHE[result_id]
        total = len(df)
        start = (page - 1) * size
        end = start + size
        
        print(f"DEBUG: Slicing Result. Total={total}, Start={start}, End={end}")
        
        # Slice
        subset = df.iloc[start:end]
        # Handle NaNs
        import numpy as np
        subset = subset.replace({np.nan: None})
        
        return {
            "page": page,
            "pageSize": size,
            "total": total,
            "rows": subset.to_dict(orient='records')
        }
    except Exception as e:
        import traceback
        print("DEBUG: get_diff_result_page Error:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/doc/diff/run")
async def run_diff(req: DiffRunRequest):
    try:
        print(f"DEBUG: run_diff started. A={req.file_id_a}, B={req.file_id_b}, Mode={req.mode}")
        
        if req.file_id_a not in DATAFRAME_CACHE and req.file_id_a not in FILE_CACHE:
             print("DEBUG: File A missing from both caches")
             raise HTTPException(status_code=404, detail="文件已过期或不存在")
        if req.file_id_b not in DATAFRAME_CACHE and req.file_id_b not in FILE_CACHE:
             print("DEBUG: File B missing from both caches")
             raise HTTPException(status_code=404, detail="文件已过期或不存在")
             
        # Need to access file metadata for re-parsing if needed
        # But wait, run_diff logic below checks DATAFRAME_CACHE first.
        # So we just need to ensure we can get file content if DF missing.
        
        # If file_id in DATAFRAME_CACHE, we are good.
        # If not, we need FILE_CACHE.
        
        # Logic below handles it.
        
        # Run diff logic in threadpool to avoid blocking
        def process_diff():
            print("DEBUG: process_diff start")
            # 1. Get DataFrames (Try Cache First)
            if req.file_id_a in DATAFRAME_CACHE:
                 print("DEBUG: Using Cached DF for A")
                 df_a = DATAFRAME_CACHE[req.file_id_a][req.sheet_a].copy()
            else:
                 print("DEBUG: Parsing DF for A")
                 file_a = FILE_CACHE[req.file_id_a]
                 df_a = read_file_to_df(file_a['content'], file_a['ext'], req.sheet_a)
            
            if req.file_id_b in DATAFRAME_CACHE:
                 print("DEBUG: Using Cached DF for B")
                 df_b = DATAFRAME_CACHE[req.file_id_b][req.sheet_b].copy()
            else:
                 print("DEBUG: Parsing DF for B")
                 file_b = FILE_CACHE[req.file_id_b]
                 df_b = read_file_to_df(file_b['content'], file_b['ext'], req.sheet_b)
            
            # Global cleanup: fillna with empty string to avoid NaN issues
            df_a = df_a.fillna("").astype(str)
            df_b = df_b.fillna("").astype(str)
            
            # Strip all string columns again just in case
            for col in df_a.columns: df_a[col] = df_a[col].str.strip()
            for col in df_b.columns: df_b[col] = df_b[col].str.strip()
            
            print(f"DEBUG: DF Loaded & Cleaned. A shape={df_a.shape}, B shape={df_b.shape}")
            
            equals_conds = [c for c in req.conditions if c.op == 'equals']
            other_conds = [c for c in req.conditions if c.op != 'equals']
            
            if not equals_conds:
                 raise ValueError("至少需要一个'等于'条件来对齐数据")
                 
            left_on = [c.col_a for c in equals_conds]
            right_on = [c.col_b for c in equals_conds]
            
            # Validate columns
            for col in left_on:
                if col not in df_a.columns: raise KeyError(f"源文件(A)中找不到列: {col}")
            for col in right_on:
                if col not in df_b.columns: raise KeyError(f"目标文件(B)中找不到列: {col}")
            
            # 2. Outer Join with Indicator
            print("DEBUG: Merging (Outer)...")
            # Note: We cast to str above, so merge should be robust
            merged = pd.merge(df_a, df_b, left_on=left_on, right_on=right_on, suffixes=('_A', '_B'), how='outer', indicator=True)
            print(f"DEBUG: Merge done. Result shape={merged.shape}")
            
            # 3. Mode Filtering
            if req.mode == 'intersection':
                # Only keep rows present in BOTH
                merged = merged[merged['_merge'] == 'both']
            elif req.mode == 'difference_a':
                # Only keep rows in A but NOT in B (Left Only)
                merged = merged[merged['_merge'] == 'left_only']
            elif req.mode == 'difference_b':
                # Only keep rows in B but NOT in A (Right Only)
                merged = merged[merged['_merge'] == 'right_only']
            
            # 4. Apply Other Conditions (Filter)
            # Only applicable if we have data (and typically for 'intersection' mode)
            # For difference modes, 'other_conds' might not make sense or should be ignored?
            # Actually, if user wants "A-B where Name != Name", that implies intersection logic.
            # If user wants "Left Only", then B columns are null, so comparisons fail.
            
            if req.mode == 'intersection' and other_conds:
                for c in other_conds:
                    # Resolve column names (suffixes)
                    col_a = c.col_a
                    if col_a not in merged.columns and f"{col_a}_A" in merged.columns: col_a = f"{col_a}_A"
                    
                    col_b = c.col_b
                    if col_b not in merged.columns and f"{col_b}_B" in merged.columns: col_b = f"{col_b}_B"
                    
                    if col_a in merged.columns and col_b in merged.columns:
                        if c.op == 'not_equals':
                            merged = merged[merged[col_a] != merged[col_b]]
                        elif c.op == 'contains':
                            merged = merged[merged[col_a].str.contains(merged[col_b], na=False, regex=False)]
                        elif c.op == 'not_contains':
                            merged = merged[~merged[col_a].str.contains(merged[col_b], na=False, regex=False)]
            
            # Remove indicator column
            if '_merge' in merged.columns:
                del merged['_merge']

            # Replace NaN for JSON (though we filled with "", outer merge introduces new NaNs for non-matching rows)
            # So fill again
            import numpy as np
            merged = merged.replace({np.nan: None})
            
            # Save Result to Memory
            result_id = str(uuid.uuid4())
            FILE_CACHE[result_id] = merged
                
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
    if result_id not in FILE_CACHE:
        raise HTTPException(status_code=404, detail="结果文件已过期")
    
    # Run export in threadpool
    def export_excel():
        df = FILE_CACHE[result_id]
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
