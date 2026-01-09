// --- Doc Module Logic ---
function switchDocPanel(panelName) {
    document.querySelectorAll('.doc-nav-item').forEach(el => el.classList.remove('active'));
    const map = { 'converter': 0, 'diff': 1, 'toolbox': 2 };
    const navItems = document.querySelectorAll('.doc-nav-item');
    if(navItems[map[panelName]]) navItems[map[panelName]].classList.add('active');
    
    document.querySelectorAll('.doc-panel').forEach(el => el.classList.remove('active'));
    document.getElementById('doc-panel-' + panelName).classList.add('active');
}

// --- Converter Logic ---
function triggerJsonUpload() { document.getElementById('json-upload-input').click(); }

function handleJsonUpload(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = (e) => {
            executeJsonParse(e.target.result);
        };
        reader.readAsText(input.files[0]);
        input.value = ''; // Reset to allow re-upload
    }
}

async function parseJsonInput() {
    const content = document.getElementById('json-input-text').value;
    if (!content.trim()) { alert("请输入 JSON 内容"); return; }
    executeJsonParse(content);
}

async function executeJsonParse(content) {
    try {
        const res = await fetch('/api/doc/json/parse', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ content })
        });
        if (!res.ok) throw new Error((await res.json()).detail);
        
        const data = await res.json();
        docState.converter.headers = data.headers;
        docState.converter.rows = data.rows;
        docState.converter.page = 1;
        docState.converter.searchMatches = [];
        docState.converter.currentMatch = -1;
        
        document.getElementById('converter-input-area').classList.add('hidden');
        document.getElementById('converter-preview-area').classList.remove('hidden');
        
        renderInteractiveTable('converter-table-container', 'converter');
    } catch (e) { alert("解析错误：" + e.message); }
}

function resetConverter() {
    document.getElementById('converter-preview-area').classList.add('hidden');
    document.getElementById('converter-input-area').classList.remove('hidden');
}

async function downloadConverterExcel() {
    try {
        const res = await fetch('/api/doc/excel/generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                headers: docState.converter.headers, 
                rows: docState.converter.rows 
            })
        });
        if (!res.ok) throw new Error("下载失败");
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = "converted.xlsx";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    } catch (e) { alert(e.message); }
}

