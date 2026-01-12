// 简化的自动化模块前端逻辑

// 状态管理
const automationState = {
    isRecording: false,
    currentTaskId: null,
    tasks: [],
    pollingInterval: null
};

// 初始化
function initAutomation() {
    refreshTaskList();
}

// 刷新任务列表
async function refreshTaskList() {
    try {
        const res = await fetch('/api/automation/tasks');
        if (!res.ok) throw new Error('加载失败');
        
        const data = await res.json();
        automationState.tasks = data.tasks;
        renderTaskList(data.tasks);
    } catch (e) {
        console.error('Error loading tasks:', e);
        alert('加载任务失败: ' + e.message);
    }
}

// 渲染任务列表
function renderTaskList(tasks) {
    const container = document.getElementById('task-list');
    
    if (!tasks || tasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-robot" style="font-size: 48px; color: #444; margin-bottom: 15px;"></i>
                <div>暂无任务</div>
                <div style="font-size: 12px; color: #666; margin-top: 5px;">点击"开始录制"创建第一个自动化任务</div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = tasks.map(task => `
        <div class="task-card" data-task-id="${task.id}">
            <div class="task-info">
                <div class="task-name">${escapeHtml(task.name)}</div>
                <div class="task-meta">
                    <span><i class="fa-solid fa-clock"></i> ${task.duration}秒</span>
                    <span><i class="fa-solid fa-list"></i> ${task.event_count}个操作</span>
                    <span><i class="fa-solid fa-calendar"></i> ${formatDate(task.created_at)}</span>
                </div>
            </div>
            <div class="task-actions">
                <button onclick="executeTask('${task.id}')" class="btn-execute" title="执行">
                    <i class="fa-solid fa-play"></i> 执行
                </button>
                <button onclick="editTask('${task.id}')" title="编辑">
                    <i class="fa-solid fa-edit"></i>
                </button>
                <button onclick="renameTask('${task.id}', '${escapeHtml(task.name)}')" title="重命名">
                    <i class="fa-solid fa-pen"></i>
                </button>
                <button onclick="deleteTask('${task.id}')" class="btn-delete" title="删除">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

// 开始录制
async function startRecording() {
    try {
        // 获取是否记录鼠标轨迹
        const recordMouseMove = document.getElementById('record-mouse-move')?.checked || false;
        
        const res = await fetch('/api/automation/start-recording', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ record_mouse_move: recordMouseMove })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '启动录制失败');
        }
        
        const data = await res.json();
        automationState.isRecording = true;
        automationState.currentTaskId = data.task_id;
        
        // 显示录制状态
        document.getElementById('recording-overlay').style.display = 'flex';
        
        // 开始轮询录制状态
        startStatusPolling();
        
    } catch (e) {
        alert('启动录制失败: ' + e.message);
    }
}

// 轮询录制状态
function startStatusPolling() {
    automationState.pollingInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/automation/recording-status');
            const data = await res.json();
            
            if (!data.is_recording && automationState.isRecording) {
                // 录制已停止（ESC键停止）
                document.getElementById('recording-overlay').style.display = 'none';
                automationState.isRecording = false;
                stopStatusPolling();
                
                // 刷新任务列表
                await refreshTaskList();
                
                // 显示保存通知
                if (data.just_saved && data.saved_task) {
                    alert(`录制完成！已保存: ${data.saved_task.name}`);
                }
            }
        } catch (e) {
            console.error('Status polling error:', e);
        }
    }, 200);  // 每200ms轮询一次
}

function stopStatusPolling() {
    if (automationState.pollingInterval) {
        clearInterval(automationState.pollingInterval);
        automationState.pollingInterval = null;
    }
}

// 停止录制
async function stopRecording() {
    try {
        // 停止轮询
        stopStatusPolling();
        
        const res = await fetch('/api/automation/stop-recording', { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '停止录制失败');
        }
        
        const data = await res.json();
        
        // 隐藏录制状态
        document.getElementById('recording-overlay').style.display = 'none';
        
        // 重置状态
        automationState.isRecording = false;
        automationState.currentTaskId = null;
        
        // 刷新任务列表
        await refreshTaskList();
        
        // 显示保存通知
        if (data.task) {
            alert(`录制完成！已保存: ${data.task.name}`);
        }
        
    } catch (e) {
        alert('停止录制失败: ' + e.message);
    }
}

// 执行任务 - 打开设置对话框
async function executeTask(taskId) {
    automationState.executeTaskId = taskId;
    document.getElementById('exec-speed').value = '1';
    document.getElementById('exec-loop').value = '1';
    document.getElementById('execute-modal').style.display = 'flex';
}

// 关闭执行设置对话框
function closeExecuteModal() {
    document.getElementById('execute-modal').style.display = 'none';
    automationState.executeTaskId = null;
}

// 确认执行
async function confirmExecute() {
    const taskId = automationState.executeTaskId;
    const speed = parseFloat(document.getElementById('exec-speed').value) || 1;
    const loopCount = parseInt(document.getElementById('exec-loop').value) || 1;
    
    closeExecuteModal();
    
    try {
        const res = await fetch(`/api/automation/task/${taskId}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                speed: speed,
                loop_count: loopCount
            })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '执行失败');
        }
        
        console.log(`任务开始执行，速度${speed}x，循环${loopCount}次`);
        
    } catch (e) {
        alert('执行失败: ' + e.message);
    }
}

