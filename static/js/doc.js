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
    const container = document.getElementById(containerId);
    const tableId = module + '-table';
    
    // Pagination Calc
    const start = (state.page - 1) * state.pageSize;
    const end = start + state.pageSize;
    const displayRows = state.rows.slice(start, end);
    const totalPages = Math.ceil(state.rows.length / state.pageSize);
    
    // Build Table HTML
    let html = `<table id="${tableId}" class="doc-table"><thead><tr>`;
    
    // Corner Cell (Row Numbers Header)
    html += `<th class="row-num">#</th>`;

    // Headers
    state.headers.forEach((h, idx) => {
        // Add class for column selection/hover identification
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
    displayRows.forEach((row, rIdx) => {
        const globalRowIdx = start + rIdx + 1;
        html += `<tr>`;
        
        // Row Number Cell
        html += `<td class="row-num">${globalRowIdx}</td>`;
        
        state.headers.forEach((col, cIdx) => {
            let val = row[col] !== null ? String(row[col]) : '';
            // Highlight Logic
            if (state.filterQuery) {
                 const regex = new RegExp(`(${state.filterQuery})`, 'gi');
                 val = val.replace(regex, '<span class="search-highlight">$1</span>');
            }
            // Add class for column, and context menu handler
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
    
    // Update highlights after render
    if (module.startsWith('diff')) {
        updateColumnHighlights();
    }
    
    // Render Pagination
    const pagId = module + '-pagination';
    const pagEl = document.getElementById(pagId);
    if (pagEl) {
        const totalRows = state.rows.length;
        pagEl.innerHTML = `
            <div style="margin-right: auto; color: #888; font-size: 12px;">
                总计：${totalRows} 行
            </div>
            
            <select onchange="changePageSize('${module}', this.value)" style="background: #3c3c3c; color: white; border: 1px solid #555; padding: 2px 5px; border-radius: 4px; margin-right: 10px; font-size: 12px;">
                <option value="10" ${state.pageSize == 10 ? 'selected' : ''}>10 / 页</option>
                <option value="20" ${state.pageSize == 20 ? 'selected' : ''}>20 / 页</option>
                <option value="50" ${state.pageSize == 50 ? 'selected' : ''}>50 / 页</option>
                <option value="100" ${state.pageSize == 100 ? 'selected' : ''}>100 / 页</option>
            </select>

            <button onclick="changePage('${module}', -1)" ${state.page === 1 ? 'disabled' : ''}>< 上一页</button>
            <span style="margin: 0 10px;">第 ${state.page} 页 / 共 ${totalPages} 页</span>
            <button onclick="changePage('${module}', 1)" ${state.page === totalPages ? 'disabled' : ''}>下一页 ></button>
        `;
    }
}

function changePageSize(module, newSize) {
    const state = docState[module];
    state.pageSize = parseInt(newSize);
    state.page = 1; // Reset to first page
    renderInteractiveTable(module + '-table-container', module);
}

function changePage(module, delta) {
    const state = docState[module];
    const totalPages = Math.ceil(state.rows.length / state.pageSize);
    const newPage = state.page + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        state.page = newPage;
        renderInteractiveTable(module + '-table-container', module);
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
         filterQuery: ''
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
         <select class="cond-op" style="width:80px; background:#333; color:white; border:1px solid #555;">
             <option value="equals">等于</option>
             <option value="not_equals">不等于</option>
             <option value="contains">包含</option>
             <option value="not_contains">不包含</option>
         </select>
         <select class="cond-col-b" style="flex:1; background:#333; color:white; border:1px solid #555;" onchange="updateColumnHighlights()">${optsB}</select>
         <button onclick="this.parentElement.remove(); updateColumnHighlights();" style="background:none; border:none; color:#f44336; cursor:pointer;"><i class="fa-solid fa-times"></i></button>
     `;
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
    
    const req = {
        file_id_a: docState.diff.fileA,
        sheet_a: docState.diff.currentSheetA,
        file_id_b: docState.diff.fileB,
        sheet_b: docState.diff.currentSheetB,
        conditions: conditions
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
        docState.diffResult = {
            headers: data.preview.headers,
            rows: data.preview.rows,
            page: 1,
            pageSize: 50,
            filterQuery: '',
            resultId: data.result_id
        };
        
        document.getElementById('diff-result-modal').classList.remove('hidden');
        renderInteractiveTable('diff-result-table-container', 'diffResult');
        
        // Bind Download Button
        document.getElementById('btn-download-diff').onclick = () => downloadDiffResult(data.result_id);
        
    } catch (e) { alert("对比失败：" + e.message); }
}

async function downloadDiffResult(resultId) {
    window.location.href = `/api/doc/diff/download/${resultId}`;
}
 
 function selectDiffColumn(module, colName) {
      // Logic moved to Double Click, but keeping this if single click on header is needed later
  }

  // --- Double Click Interaction & Highlighting ---
  let lastInteractedSide = null; // 'A' or 'B' or null

  function handleCellDoubleClick(module, colName) {
      if (!module.startsWith('diff')) return;
      
      const side = module === 'diffA' ? 'A' : 'B';
      const list = document.getElementById('diff-conditions-list');
      const rows = list.children;
      
      // If A is double clicked
      if (side === 'A') {
          // Logic: 
          // 1. If we just interacted with B (completed a pair) -> Start NEW pair with A
          // 2. If we just interacted with A (maybe correcting selection) -> Update CURRENT last row A
          // 3. If no rows -> Start NEW pair
          
          let targetRow = null;
          
          if (rows.length === 0 || lastInteractedSide === 'B') {
              // Create new row
              addDiffCondition(); // This creates a row and sets default first col
              targetRow = list.lastElementChild;
          } else {
              // Use last row
              targetRow = list.lastElementChild;
          }
          
          // Set A value
          const selA = targetRow.querySelector('.cond-col-a');
          selA.value = colName;
          
          lastInteractedSide = 'A';
      } 
      // If B is double clicked
      else if (side === 'B') {
          // Logic:
          // 1. If we just interacted with A (pending pair) -> Complete CURRENT row B
          // 2. If we just interacted with B (correcting) -> Update CURRENT last row B
          // 3. If no rows or just completed B -> Start NEW pair (Wait, B first? Rare, but okay. Create row, set B)
          
          let targetRow = null;
          
          if (rows.length === 0 || lastInteractedSide === 'B') {
               // Create new row (though unusual to start with B)
               addDiffCondition();
               targetRow = list.lastElementChild;
          } else {
               // Use last row (which presumably has A set)
               targetRow = list.lastElementChild;
          }
          
          // Set B value
          const selB = targetRow.querySelector('.cond-col-b');
          selB.value = colName;
          
          lastInteractedSide = 'B';
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
      // Logic: The last row is "Active" IF it's not fully "sealed". 
      // But for simplicity, let's say the last row is ALWAYS "Active" (Bright), others are "Used" (Dim).
      
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
