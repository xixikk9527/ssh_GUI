// --- SFTP ---
let selectedFileElement = null;

function selectFileElement(el) {
    if (selectedFileElement) selectedFileElement.classList.remove('selected');
    selectedFileElement = el;
    el.classList.add('selected');
}

function getParentPath(path) {
    if (!path || path === '/' || path === '.') return '/';
    if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1);
    
    const lastSlashIndex = path.lastIndexOf('/');
    if (lastSlashIndex <= 0) return '/';
    return path.substring(0, lastSlashIndex);
}

async function refreshFileTree(path) {
    if (!session_id) return;
    const container = document.getElementById('sftp-tree');
    container.innerHTML = '<div style="padding:10px; color:#aaa;">Loading...</div>';
    try {
        const res = await fetch(`/api/files/list?session_id=${session_id}&path=${encodeURIComponent(path)}`);
        const data = await res.json();
        currentSftpPath = data.current_path;
        document.getElementById('sftp-path').innerText = currentSftpPath;
        
        container.innerHTML = '';
        if (currentSftpPath !== '/' && currentSftpPath !== '.') {
            const upEl = document.createElement('div');
            upEl.className = 'file-item';
            upEl.innerHTML = `<i class="fa-solid fa-arrow-up"></i> ..`;
            upEl.ondblclick = () => refreshFileTree(getParentPath(currentSftpPath));
            container.appendChild(upEl);
        }
        
        data.files.forEach(f => {
            const el = document.createElement('div');
            el.className = 'file-item';
            el.innerHTML = `<i class="fa-solid ${f.is_dir ? 'fa-folder' : 'fa-file'}"></i> ${f.name}`;
            el.onclick = () => selectFileElement(el);
            el.ondblclick = () => {
                if (f.is_dir) refreshFileTree(currentSftpPath + '/' + f.name);
                else openFile(currentSftpPath + '/' + f.name);
            };
            container.appendChild(el);
        });
    } catch (e) { container.innerHTML = '<div style="padding:10px; color:red;">Error loading files</div>'; }
}

async function openFile(path) {
    try {
        const res = await fetch(`/api/files/content?session_id=${session_id}&path=${encodeURIComponent(path)}`);
        if (!res.ok) {
            const err = await res.json();
            alert(err.detail); return;
        }
        const data = await res.json();
        currentEditingFile = path;
        if(window.editor) window.editor.setValue(data.content);
    } catch (e) { alert("Failed to open file (Network Error)"); }
}

async function saveFile() {
    if (!currentEditingFile) return;
    try {
        await fetch('/api/files/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ session_id, path: currentEditingFile, content: window.editor.getValue() })
        });
        alert("Saved successfully!");
    } catch (e) { alert("Save failed"); }
}

// Helper to build tree from flat paths
function buildTree(items) {
    const root = {};
    items.forEach(item => {
        const parts = item.path.split('/').filter(p => p); 
        let current = root;
        parts.forEach((part, i) => {
            if (!current[part]) {
                current[part] = { 
                    __data: (i === parts.length - 1) ? item : null, 
                    __children: {} 
                };
            } else if (i === parts.length - 1) {
                 current[part].__data = item; 
            }
            current = current[part].__children;
        });
    });
    return root;
}

// --- Tree View Logic ---
function createTreeDom(node, container, level = 0) {
    for (const key in node) {
        const childNode = node[key];
        const hasChildren = Object.keys(childNode.__children).length > 0;
        const item = childNode.__data;
        const isDir = item ? item.is_dir : hasChildren;
        
        const nodeEl = document.createElement('div');
        nodeEl.className = 'tree-node';
        
        const contentEl = document.createElement('div');
        contentEl.className = 'tree-content';
        contentEl.style.paddingLeft = (level * 15 + 5) + 'px';
        
        let iconHtml = '';
        if (isDir) {
            iconHtml = `<i class="fa-solid fa-folder" style="color: #dcb67a; margin-right:6px; width:14px; text-align:center;"></i>`;
        } else {
            iconHtml = `<i class="fa-solid fa-file" style="color: #9cdcfe; margin-right:6px; width:14px; text-align:center;"></i>`;
        }
        
        contentEl.innerHTML = `${iconHtml}<span style="font-size:13px;">${key}</span>`;
        nodeEl.appendChild(contentEl);
        
        let childrenContainer = null;
        if (hasChildren) {
            childrenContainer = document.createElement('div');
            childrenContainer.className = 'tree-children';
            createTreeDom(childNode.__children, childrenContainer, level); 
        }

        if (item) {
            contentEl.title = item.path;
            contentEl.ondblclick = (e) => {
                e.stopPropagation();
                if (item.is_dir) {
                    refreshFileTree(item.path);
                } else {
                    openFile(item.path);
                }
            };
        }

        contentEl.onclick = (e) => {
            e.stopPropagation();
            document.querySelectorAll('.tree-content').forEach(el => el.style.background = '');
            contentEl.style.background = '#37373d';
            
            if (isDir && childrenContainer) {
                if (childrenContainer.style.display === 'none') {
                    childrenContainer.style.display = 'block';
                } else {
                    childrenContainer.style.display = 'none';
                }
            }
        };

        container.appendChild(nodeEl);
        if (childrenContainer) container.appendChild(childrenContainer);
    }
}

async function sftpSearch() {
    const query = document.getElementById('sftp-search').value;
    if (!query) return;
    const container = document.getElementById('sftp-tree');
    container.innerHTML = '<div style="padding:10px;">Searching...</div>';
    
    try {
        const res = await fetch(`/api/files/search?session_id=${session_id}&path=/&query=${encodeURIComponent(query)}`);
        const results = await res.json();
        
        container.innerHTML = `<div style="padding:5px; font-weight:bold; border-bottom:1px solid #333; display:flex; justify-content:space-between;">
            <span>Global Results: "${query}" (${results.length})</span>
            <button onclick="refreshFileTree(currentSftpPath)" style="background:none; border:none; color:#aaa; cursor:pointer;" title="Clear"><i class="fa-solid fa-times"></i></button>
        </div>`;
        
        if (results.length === 0) {
            container.innerHTML += '<div style="padding:5px;">No results found</div>';
            return;
        }
        
        const treeRoot = buildTree(results);
        const treeContainer = document.createElement('div');
        createTreeDom(treeRoot, treeContainer, 0);
        container.appendChild(treeContainer);
        
    } catch (e) { 
        console.error(e);
        container.innerHTML = '<div style="padding:10px; color:red;">Search failed</div>'; 
    }
}