// 重命名任务
function renameTask(taskId, currentName) {
    automationState.selectedTaskId = taskId;
    document.getElementById('task-new-name').value = currentName;
    document.getElementById('task-rename-modal').style.display = 'flex';
}

async function confirmRename() {
    const newName = document.getElementById('task-new-name').value.trim();
    if (!newName) {
        alert('请输入任务名称');
        return;
    }
    
    try {
        const res = await fetch(`/api/automation/task/${automationState.selectedTaskId}/rename`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '重命名失败');
        }
        
        closeRenameModal();
        await refreshTaskList();
        
    } catch (e) {
        alert('重命名失败: ' + e.message);
    }
}

function closeRenameModal() {
    document.getElementById('task-rename-modal').style.display = 'none';
    automationState.selectedTaskId = null;
}

// 删除任务
async function deleteTask(taskId) {
    if (!confirm('确定要删除此任务吗？此操作不可恢复。')) {
        return;
    }
    
    try {
        const res = await fetch(`/api/automation/task/${taskId}`, {
            method: 'DELETE'
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '删除失败');
        }
        
        await refreshTaskList();
        
    } catch (e) {
        alert('删除失败: ' + e.message);
    }
}

// 编辑任务
async function editTask(taskId) {
    try {
        const res = await fetch(`/api/automation/task/${taskId}`);
        if (!res.ok) throw new Error('获取任务失败');
        
        const task = await res.json();
        automationState.editingTask = task;
        
        renderTaskEditor(task);
        document.getElementById('task-edit-modal').style.display = 'flex';
    } catch (e) {
        alert('加载任务失败: ' + e.message);
    }
}

// 渲染任务编辑器
function renderTaskEditor(task) {
    const container = document.getElementById('event-list');
    
    if (!task.events || task.events.length === 0) {
        container.innerHTML = '<div class="empty-events">暂无事件</div>';
        return;
    }
    
    container.innerHTML = task.events.map((event, index) => `
        <div class="event-item" data-index="${index}">
            <div class="event-index">${index + 1}</div>
            <div class="event-icon">${getEventIcon(event.type)}</div>
            <div class="event-info">
                <div class="event-type">${getEventTypeName(event.type)}</div>
                <div class="event-detail">${getEventDetail(event)}</div>
            </div>
            <div class="event-time">${event.time.toFixed(2)}s</div>
            <div class="event-actions">
                <button onclick="editEvent(${index})" title="编辑"><i class="fa-solid fa-pen"></i></button>
                <button onclick="deleteEvent(${index})" title="删除"><i class="fa-solid fa-trash"></i></button>
            </div>
        </div>
    `).join('');
}