// --- Shared Table Logic ---
function renderInteractiveTable(containerId, module) {
    const state = docState[module];
    if (!state) return; // Safety check
    
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const tableId = module + '-table';
    
    // Ensure numeric types
    state.page = Number(state.page) || 1;
    state.pageSize = Number(state.pageSize) || 50;

    // Pagination Calc
    // Check if totalRows is defined (even if 0)
    const isBackendPagination = (state.totalRows !== undefined && state.totalRows !== null);
    
    // Ensure rows is an array
    if (!Array.isArray(state.rows)) state.rows = [];

    const totalRows = isBackendPagination ? state.totalRows : state.rows.length;
    // Prevent division by zero or NaN
    const totalPages = (state.pageSize > 0) ? Math.ceil(totalRows / state.pageSize) : 1;
    const safeTotalPages = totalPages > 0 ? totalPages : 1;
    
    let displayRows = [];
    if (isBackendPagination) {
        displayRows = state.rows;
        // Safety check
        if (displayRows.length > state.pageSize) {
            displayRows = displayRows.slice(0, state.pageSize);
        }
    } else {
        const start = (state.page - 1) * state.pageSize;
        const end = start + state.pageSize;
        displayRows = state.rows.slice(start, end);
    }

    // Build Table HTML
    let html = `<table id="${tableId}" class="doc-table"><thead><tr>`;
    
    // Corner Cell
    html += `<th class="row-num">#</th>`;

    // Headers
    (state.headers || []).forEach((h, idx) => {
        html += `<th class="col-${idx}" 
            ondblclick="editHeader('${module}', ${idx}, this)" 
            onclick="selectDiffColumn('${module}', '${h}')" 
            oncontextmenu="showHeaderMenu(event, '${module}', ${idx})"
            onmouseenter="highlightColumn('${module}', ${idx}, true)"
            onmouseleave="highlightColumn('${module}', ${idx}, false)"
        >${h}</th>`;
    });
    html += `</tr></thead><tbody>`;
    
    // Rows
    // FIX: For client-side pagination, row numbers should start from (page-1)*size + 1.
    // For backend pagination, we also need to know the offset.
    // Current logic: pageStartIdx is calculated from current page.
    const pageStartIdx = (state.page - 1) * state.pageSize;
    
    displayRows.forEach((row, rIdx) => {
        const globalRowIdx = pageStartIdx + rIdx + 1;
        html += `<tr>`;
        html += `<td class="row-num">${globalRowIdx}</td>`;
        
        (state.headers || []).forEach((col, cIdx) => {
            let val = (row && row[col] !== null && row[col] !== undefined) ? String(row[col]) : '';
            if (state.filterQuery) {
                 const regex = new RegExp(`(${state.filterQuery})`, 'gi');
                 val = val.replace(regex, '<span class="search-highlight">$1</span>');
            }
            html += `<td class="col-${cIdx}" 
                oncontextmenu="showHeaderMenu(event, '${module}', ${cIdx})"
                onmouseenter="highlightColumn('${module}', ${cIdx}, true)"
                onmouseleave="highlightColumn('${module}', ${cIdx}, false)"
                ondblclick="handleCellDoubleClick('${module}', '${col}')"
            >${val}</td>`;
        });
        html += `</tr>`;
    });
    html += `</tbody></table>`;
    
    container.innerHTML = html;
    
    if (module.startsWith('diff')) {
        updateColumnHighlights();
    }
    
    // Render Pagination
    // Note: module might be "diffResult" (camelCase), but ID in HTML is "diffResult-pagination"
    // Other modules like "converter", "toolbox" might use different ID conventions?
    // Let's check HTML.
    // Converter has no pagination ID in previous code?
    // Toolbox usually just "toolbox-preview-container".
    
    // Let's try to find a pagination container generically.
    // If module is "diffResult", ID is "diffResult-pagination".
    // If module is "converter", ID might be "converter-pagination" (if exists).
    
    const possibleIds = [module + '-pagination', module.replace('Result', '') + '-pagination'];
    let pagEl = null;
    for (const id of possibleIds) {
        pagEl = document.getElementById(id);
        if (pagEl) break;
    }
    
    if (pagEl) {
        pagEl.innerHTML = `
            <div style="margin-right: auto; color: #888; font-size: 12px;">
                总计：${totalRows} 行
            </div>
            
            <select onchange="changePageSize('${module}', this.value)" style="background: #3c3c3c; color: white; border: 1px solid #555; padding: 2px 5px; border-radius: 4px; margin-right: 10px; font-size: 12px;">
                <option value="10" ${state.pageSize === 10 ? 'selected' : ''}>10 / 页</option>
                <option value="20" ${state.pageSize === 20 ? 'selected' : ''}>20 / 页</option>
                <option value="50" ${state.pageSize === 50 ? 'selected' : ''}>50 / 页</option>
                <option value="100" ${state.pageSize === 100 ? 'selected' : ''}>100 / 页</option>
            </select>

            <button onclick="changePage('${module}', -1)" ${state.page <= 1 ? 'disabled' : ''}>< 上一页</button>
            <span style="margin: 0 10px;">第 ${state.page} 页 / 共 ${safeTotalPages} 页</span>
            <button onclick="changePage('${module}', 1)" ${state.page >= safeTotalPages ? 'disabled' : ''}>下一页 ></button>
        `;
    }
}

async function changePageSize(module, newSize) {
    const state = docState[module];
    if (!state) return;
    
    state.pageSize = parseInt(newSize);
    state.page = 1; 
    
    if (state.totalRows !== undefined && state.totalRows !== null) {
        await fetchDiffPage(module);
    }
    renderInteractiveTable(module + '-table-container', module);
}

