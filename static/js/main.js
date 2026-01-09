// Global State
let session_id = null;
let currentSftpPath = ".";
let currentEditingFile = null;
let allCommands = [];

// Doc Module State
let docState = {
    converter: { headers: [], rows: [], searchMatches: [], currentMatch: -1, page: 1, pageSize: 50, filterQuery: '' },
    diff: { fileA: null, fileB: null, sheetsA: [], sheetsB: [], conditions: [] },
    toolbox: { headers: [], rows: [], page: 1, pageSize: 50, filterQuery: '' }
};

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    initTerminal();
    loadHistory(); // Try to auto-load history
    
    // Monaco Init
    if (typeof monaco !== 'undefined') {
        // Monaco loaded via CDN in index.html, wait for it if needed or configure here
        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' }});
        require(['vs/editor/editor.main'], function() {
            window.editor = monaco.editor.create(document.getElementById('sftp-editor'), {
                value: "// Select a file to edit...",
                language: 'plaintext',
                theme: 'vs-dark',
                automaticLayout: true
            });
            window.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveFile);
        });
    }

    // Global click to hide context menu
    document.addEventListener('click', () => {
        const menu = document.getElementById('context-menu');
        if(menu) menu.classList.add('hidden');
    });
    
    // Cmd input enter
    const cmdInput = document.getElementById('cmd-input');
    if (cmdInput) {
        cmdInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const cmd = e.target.value;
                if (cmd && socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(cmd + '\n');
                    term.focus();
                    e.target.value = '';
                }
            }
        });
    }
});

// --- View Manager ---
function switchView(viewName) {
    document.querySelectorAll('.view-container').forEach(el => {
        el.classList.remove('active');
    });
    const view = document.getElementById('view-' + viewName);
    if(view) view.classList.add('active');
    
    if (viewName === 'ssh' && fitAddon) {
        // Ensure terminal fits the container after view switch
        setTimeout(() => { 
            fitAddon.fit(); 
            term.focus(); 
            sendResize();
        }, 100);
    }
    if (viewName === 'commands') {
        loadCommands();
    }
    if (viewName === 'sftp') {
        // Initial load if first time
        if (document.getElementById('sftp-tree').innerHTML === '') {
            refreshFileTree(currentSftpPath);
        }
    }
}

function handleHomeAction(action) {
    if (action === 'ssh') {
        if (!session_id) {
            showLogin();
        } else {
            switchView('ssh');
        }
    } else if (action === 'doc') {
        switchView('doc');
    }
}

function showLogin() {
    document.getElementById('login-overlay').classList.remove('hidden');
}

// --- Context Menu ---
function showContextMenu(e) {
    e.preventDefault();
    if (!session_id) return;
    const menu = document.getElementById('context-menu');
    menu.style.left = e.pageX + 'px';
    menu.style.top = e.pageY + 'px';
    menu.classList.remove('hidden');
}

function handleMenu(action) {
    if (!session_id) { alert("Please connect first!"); showLogin(); return; }
    switchView(action);
}