// 获取事件图标
function getEventIcon(type) {
    const icons = {
        'mouse_click': '<i class="fa-solid fa-mouse" style="color:#4caf50"></i>',
        'mouse_move': '<i class="fa-solid fa-arrows-alt" style="color:#2196f3"></i>',
        'mouse_scroll': '<i class="fa-solid fa-arrows-up-down" style="color:#ff9800"></i>',
        'key_press': '<i class="fa-solid fa-keyboard" style="color:#9c27b0"></i>',
        'key_release': '<i class="fa-solid fa-keyboard" style="color:#607d8b"></i>',
        'wait': '<i class="fa-solid fa-clock" style="color:#795548"></i>',
        'input_text': '<i class="fa-solid fa-font" style="color:#e91e63"></i>'
    };
    return icons[type] || '<i class="fa-solid fa-question"></i>';
}

// 获取事件类型名称
function getEventTypeName(type) {
    const names = {
        'mouse_click': '鼠标点击',
        'mouse_move': '鼠标移动',
        'mouse_scroll': '鼠标滚轮',
        'key_press': '按键按下',
        'key_release': '按键释放',
        'wait': '等待',
        'input_text': '输入文本'
    };
    return names[type] || type;
}

// 获取事件详情
function getEventDetail(event) {
    switch (event.type) {
        case 'mouse_click':
            return `${event.button}键 ${event.pressed ? '按下' : '释放'} (${event.x}, ${event.y})`;
        case 'mouse_move':
            return `移动到 (${event.x}, ${event.y})`;
        case 'mouse_scroll':
            return `滚动 ${event.dy > 0 ? '↑' : '↓'} (${event.x}, ${event.y})`;
        case 'key_press':
            return `按下 [${event.key}]`;
        case 'key_release':
            return `释放 [${event.key}]`;
        case 'wait':
            return `等待 ${event.duration}秒`;
        case 'input_text':
            return `输入: ${event.text}`;
        default:
            return JSON.stringify(event);
    }
}

// 关闭编辑对话框
function closeEditModal() {
    document.getElementById('task-edit-modal').style.display = 'none';
    automationState.editingTask = null;
}