async function changePage(module, delta) {
    console.log(`DEBUG: changePage called for ${module}, delta=${delta}`);
    const state = docState[module];
    if (!state) return;
    
    const isBackendPagination = (state.totalRows !== undefined && state.totalRows !== null);
    const totalRows = isBackendPagination ? state.totalRows : state.rows.length;
    // Prevent division by zero
    const pageSize = state.pageSize > 0 ? state.pageSize : 50;
    const totalPages = Math.ceil(totalRows / pageSize) || 1;
    
    console.log(`DEBUG: Current Page: ${state.page}, Total Pages: ${totalPages}, Total Rows: ${totalRows}`);
    
    const newPage = state.page + delta;
    
    if (newPage >= 1 && newPage <= totalPages) {
        state.page = newPage;
        console.log(`DEBUG: Advancing to page ${newPage}`);
        
        if (isBackendPagination) {
             console.log("DEBUG: Fetching backend page...");
             const success = await fetchDiffPage(module);
             if (!success) {
                 console.error("DEBUG: Backend fetch failed");
                 state.page -= delta; // Revert if failed
                 return; 
             }
        }
        
        renderInteractiveTable(module + '-table-container', module);
    } else {
        console.warn("DEBUG: Page out of bounds");
    }
}

async function fetchDiffPage(module) {
    const state = docState[module];
    if (!state || !state.resultId) {
        console.error("DEBUG: Missing state or resultId for", module);
        return false;
    }
    
    // Show loading indicator
    const container = document.getElementById(module + '-table-container');
    if(container) container.style.opacity = '0.5';
    
    try {
        let url;
        if (module === 'diffResult') {
             url = `/api/doc/diff/result/${state.resultId}/page?page=${state.page}&size=${state.pageSize}`;
        } else if (module === 'diffA' || module === 'diffB') {
             const side = module === 'diffA' ? 'A' : 'B';
             const sheet = docState.diff['currentSheet' + side];
             // Encode sheet name to handle special chars
             url = `/api/doc/file/${state.resultId}/data?sheet=${encodeURIComponent(sheet)}&page=${state.page}&size=${state.pageSize}`;
        } else {
             // Fallback or other modules
             console.error("DEBUG: Unknown module for paging:", module);
             return false;
        }
        
        console.log("DEBUG: Fetching URL:", url);

        const res = await fetch(url);
        if (!res.ok) throw new Error("分页加载失败: " + res.statusText);
        const data = await res.json();
        
        console.log("DEBUG: Page Data Received. Rows:", data.rows ? data.rows.length : 'N/A');
        
        if (Array.isArray(data.rows)) {
            state.rows = data.rows;
            if(container) container.style.opacity = '1';
            return true;
        }
        throw new Error("Invalid data format");
    } catch(e) {
        alert(e.message);
        console.error("DEBUG: Fetch Error:", e);
        if(container) container.style.opacity = '1';
        return false;
    }
}


