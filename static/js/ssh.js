// --- SSH & Terminal ---
let term, socket, fitAddon;

function initTerminal() {
    if (typeof Terminal === 'undefined') {
        console.error("xterm.js failed to load");
        return;
    }
    term = new Terminal({
        cursorBlink: true, fontSize: 14, fontFamily: 'Menlo, Monaco, monospace',
        theme: { background: '#000000' }
    });
    
    // FitAddon Logic
    let FitAddonClass;
    if (typeof FitAddon === 'object' && FitAddon.FitAddon) FitAddonClass = FitAddon.FitAddon;
    else if (typeof FitAddon === 'function') FitAddonClass = FitAddon;
    else { console.error("FitAddon missing"); return; }

    fitAddon = new FitAddonClass();
    term.loadAddon(fitAddon);
    term.open(document.getElementById('terminal-container'));
    fitAddon.fit();
    
    new ResizeObserver(() => {
        try { fitAddon.fit(); sendResize(); } catch(e){}
    }).observe(document.getElementById('terminal-container'));
    
    term.onData(data => {
        if (socket && socket.readyState === WebSocket.OPEN) socket.send(data);
    });
}

async function loadHistory() {
    try {
        const res = await fetch('/api/history');
        const data = await res.json();
        if (data.hostname) {
            document.getElementById('login-host').value = data.hostname;
            document.getElementById('login-user').value = data.username;
            document.getElementById('login-pass').value = data.password;
            document.getElementById('login-port').value = data.port || 22;
            updateHostInfo(data);
        }
    } catch (e) {}
}

async function connectSSH() {
    const host = document.getElementById('login-host').value;
    const user = document.getElementById('login-user').value;
    const pass = document.getElementById('login-pass').value;
    const port = document.getElementById('login-port').value;

    if(!host || !user || !pass) { alert("Please fill all fields"); return; }

    const btn = document.querySelector('#login-overlay .btn-primary');
    const originalText = btn.innerText;
    btn.innerText = "Connecting...";
    btn.disabled = true;

    try {
        const res = await fetch('/api/connect', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ hostname: host, username: user, password: pass, port: parseInt(port) })
        });
        const data = await res.json();
        if (res.ok) {
            session_id = data.session_id;
            document.getElementById('login-overlay').classList.add('hidden');
            
            // Save history
            fetch('/api/history', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ hostname: host, username: user, password: pass, port: parseInt(port) })
            });

            updateHostInfo({hostname: host, username: user});
            startWebSocket();
            switchView('ssh');
        } else {
            alert("Connection failed: " + data.detail);
        }
    } catch (e) { alert("Error: " + e.message); }
    finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

function startWebSocket() {
    if (socket) {
        socket.onclose = null;
        socket.close();
    }
    term.reset();
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${protocol}://${window.location.host}/ws/ssh/${session_id}`);
    socket.onopen = () => { 
        term.write('\r\n\x1b[32mConnected to ' + document.getElementById('host-display-ip').innerText + '...\x1b[0m\r\n'); 
        sendResize(); 
    };
    socket.onmessage = (e) => term.write(e.data);
    socket.onclose = () => term.write('\r\n\x1b[31mConnection Closed.\x1b[0m\r\n');
    socket.onerror = () => term.write('\r\n\x1b[31mWebSocket Error.\x1b[0m\r\n');
}

function reconnectTerminal() {
    if (!session_id) {
        alert("No active session. Please connect via Home first.");
        return;
    }
    startWebSocket();
}

function disconnectTerminal() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
    } else {
        term.write('\r\n\x1b[33mAlready disconnected.\x1b[0m\r\n');
    }
}

function sendResize() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
    }
}

function updateHostInfo(info) {
    document.getElementById('host-display-ip').innerText = info.hostname;
    document.getElementById('host-display-user').innerText = info.username;
}

// --- Command Library Logic ---
async function loadCommands() {
    if (allCommands.length > 0) return; 
    const listEl = document.getElementById('cmd-list');
    listEl.innerHTML = '<div style="padding:20px; color:#aaa;"><i class="fa-solid fa-spinner fa-spin"></i> Loading commands...</div>';
    
    try {
        const res = await fetch('/api/config/commands');
        if (!res.ok) throw new Error("API Error");
        allCommands = await res.json();
        
        if (allCommands.length === 0) {
            listEl.innerHTML = '<div style="padding:20px; color:#aaa;">No commands found in config/kali_commands.json</div>';
            return;
        }
        renderCommands(allCommands);
    } catch (e) { 
        console.error(e);
        listEl.innerHTML = `<div style="padding:20px; color:red;">Failed to load commands: ${e.message}</div>`;
    }
}

function renderCommands(commands) {
    const categories = ['All', ...new Set(commands.map(c => c.category || 'Uncategorized'))];
    const catContainer = document.getElementById('cmd-category-list');
    
    let html = `<div class="category-header"><i class="fa-solid fa-list"></i> CATEGORIES</div>`;
    html += `<div class="category-scroll">`;
    
    categories.forEach(cat => {
        const count = cat === 'All' ? commands.length : commands.filter(c => (c.category || 'Uncategorized') === cat).length;
        html += `
            <div class="category-item" onclick="filterByCategory('${cat}')">
                <span>${cat}</span>
                <span class="category-badge">${count}</span>
            </div>`;
    });
    html += `</div>`;
    
    catContainer.innerHTML = html;
    filterByCategory('All');
}

function filterByCategory(cat) {
    document.querySelectorAll('.category-item').forEach(el => {
        const name = el.querySelector('span').innerText;
        el.classList.toggle('active', name === cat);
    });
    
    document.getElementById('cmd-current-category').innerText = cat;
    
    let filtered;
    if (cat === 'All') filtered = allCommands;
    else filtered = allCommands.filter(c => (c.category || 'Uncategorized') === cat);
    
    renderCommandList(filtered);
}

function filterCommands(query) {
    if (!query) {
        const activeCat = document.querySelector('.category-item.active span').innerText;
        filterByCategory(activeCat);
        return;
    }
    const filtered = allCommands.filter(c => 
        c.command.toLowerCase().includes(query.toLowerCase()) || 
        c.description.toLowerCase().includes(query.toLowerCase())
    );
    renderCommandList(filtered);
}

function renderCommandList(list) {
    const container = document.getElementById('cmd-list');
    if (list.length === 0) {
        container.innerHTML = '<div style="color:#666; text-align:center; margin-top:50px;">No commands found</div>';
        return;
    }
    
    container.innerHTML = list.map(cmd => {
        const safeCmd = cmd.command.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        return `
        <div class="cmd-card">
            <div class="cmd-card-header">
                <div class="cmd-code-wrap">${cmd.command}</div>
                <div class="cmd-actions">
                    <button class="action-btn" onclick="copyCommand('${safeCmd}')"><i class="fa-solid fa-copy"></i> Copy</button>
                    <button class="action-btn run" onclick="executeCommand('${safeCmd}')"><i class="fa-solid fa-play"></i> Run</button>
                </div>
            </div>
            <div class="cmd-card-body">
                <div style="color:#888; font-size:12px; margin-bottom:5px;">${cmd.category || 'General'}</div>
                ${cmd.description}
            </div>
        </div>
    `}).join('');
}

function executeCommand(cmd) {
    switchView('ssh');
    const input = document.getElementById('cmd-input');
    input.value = cmd;
    input.focus();
}

function copyCommand(cmd) {
    navigator.clipboard.writeText(cmd);
}