// 保存任务
async function saveTask() {
    const task = automationState.editingTask;
    if (!task) return;
    
    try {
        const res = await fetch(`/api/automation/task/${task.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(task)
        });
        
        if (!res.ok) throw new Error('保存失败');
        
        closeEditModal();
        await refreshTaskList();
        alert('保存成功');
    } catch (e) {
        alert('保存失败: ' + e.message);
    }
}

// 删除事件
function deleteEvent(index) {
    if (!confirm('确定删除此步骤？')) return;
    
    automationState.editingTask.events.splice(index, 1);
    renderTaskEditor(automationState.editingTask);
}

// 编辑事件
function editEvent(index) {
    const event = automationState.editingTask.events[index];
    automationState.editingEventIndex = index;
    
    // 填充编辑表单
    document.getElementById('event-type').value = event.type;
    document.getElementById('event-time').value = event.time.toFixed(2);
    updateEventForm(event.type, event);
    
    document.getElementById('event-edit-modal').style.display = 'flex';
}

// 更新事件编辑表单
function updateEventForm(type, event = {}) {
    const container = document.getElementById('event-params');
    
    let html = '';
    switch (type) {
        case 'mouse_click':
            html = `
                <div class="param-row">
                    <label>X坐标</label>
                    <input type="number" id="param-x" value="${event.x || 0}">
                </div>
                <div class="param-row">
                    <label>Y坐标</label>
                    <input type="number" id="param-y" value="${event.y || 0}">
                </div>
                <div class="param-row">
                    <label>按键</label>
                    <select id="param-button">
                        <option value="left" ${event.button === 'left' ? 'selected' : ''}>左键</option>
                        <option value="right" ${event.button === 'right' ? 'selected' : ''}>右键</option>
                        <option value="middle" ${event.button === 'middle' ? 'selected' : ''}>中键</option>
                    </select>
                </div>
                <div class="param-row">
                    <label>动作</label>
                    <select id="param-pressed">
                        <option value="true" ${event.pressed ? 'selected' : ''}>按下</option>
                        <option value="false" ${!event.pressed ? 'selected' : ''}>释放</option>
                    </select>
                </div>
            `;
            break;
        case 'mouse_move':
            html = `
                <div class="param-row">
                    <label>X坐标</label>
                    <input type="number" id="param-x" value="${event.x || 0}">
                </div>
                <div class="param-row">
                    <label>Y坐标</label>
                    <input type="number" id="param-y" value="${event.y || 0}">
                </div>
            `;
            break;
        case 'key_press':
        case 'key_release':
            html = `
                <div class="param-row">
                    <label>按键</label>
                    <input type="text" id="param-key" value="${event.key || ''}" placeholder="如: a, enter, ctrl">
                </div>
            `;
            break;
        case 'wait':
            html = `
                <div class="param-row">
                    <label>等待时间(秒)</label>
                    <input type="number" id="param-duration" value="${event.duration || 1}" step="0.1" min="0.1">
                </div>
            `;
            break;
        case 'input_text':
            html = `
                <div class="param-row">
                    <label>输入文本</label>
                    <input type="text" id="param-text" value="${event.text || ''}" placeholder="要输入的文本">
                </div>
            `;
            break;
        case 'mouse_scroll':
            html = `
                <div class="param-row">
                    <label>X坐标</label>
                    <input type="number" id="param-x" value="${event.x || 0}">
                </div>
                <div class="param-row">
                    <label>Y坐标</label>
                    <input type="number" id="param-y" value="${event.y || 0}">
                </div>
                <div class="param-row">
                    <label>滚动量</label>
                    <input type="number" id="param-dy" value="${event.dy || 0}">
                </div>
            `;
            break;
    }
    
    container.innerHTML = html;
}

// 关闭事件编辑对话框
function closeEventEditModal() {
    document.getElementById('event-edit-modal').style.display = 'none';
    automationState.editingEventIndex = null;
}

// 保存事件
function saveEvent() {
    const index = automationState.editingEventIndex;
    const type = document.getElementById('event-type').value;
    const time = parseFloat(document.getElementById('event-time').value) || 0;
    
    let event = { type, time };
    
    switch (type) {
        case 'mouse_click':
            event.x = parseInt(document.getElementById('param-x').value) || 0;
            event.y = parseInt(document.getElementById('param-y').value) || 0;
            event.button = document.getElementById('param-button').value;
            event.pressed = document.getElementById('param-pressed').value === 'true';
            break;
        case 'mouse_move':
            event.x = parseInt(document.getElementById('param-x').value) || 0;
            event.y = parseInt(document.getElementById('param-y').value) || 0;
            break;
        case 'key_press':
        case 'key_release':
            event.key = document.getElementById('param-key').value;
            break;
        case 'wait':
            event.duration = parseFloat(document.getElementById('param-duration').value) || 1;
            break;
        case 'input_text':
            event.text = document.getElementById('param-text').value;
            break;
        case 'mouse_scroll':
            event.x = parseInt(document.getElementById('param-x').value) || 0;
            event.y = parseInt(document.getElementById('param-y').value) || 0;
            event.dy = parseInt(document.getElementById('param-dy').value) || 0;
            break;
    }
    
    if (index !== null && index !== undefined) {
        automationState.editingTask.events[index] = event;
    } else {
        automationState.editingTask.events.push(event);
    }
    
    closeEventEditModal();
    renderTaskEditor(automationState.editingTask);
}

// 添加新步骤
function addNewEvent() {
    automationState.editingEventIndex = null;
    
    const lastEvent = automationState.editingTask.events[automationState.editingTask.events.length - 1];
    const newTime = lastEvent ? lastEvent.time + 0.5 : 0;
    
    document.getElementById('event-type').value = 'wait';
    document.getElementById('event-time').value = newTime.toFixed(2);
    updateEventForm('wait', { duration: 1 });
    
    document.getElementById('event-edit-modal').style.display = 'flex';
}

// 工具函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}