function editHeader(module, idx, th) {
    const oldVal = docState[module].headers[idx];
    const input = document.createElement('input');
    input.value = oldVal;
    input.style.width = '100%';
    input.style.color = 'black';
    
    input.onblur = () => finishEdit();
    input.onkeydown = (e) => { if (e.key === 'Enter') finishEdit(); };
    
    function finishEdit() {
         const newVal = input.value.trim();
         if (newVal && newVal !== oldVal) {
             docState[module].headers[idx] = newVal;
             docState[module].rows.forEach(r => {
                 r[newVal] = r[oldVal];
                 delete r[oldVal];
             });
             renderInteractiveTable(module + '-table-container', module);
         } else {
             th.innerText = oldVal;
         }
     }
     
     th.innerHTML = '';
     th.appendChild(input);
     input.focus();
 }
 
 // Context Menu Logic
 let contextMenuTarget = { module: null, colIdx: -1 };

 function showHeaderMenu(e, module, idx) {
     e.preventDefault();
     contextMenuTarget = { module, idx };
     const menu = document.getElementById('column-context-menu');
     menu.style.display = 'block';
     menu.style.left = e.pageX + 'px';
     menu.style.top = e.pageY + 'px';
 }

 function highlightColumn(module, idx, isActive) {
     const tableId = module + '-table';
     const table = document.getElementById(tableId);
     if (!table) return;
     
     // Performance: Select by class is faster than iterating all rows
     // We added class "col-{idx}" to both th and td
     const cells = table.querySelectorAll(`.col-${idx}`);
     cells.forEach(cell => {
         if (isActive) cell.classList.add('col-hover');
         else cell.classList.remove('col-hover');
     });
 }

 function deleteColumnAction() {
     const { module, idx } = contextMenuTarget;
     if (module && idx !== -1) {
          docState[module].headers.splice(idx, 1);
          renderInteractiveTable(module + '-table-container', module);
     }
     hideContextMenu();
 }

 function hideContextMenu() {
     document.getElementById('column-context-menu').style.display = 'none';
 }

 function searchTable(tableId, query) {
    const module = tableId.split('-')[0];
    docState[module].filterQuery = query;
    renderInteractiveTable(module + '-table-container', module);
}

function navigateSearch(tableId, dir) {
     alert("当前版本仅支持页内搜索导航。");
 }

 // --- Diff Module Logic ---
 async function loadDiffFile(side, input) { // side: 'A' or 'B'
     if (!input.files || !input.files[0]) return;
     
     const formData = new FormData();
    formData.append('file', input.files[0]);
    
    // Updated ID convention: module + '-table-container'
    // diffA -> diffA-table-container
    const previewContainer = document.getElementById(`diff${side}-table-container`);
    previewContainer.innerHTML = '<div style="padding:20px; color:#aaa;">上传解析中...</div>';
    
    try {
         const res = await fetch('/api/doc/excel/upload', {
             method: 'POST',
             body: formData
         });
         
         if (!res.ok) {
             let errorMsg = res.statusText;
             try {
                 const text = await res.text();
                 try {
                     const errJson = JSON.parse(text);
                     errorMsg = errJson.detail || errorMsg;
                 } catch (e) {
                     // Not JSON, use text directly
                     if (text) errorMsg = text.substring(0, 100) + "...";
                 }
             } catch (e) {
                 // Read failed, keep statusText
             }
             throw new Error(errorMsg);
         }
         
         const data = await res.json();
         
         if (side === 'A') {
             docState.diff.fileA = data.file_id;
             docState.diff.sheetsA = data.sheets;
             docState.diff.previewA = data.preview; 
         } else {
             docState.diff.fileB = data.file_id;
             docState.diff.sheetsB = data.sheets;
             docState.diff.previewB = data.preview;
         }
         
         renderSheetTabs(side, data.sheets);
         if (data.sheets.length > 0) {
            switchSheet(side, data.sheets[0]);
        }
    } catch (e) {
        previewContainer.innerHTML = `<div style="padding:20px; color:red;">错误：${e.message}</div>`;
    }
}
 
 function renderSheetTabs(side, sheets) {
     const container = document.getElementById(`diff-sheets-${side.toLowerCase()}`);
     container.innerHTML = sheets.map(s => 
         `<div class="sheet-tab" onclick="switchSheet('${side}', '${s}')">${s}</div>`
     ).join('');
 }
 
 function switchSheet(side, sheetName) {
     const container = document.getElementById(`diff-sheets-${side.toLowerCase()}`);
     Array.from(container.children).forEach(el => {
         el.classList.toggle('active', el.innerText === sheetName);
     });
     
     docState.diff['currentSheet' + side] = sheetName;
     const previewData = docState.diff['preview' + side][sheetName];
     
     docState['diff' + side] = {
         headers: [...previewData.headers], 
         rows: [...previewData.rows], 
         page: 1,
         pageSize: 50,
         filterQuery: '',
         resultId: docState.diff['file' + side],
         totalRows: previewData.total_rows
    };
    
    // Use unified ID: diffA-table-container
    renderInteractiveTable(`diff${side}-table-container`, 'diff' + side);
    updateConditionDropdowns();
}
 
 function addDiffCondition() {
     const list = document.getElementById('diff-conditions-list');
     const div = document.createElement('div');
     div.style.display = 'flex';
     div.style.gap = '10px';
     div.style.marginBottom = '5px';
     div.style.alignItems = 'center';
     
     const colsA = docState.diffA ? docState.diffA.headers : [];
     const colsB = docState.diffB ? docState.diffB.headers : [];
     
     const optsA = colsA.map(c => `<option value="${c}">${c}</option>`).join('');
     const optsB = colsB.map(c => `<option value="${c}">${c}</option>`).join('');
     
     div.innerHTML = `
         <select class="cond-col-a" style="flex:1; background:#333; color:white; border:1px solid #555;" onchange="updateColumnHighlights()">${optsA}</select>
         <select class="cond-op" style="width:80px; background:#333; color:white; border:1px solid #555;" onchange="updateColumnHighlights()">
             <option value="equals">等于</option>
             <option value="not_equals">不等于</option>
             <option value="contains">包含</option>
             <option value="not_contains">不包含</option>
         </select>
         <select class="cond-col-b" style="flex:1; background:#333; color:white; border:1px solid #555;" onchange="updateColumnHighlights()">${optsB}</select>
         <span class="cond-count" style="width:60px; text-align:right; color:#888; font-size:12px;">-</span>
         <button onclick="this.parentElement.remove(); updateColumnHighlights();" style="background:none; border:none; color:#f44336; cursor:pointer;"><i class="fa-solid fa-times"></i></button>
     `;
     
     // Initialize touched state for smart pairing
     div.dataset.touchedA = "false";
     div.dataset.touchedB = "false";
     
     list.appendChild(div);
     
     // Scroll to bottom
     list.scrollTop = list.scrollHeight;
     
     // Update highlights immediately for the new row (default selected columns)
     updateColumnHighlights();
 }
 
 function updateConditionDropdowns() {
     const colsA = docState.diffA ? docState.diffA.headers : [];
     const colsB = docState.diffB ? docState.diffB.headers : [];
     
     document.querySelectorAll('.cond-col-a').forEach(sel => {
         const val = sel.value;
         sel.innerHTML = colsA.map(c => `<option value="${c}">${c}</option>`).join('');
         if(colsA.includes(val)) sel.value = val;
     });
     
     document.querySelectorAll('.cond-col-b').forEach(sel => {
         const val = sel.value;
         sel.innerHTML = colsB.map(c => `<option value="${c}">${c}</option>`).join('');
         if(colsB.includes(val)) sel.value = val;
     });
 }
 
 async function startDiff() {
    if (!docState.diff.fileA || !docState.diff.fileB) { alert("请上传两个文件"); return; }
    
    const conditions = [];
    document.querySelectorAll('#diff-conditions-list > div').forEach(div => {
        conditions.push({
            col_a: div.querySelector('.cond-col-a').value,
            op: div.querySelector('.cond-op').value,
            col_b: div.querySelector('.cond-col-b').value
        });
    });
    
    if (conditions.length === 0) { alert("请至少添加一个条件"); return; }
    
    // Get selected mode
    const mode = document.getElementById('diff-mode-select').value;
    
    const req = {
        file_id_a: docState.diff.fileA,
        sheet_a: docState.diff.currentSheetA,
        file_id_b: docState.diff.fileB,
        sheet_b: docState.diff.currentSheetB,
        conditions: conditions,
        mode: mode
    };
    
    try {
        const res = await fetch('/api/doc/diff/run', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(req)
        });
        if (!res.ok) throw new Error((await res.json()).detail);
        
        const data = await res.json();
        
        // Show Preview Modal
        // Ensure rows match pageSize for initial page
        const initialRows = data.preview.rows.slice(0, 50);
        
        docState.diffResult = {
            headers: data.preview.headers,
            rows: initialRows, // Use sliced rows for page 1
            page: 1,
            pageSize: 50,
            filterQuery: '',
            resultId: data.result_id,
            totalRows: data.total_rows // Ensure total_rows is correctly passed
        };
        
        console.log("DEBUG: Diff Result Init. Total Rows:", data.total_rows, "Result ID:", data.result_id);
        
        // Pass conditions and mode to modal for display
        showDiffResultModal(conditions, mode);
        
        // Ensure the table container is cleared before rendering to avoid duplicates or stale data
        const container = document.getElementById('diff-result-table-container');
        if (container) container.innerHTML = '';
        
        renderInteractiveTable('diff-result-table-container', 'diffResult');
        
        // Bind Download Button
        document.getElementById('btn-download-diff').onclick = () => downloadDiffResult(data.result_id);
        
    } catch (e) { alert("对比失败：" + e.message); }
}

function showDiffResultModal(conditions, mode) {
    const modal = document.getElementById('diff-result-modal');
    modal.classList.remove('hidden');
    
    // Inject conditions summary
    const container = document.getElementById('diff-result-conditions');
    if (container) {
        const opMap = {
            'equals': '等于', 'not_equals': '不等于',
            'contains': '包含', 'not_contains': '不包含'
        };
        const modeMap = {
            'intersection': '交集 (Matched)',
            'difference_a': '仅源文件 (A-B)',
            'difference_b': '仅目标文件 (B-A)'
        };
        
        const modeBadge = `<span class="badge-cond" style="background:#007acc; color:white;">模式: ${modeMap[mode] || mode}</span>`;
        
        const condBadges = conditions.map((c, i) => `
            <span class="badge-cond">
                ${c.col_a} <span style="color:#aaa">${opMap[c.op]}</span> ${c.col_b}
            </span>
        `).join('');
        
        container.innerHTML = modeBadge + condBadges;
    }
}

async function downloadDiffResult(resultId) {
    window.location.href = `/api/doc/diff/download/${resultId}`;
}
 
 function selectDiffColumn(module, colName) {
      // Logic moved to Double Click, but keeping this if single click on header is needed later
  }

  // --- Double Click Interaction & Highlighting ---

  function handleCellDoubleClick(module, colName) {
      if (!module.startsWith('diff')) return;
      
      const side = module === 'diffA' ? 'A' : 'B';
      const list = document.getElementById('diff-conditions-list');
      const rows = list.children;
      
      // Determine if we need a new row or use the last one
      let targetRow = null;
      let needNewRow = false;

      if (rows.length === 0) {
          needNewRow = true;
      } else {
          const lastRow = list.lastElementChild;
          // Check if the last row is "Full" (both sides touched)
          // If manually added, dataset might be undefined, treat as false (not full)
          const touchedA = lastRow.dataset.touchedA === "true";
          const touchedB = lastRow.dataset.touchedB === "true";
          
          if (touchedA && touchedB) {
              needNewRow = true;
          } else {
              targetRow = lastRow;
          }
      }

      if (needNewRow) {
          addDiffCondition();
          targetRow = list.lastElementChild;
      }
      
      // Update value and touched state
      if (side === 'A') {
          const selA = targetRow.querySelector('.cond-col-a');
          selA.value = colName;
          targetRow.dataset.touchedA = "true";
      } else {
          const selB = targetRow.querySelector('.cond-col-b');
          selB.value = colName;
          targetRow.dataset.touchedB = "true";
      }
      
      updateColumnHighlights();
  }

  function updateColumnHighlights() {
      // 1. Clear all highlights
      document.querySelectorAll('.col-highlight-active, .col-highlight-used').forEach(el => {
          el.classList.remove('col-highlight-active', 'col-highlight-used');
      });
      
      // 2. Gather used columns from all conditions
      const list = document.getElementById('diff-conditions-list');
      const rows = list.children;
      if (rows.length === 0) return;
      
      // We distinguish "Active" (Last row, currently being edited) vs "Used" (Previous rows)
      
      for (let i = 0; i < rows.length; i++) {
          const row = rows[i];
          const colA = row.querySelector('.cond-col-a').value;
          const colB = row.querySelector('.cond-col-b').value;
          
          const isActive = (i === rows.length - 1);
          const className = isActive ? 'col-highlight-active' : 'col-highlight-used';
          
          // Apply to Table A
          applyHighlight('diffA', colA, className);
          // Apply to Table B
          applyHighlight('diffB', colB, className);
      }
      
      // 3. Trigger Stats Check (Debounced)
      if (window.diffStatsTimeout) clearTimeout(window.diffStatsTimeout);
      window.diffStatsTimeout = setTimeout(checkDiffStats, 500);
  }

  async function checkDiffStats() {
      if (!docState.diff.fileA || !docState.diff.fileB) return;
      
      const conditions = [];
      const rows = document.querySelectorAll('#diff-conditions-list > div');
      if (rows.length === 0) return;
      
      rows.forEach(div => {
          conditions.push({
              col_a: div.querySelector('.cond-col-a').value,
              op: div.querySelector('.cond-op').value,
              col_b: div.querySelector('.cond-col-b').value
          });
      });
      
      // Get selected mode
      const mode = document.getElementById('diff-mode-select').value;
      
      const req = {
          file_id_a: docState.diff.fileA,
          sheet_a: docState.diff.currentSheetA,
          file_id_b: docState.diff.fileB,
          sheet_b: docState.diff.currentSheetB,
          conditions: conditions,
          mode: mode // Add mode to stats request
      };
      
      // Show loading
      rows.forEach(div => {
          div.querySelector('.cond-count').innerText = '...';
      });
      document.getElementById('diff-total-count-display').innerText = '计算中...';
      
      try {
          const res = await fetch('/api/doc/diff/stats', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify(req)
          });
          const data = await res.json();
          
          if (data.error) {
               document.getElementById('diff-total-count-display').innerText = '错误: ' + data.error;
               rows.forEach(div => div.querySelector('.cond-count').innerText = 'Err');
               return;
          }
          
          // Update steps
          data.steps.forEach((count, idx) => {
              if (rows[idx]) {
                  rows[idx].querySelector('.cond-count').innerText = count + ' 项';
              }
          });
          
          // Update total
          document.getElementById('diff-total-count-display').innerText = `最终匹配: ${data.total} 项`;
          
      } catch (e) {
          console.error(e);
      }
  }


  function applyHighlight(module, colName, className) {
      if (!docState[module]) return;
      
      const headers = docState[module].headers;
      const colIdx = headers.indexOf(colName);
      if (colIdx === -1) return;
      
      const table = document.getElementById(module + '-table');
      if (!table) return;
      
      // Select all cells in this column (th and td)
      // We used class "col-{idx}"
      const cells = table.querySelectorAll(`.col-${colIdx}`);
      cells.forEach(cell => cell.classList.add(className));
  }

  async function loadToolboxFile(input) {
     if (!input.files || !input.files[0]) return;
     const formData = new FormData();
     formData.append('file', input.files[0]);
     
     try {
         const res = await fetch('/api/doc/excel/upload', { method: 'POST', body: formData });
         const data = await res.json();
         
         const sheet = data.sheets[0];
         const preview = data.preview[sheet];
         
         docState.toolbox = {
             headers: preview.headers,
             rows: preview.rows,
             page: 1,
             pageSize: 50,
             filterQuery: ''
         };
         
         renderInteractiveTable('toolbox-preview-container', 'toolbox');
    } catch(e) { alert("上传失败：" + e.message); }
}
