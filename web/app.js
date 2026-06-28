// Tab Navigation
document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Remove active class from all links and tabs
        document.querySelectorAll('.nav-links a').forEach(l => l.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        
        // Add active class to clicked link and corresponding tab
        this.classList.add('active');
        const tabId = this.getAttribute('data-tab');
        document.getElementById(`tab-${tabId}`).classList.add('active');
    });
});

// Socket.IO Connection
const socket = io({
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    reconnectionAttempts: Infinity,
    transports: ['websocket', 'polling']
});

const connStatus = document.getElementById('conn-status');

socket.on('connect', () => {
    connStatus.className = 'connection-status online';
    connStatus.innerHTML = '<i class="fas fa-circle"></i> <span>Đã kết nối</span>';
    addEventLog('system', 'Hệ thống', 'Kết nối thành công tới máy chủ');
    
    // Fetch initial status
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            document.getElementById('sys-uptime').textContent = data.uptime || 'Đang hoạt động';
        })
        .catch(console.error);
        
    // Fetch and populate recent events list
    loadRecentEvents();
});

function fetchDoorStatus(btn = null) {
    if (btn) animateRefreshButton(btn);
    return fetch('/api/status?t=' + new Date().getTime())
        .then(res => res.json())
        .then(data => {
            if (data.status === 'online') {
                mainDoorOpen = (data.main_door === 'open');
                deliveryBoxOpen = (data.delivery_box === 'open');
                
                // Cập nhật text hiển thị tổng quan
                const mainEl = document.getElementById('main-door-status');
                if (mainEl) {
                    mainEl.textContent = mainDoorOpen ? 'Cửa đang mở' : 'Đang khóa';
                    mainEl.style.color = mainDoorOpen ? 'var(--warning-color)' : 'inherit';
                }
                
                const delEl = document.getElementById('delivery-box-status');
                if (delEl) {
                    delEl.textContent = deliveryBoxOpen ? 'Cửa đang mở' : 'Đang khóa';
                    delEl.style.color = deliveryBoxOpen ? 'var(--warning-color)' : 'inherit';
                }
                
                updateButtonStates();
            }
            return { mainDoorOpen, deliveryBoxOpen };
        })
        .catch(err => {
            console.error("Error fetching door status:", err);
            return { mainDoorOpen, deliveryBoxOpen };
        });
}

socket.on('disconnect', () => {
    connStatus.className = 'connection-status offline';
    connStatus.innerHTML = '<i class="fas fa-circle"></i> <span>Mất kết nối</span>';
    addEventLog('error', 'Hệ thống', 'Mất kết nối tới máy chủ');
});

let mainDoorOpen = false;
let deliveryBoxOpen = false;

// Handle real-time door status
socket.on('door_status', (data) => {
    console.log("Door status update:", data);
    const isMainDoor = data.door && data.door.includes('MAIN DOOR');
    const elId = isMainDoor ? 'main-door-status' : 'delivery-box-status';
    const el = document.getElementById(elId);
    
    if (data.status === 'unlocked') {
        el.textContent = 'Đang mở';
        el.style.color = 'var(--success-color)';
        addEventLog('unlock', isMainDoor ? 'MAIN DOOR' : 'DELIVERY BOX', 'Đã mở khóa (App/Web/Mật khẩu)');
        if (isMainDoor) mainDoorOpen = true;
        else deliveryBoxOpen = true;
    } else {
        el.textContent = 'Đang khóa';
        el.style.color = 'inherit';
        addEventLog('lock', isMainDoor ? 'MAIN DOOR' : 'DELIVERY BOX', 'Đã đóng khóa');
        if (isMainDoor) mainDoorOpen = false;
        else deliveryBoxOpen = false;
    }
    
    updateButtonStates();
});

// Handle RFID events
socket.on('rfid_event', (data) => {
    console.log("RFID event:", data);
    let msg = `Thẻ RFID: ${data.detail || 'Không rõ'}`;
    if (data.event === 'rfid_enrolled') {
        msg = `Đã thêm thẻ mới: ${data.detail}`;
        addEventLog('success', 'Đăng ký thẻ', msg);
    } else {
        addEventLog('info', 'Quẹt thẻ', msg);
    }
});

// Handle real-time system events (like physical door open/close)
socket.on('system_event', (data) => {
    console.log("System event:", data);
    const isMainDoor = data.detail && data.detail.includes('MAIN DOOR');
    const isDelivery = data.detail && data.detail.includes('DELIVERY BOX');
    
    if (data.event === 'physical_door_open') {
        if (isMainDoor) mainDoorOpen = true;
        else if (isDelivery) deliveryBoxOpen = true;
        addEventLog('info', isMainDoor ? 'Cửa Chính' : 'Tủ Nhận Đồ', 'Cửa đã được mở ra');
    } else if (data.event === 'physical_door_close') {
        if (isMainDoor) mainDoorOpen = false;
        else if (isDelivery) deliveryBoxOpen = false;
        addEventLog('info', isMainDoor ? 'Cửa Chính' : 'Tủ Nhận Đồ', 'Cửa đã được khép lại');
    }
    updateButtonStates();
    
    // Update the text in the status section
    const elId = isMainDoor ? 'main-door-status' : 'delivery-box-status';
    const el = document.getElementById(elId);
    if (el) {
        if (data.event === 'physical_door_open') {
            el.textContent = 'Cửa đang mở';
            el.style.color = 'var(--warning-color)';
        } else if (data.event === 'physical_door_close') {
            el.textContent = 'Cửa đã khép';
            el.style.color = 'var(--text-secondary)';
        }
    }
});

// Handle Face events
socket.on('face_event', (data) => {
    console.log("Face event:", data);
    addEventLog('face', 'Nhận diện', `Khuôn mặt: ${data.detail || 'Không rõ'}`);
});

// Handle raw logs
socket.on('new_log', (data) => {
    if (data.raw) {
        addEventLog('info', 'System Log', data.raw);
    }
});

function updateButtonStates() {
    const mainUnlockBtn = document.getElementById('btn-main-unlock');
    const mainLockBtn = document.getElementById('btn-main-lock');
    const deliveryUnlockBtn = document.getElementById('btn-delivery-unlock');
    const deliveryLockBtn = document.getElementById('btn-delivery-lock');
    
    if (!mainUnlockBtn) return;

    if (deliveryBoxOpen) {
        mainUnlockBtn.disabled = true;
        mainLockBtn.disabled = true;
        mainUnlockBtn.style.opacity = '0.5';
        mainLockBtn.style.opacity = '0.5';
        mainUnlockBtn.style.cursor = 'not-allowed';
        mainLockBtn.style.cursor = 'not-allowed';
    } else {
        mainUnlockBtn.disabled = false;
        mainLockBtn.disabled = false;
        mainUnlockBtn.style.opacity = '1';
        mainLockBtn.style.opacity = '1';
        mainUnlockBtn.style.cursor = 'pointer';
        mainLockBtn.style.cursor = 'pointer';
    }

    if (mainDoorOpen) {
        deliveryUnlockBtn.disabled = true;
        deliveryLockBtn.disabled = true;
        deliveryUnlockBtn.style.opacity = '0.5';
        deliveryLockBtn.style.opacity = '0.5';
        deliveryUnlockBtn.style.cursor = 'not-allowed';
        deliveryLockBtn.style.cursor = 'not-allowed';
    } else {
        deliveryUnlockBtn.disabled = false;
        deliveryLockBtn.disabled = false;
        deliveryUnlockBtn.style.opacity = '1';
        deliveryLockBtn.style.opacity = '1';
        deliveryUnlockBtn.style.cursor = 'pointer';
        deliveryLockBtn.style.cursor = 'pointer';
    }
}

function addEventLog(type, title, desc, timestamp = null) {
    const list = document.getElementById('event-list');
    
    // Create new element
    const item = document.createElement('div');
    item.className = `event-item ${type}`;
    
    let icon = 'fa-info-circle';
    if (type === 'unlock') icon = 'fa-unlock';
    if (type === 'lock') icon = 'fa-lock';
    if (type === 'rfid') icon = 'fa-id-card';
    if (type === 'face') icon = 'fa-user-check';
    if (type === 'error') icon = 'fa-exclamation-triangle';
    
    const time = timestamp ? new Date(timestamp * 1000).toLocaleTimeString('vi-VN') : new Date().toLocaleTimeString('vi-VN');
    
    item.innerHTML = `
        <div class="event-icon"><i class="fas ${icon}"></i></div>
        <div class="event-desc">
            <strong>${title}</strong>
            <span>${desc}</span>
        </div>
        <div class="event-time">${time}</div>
    `;
    
    // Prepend to list
    list.prepend(item);
    
    // Keep only last 50 items
    if (list.children.length > 50) {
        list.removeChild(list.lastChild);
    }
}

function clearLogs() {
    document.getElementById('event-list').innerHTML = '';
}

function animateRefreshButton(btn) {
    if (!btn) return;
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-check" style="color: var(--success-color);"></i> Đã làm mới';
    setTimeout(() => {
        btn.innerHTML = originalHTML;
    }, 1500);
}

function loadRecentEvents() {
    fetch('/api/history?t=' + new Date().getTime(), { cache: 'no-store' })
        .then(res => res.json())
        .then(data => {
            const list = document.getElementById('event-list');
            if (!list) return;
            
            if (data.history && data.history.length > 0) {
                list.innerHTML = '';
                const recent = data.history.slice(0, 15).reverse();
                recent.forEach(item => {
                    if (item.event === 'rfid_enrolled') return;
                    let type = 'info';
                    let title = 'Sự kiện';
                    let desc = item.detail || '';
                    if (item.event === 'door_unlock') {
                        type = 'unlock';
                        title = item.detail && item.detail.includes('DELIVERY BOX') ? 'Tủ Nhận Đồ' : 'Cửa Chính';
                        desc = 'Đã mở khóa (Web)';
                    } else if (item.event === 'password_unlock') {
                        type = 'unlock';
                        title = item.detail && item.detail.includes('DELIVERY BOX') ? 'Tủ Nhận Đồ' : 'Cửa Chính';
                        desc = 'Đã mở khóa (Mật khẩu)';
                    } else if (item.event === 'door_lock') {
                        type = 'lock';
                        title = item.detail && item.detail.includes('DELIVERY BOX') ? 'Tủ Nhận Đồ' : 'Cửa Chính';
                        desc = 'Đã đóng khóa';
                    } else if (item.event === 'rfid_scan') {
                        type = item.detail && item.detail.includes('matched=false') ? 'error' : 'rfid';
                        title = 'Quẹt thẻ';
                        let name = 'Không rõ';
                        if (item.detail && item.detail.includes('time=')) name = item.detail.split('time=')[1].split(',')[0];
                        desc = type === 'error' ? 'Thẻ RFID từ chối' : `Thẻ hợp lệ: ${name}`;
                    } else if (item.event === 'face_recognized') {
                        type = 'face';
                        title = 'Nhận diện';
                        desc = `Khuôn mặt: ${item.detail}`;
                    } else if (item.event === 'physical_door_open') {
                        type = 'unlock';
                        title = item.detail && item.detail.includes('DELIVERY BOX') ? 'Tủ Nhận Đồ' : 'Cửa Chính';
                        desc = 'Cửa đang mở';
                    } else if (item.event === 'physical_door_close') {
                        type = 'lock';
                        title = item.detail && item.detail.includes('DELIVERY BOX') ? 'Tủ Nhận Đồ' : 'Cửa Chính';
                        desc = 'Cửa đã khép lại';
                    } else if (item.event === 'shipper_unlock') {
                        type = 'unlock';
                        title = 'Tủ Nhận Đồ';
                        desc = `Shipper nhập mã: ${item.detail}`;
                    } else {
                        return;
                    }
                    addEventLog(type, title, desc, item.timestamp);
                });
            }
        });
}

function controlDoor(door, action) {
    if (action === 'unlock') {
        fetchDoorStatus().then(status => {
            if (door === 'main' && status.deliveryBoxOpen) {
                showToast('Lỗi', 'Không thể mở! Tủ Nhận Đồ đang mở. Bạn phải khép chặt Tủ Nhận Đồ trước.', true);
                return;
            }
            if (door === 'delivery' && status.mainDoorOpen) {
                showToast('Lỗi', 'Không thể mở! Cửa Chính đang mở. Bạn phải khép chặt Cửa Chính trước.', true);
                return;
            }
            sendControlCommand(door, action);
        });
    } else {
        sendControlCommand(door, action);
    }
}

function sendControlCommand(door, action) {
    fetch('/api/door/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ door: door, action: action })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            showToast('Thành công', data.message);
            // Optimistic update to prevent double-clicking
            if (action === 'unlock') {
                if (door === 'main') mainDoorOpen = true;
                if (door === 'delivery') deliveryBoxOpen = true;
            } else if (action === 'lock') {
                if (door === 'main') mainDoorOpen = false;
                if (door === 'delivery') deliveryBoxOpen = false;
            }
            // Sync UI optimistically
            const isMain = door === 'main';
            const el = document.getElementById(isMain ? 'main-door-status' : 'delivery-box-status');
            if (action === 'unlock') {
                el.textContent = 'Đang mở';
                el.style.color = 'var(--success-color)';
            } else {
                el.textContent = 'Đang khóa';
                el.style.color = 'inherit';
            }
            updateButtonStates();
        } else {
            showToast('Lỗi', data.message, true);
        }
    })
    .catch(err => {
        console.error(err);
        showToast('Lỗi', 'Không thể kết nối đến máy chủ', true);
    });
}

function showToast(title, message, isError = false) {
    const toast = document.getElementById('toast');
    document.getElementById('toast-title').textContent = title;
    document.getElementById('toast-message').textContent = message;
    
    const icon = toast.querySelector('i');
    if (isError) {
        toast.style.borderLeftColor = 'var(--danger-color)';
        icon.className = 'fas fa-exclamation-circle';
        icon.style.color = 'var(--danger-color)';
    } else {
        toast.style.borderLeftColor = 'var(--success-color)';
        icon.className = 'fas fa-check-circle';
        icon.style.color = 'var(--success-color)';
    }
    
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// --- CARD MANAGEMENT ---
function loadCards() {
    fetch('/api/cards?t=' + new Date().getTime(), { cache: 'no-store' })
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('cards-table-body');
            if (data.cards && data.cards.length > 0) {
                tbody.innerHTML = '';
                data.cards.forEach(card => {
                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid rgba(255,255,255,0.1)';
                    tr.innerHTML = `
                        <td style="padding: 10px;">${card.time}</td>
                        <td style="padding: 10px; font-family: monospace;">${card.uid}</td>
                        <td style="padding: 10px; text-align: right;">
                            <button class="btn btn-sm" style="background: var(--primary-color);" onclick="editCard('${card.uid}', '${card.time}')">
                                <i class="fas fa-edit"></i> Sửa tên
                            </button>
                            <button class="btn btn-sm" style="background: var(--danger-color);" onclick="deleteCard('${card.uid}')">
                                <i class="fas fa-trash"></i> Xóa
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="3" style="padding: 10px; text-align: center;">Chưa có thẻ nào được cấp</td></tr>';
            }
        })
        .catch(err => console.error(err));
}

function editCard(uid, currentName) {
    const newName = prompt('Nhập tên người dùng cho thẻ ' + uid + ':', currentName);
    if (newName && newName.trim() !== '') {
        fetch('/api/cards/' + encodeURIComponent(uid), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                showToast('Thành công', data.message);
                loadCards();
            } else {
                showToast('Lỗi', data.message, true);
            }
        });
    }
}

function deleteCard(uid) {
    if (!confirm('Bạn có chắc chắn muốn thu hồi thẻ ' + uid + '?')) return;
    
    fetch('/api/cards/' + encodeURIComponent(uid), {
        method: 'DELETE'
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            showToast('Thành công', data.message);
            loadCards();
        } else {
            showToast('Lỗi', data.message, true);
        }
    })
    .catch(err => console.error(err));
}

// Load cards automatically when opening the Users tab
document.querySelector('[data-tab="users"]').addEventListener('click', loadCards);

// --- AUTHENTICATION ---
let currentRole = null;

function doLogin() {
    const role = document.getElementById('login-role').value;
    const pwd = document.getElementById('login-password').value;
    
    fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: role, password: pwd })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            currentRole = role;
            document.getElementById('login-overlay').style.display = 'none';
            document.getElementById('main-dashboard').style.display = 'flex';
            
            document.querySelectorAll('.admin-only').forEach(el => {
                el.style.display = role === 'admin' ? 'block' : 'none';
            });
            document.querySelectorAll('.tenant-only').forEach(el => {
                el.style.display = role === 'tenant' ? 'block' : 'none';
            });
            
            document.getElementById('header-role-name').textContent = role === 'admin' ? 'Chủ trọ (Admin)' : 'Người ở trọ';
            
            if (role === 'tenant') {
                document.querySelector('a[data-tab="overview"]').style.display = 'none';
                document.querySelector('a[data-tab="locks"]').style.display = 'none';
                document.querySelector('a[data-tab="users"]').style.display = 'none';
                document.querySelector('a[data-tab="logs"]').style.display = 'none';
                document.querySelector('a[data-tab="delivery"]').click();
            } else {
                document.querySelector('a[data-tab="overview"]').style.display = 'block';
                document.querySelector('a[data-tab="locks"]').style.display = 'block';
                document.querySelector('a[data-tab="users"]').style.display = 'block';
                document.querySelector('a[data-tab="logs"]').style.display = 'block';
                document.querySelector('a[data-tab="overview"]').click();
            }
        } else {
            alert('Sai mật khẩu!');
        }
    })
    .catch(err => alert('Lỗi kết nối: ' + err));
}

function doLogout() {
    currentRole = null;
    document.getElementById('login-password').value = '';
    document.getElementById('login-overlay').style.display = 'flex';
    document.getElementById('main-dashboard').style.display = 'none';
}

// --- DELIVERY CODES ---
function loadDeliveryCodes() {
    fetch('/api/delivery_codes?t=' + new Date().getTime(), { cache: 'no-store' })
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('delivery-codes-body');
            if (data.codes && data.codes.length > 0) {
                tbody.innerHTML = '';
                data.codes.forEach(c => {
                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid rgba(255,255,255,0.1)';
                    tr.innerHTML = `
                        <td style="padding: 10px;">${c.creator}</td>
                        <td style="padding: 10px; font-size: 20px; font-weight: bold; letter-spacing: 2px;">${c.code}</td>
                        <td style="padding: 10px; text-align: right;">
                            <button class="btn btn-sm" style="background: var(--danger-color);" onclick="deleteDeliveryCode('${c.code}')">
                                <i class="fas fa-trash"></i> Xóa
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="3" style="padding: 10px; text-align: center;">Chưa có mã nào</td></tr>';
            }
        });
}

function createDeliveryCode() {
    const code = document.getElementById('new-delivery-code').value;
    const creator = document.getElementById('new-delivery-creator').value;
    if (!code || code.length < 4 || isNaN(code)) {
        showToast('Lỗi', 'Mã phải là số và có ít nhất 4 chữ số', true);
        return;
    }
    fetch('/api/delivery_codes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code, creator: creator })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            showToast('Thành công', data.message);
            document.getElementById('new-delivery-code').value = '';
            document.getElementById('new-delivery-creator').value = '';
            loadDeliveryCodes();
        } else {
            showToast('Lỗi', data.message, true);
        }
    });
}

function deleteDeliveryCode(code) {
    if (!confirm('Xóa mã ' + code + '?')) return;
    fetch('/api/delivery_codes/' + code, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                showToast('Thành công', data.message);
                loadDeliveryCodes();
            }
        });
}

// --- TENANT HISTORY ---
function loadTenantHistory(btn = null) {
    if (btn) animateRefreshButton(btn);
    fetch('/api/history?t=' + new Date().getTime(), { cache: 'no-store' })
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('tenant-history-body');
            if (!tbody) return;
            if (data.history && data.history.length > 0) {
                const deliveryEvents = data.history.filter(item => item.event === 'shipper_unlock');
                if (deliveryEvents.length > 0) {
                    tbody.innerHTML = '';
                    deliveryEvents.forEach(item => {
                        const tr = document.createElement('tr');
                        tr.style.borderBottom = '1px solid rgba(255,255,255,0.1)';
                        const date = new Date(item.timestamp * 1000).toLocaleString('vi-VN');
                        tr.innerHTML = `
                            <td style="padding: 10px;">${date}</td>
                            <td style="padding: 10px; font-weight: bold; color: var(--success-color);">${item.detail || ''}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="2" style="padding: 10px; text-align: center;">Chưa có lịch sử Shipper</td></tr>';
                }
            } else {
                tbody.innerHTML = '<tr><td colspan="2" style="padding: 10px; text-align: center;">Chưa có lịch sử Shipper</td></tr>';
            }
        });
}

document.querySelector('[data-tab="delivery"]').addEventListener('click', () => {
    loadDeliveryCodes();
    loadTenantHistory();
});

// --- ACCESS HISTORY ---
function loadHistory(btn = null) {
    if (btn) animateRefreshButton(btn);
    fetch('/api/history?t=' + new Date().getTime(), { cache: 'no-store' })
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('history-table-body');
            if (data.history && data.history.length > 0) {
                // Pre-process history to remove redundant logs and clean up
                const cleanHistory = [];
                for (let i = 0; i < data.history.length; i++) {
                    const item = data.history[i];
                    
                    // Hide failed scans or enrolls
                    if (item.event === 'rfid_scan' && item.detail && item.detail.includes('matched=false')) continue;
                    if (item.event === 'rfid_enrolled') continue;
                    if (item.event === 'face_recognized' && item.detail && item.detail.includes('TIMEOUT')) continue;
                    
                    if (item.event === 'door_unlock' || item.event === 'password_unlock') {
                        let duplicate = false;
                        if (i + 1 < data.history.length) {
                            const prev = data.history[i + 1];
                            if ((prev.event === 'rfid_scan' || prev.event === 'face_recognized' || prev.event === 'shipper_unlock' || prev.event === 'password_unlock') && 
                                Math.abs(item.timestamp - prev.timestamp) <= 3) {
                                // If the current item is just door_unlock and the prev was password_unlock, skip door_unlock!
                                // If current item is password_unlock and prev was face/rfid... wait, password and face/rfid shouldn't conflict.
                                // Actually, if prev was password_unlock and current is door_unlock, door_unlock is skipped.
                                if (item.event === 'door_unlock') duplicate = true;
                            }
                        }
                        if (duplicate) continue;
                    }

                    // No bounce filtering needed anymore due to NC sensor fix
                    
                    cleanHistory.push(item);
                }

                if (cleanHistory.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="padding: 10px; text-align: center;">Chưa có lịch sử nào hợp lệ</td></tr>';
                    return;
                }

                tbody.innerHTML = '';
                cleanHistory.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid rgba(255,255,255,0.1)';
                    const date = new Date(item.timestamp * 1000).toLocaleString('vi-VN');
                    let eventName = item.event;
                    let detail = item.detail || '';
                    
                    let doorName = 'Cửa Chính'; // Mặc định
                    if (detail.includes('MAIN DOOR')) doorName = 'Cửa Chính';
                    if (detail.includes('DELIVERY BOX')) doorName = 'Tủ Nhận Đồ';
                    if (eventName === 'shipper_unlock') doorName = 'Tủ Nhận Đồ'; // Shipper code always opens delivery box
                    
                    let action = 'Chưa rõ';
                    let method = 'Chưa rõ';
                    let actor = 'UD';

                    if (eventName === 'rfid_scan') {
                        action = 'Mở khóa';
                        method = 'Thẻ RFID';
                        if (detail.includes('time=')) {
                            actor = detail.split('time=')[1].split(',')[0] || 'UD';
                        }
                    }
                    else if (eventName === 'password_unlock') {
                        action = 'Mở khóa';
                        method = 'Mật khẩu';
                        actor = 'Chủ nhà';
                    }
                    else if (eventName === 'face_recognized') {
                        action = 'Mở khóa';
                        method = 'Khuôn mặt';
                        actor = detail || 'UD';
                    }
                    else if (eventName === 'door_unlock') {
                        action = 'Mở khóa';
                        method = 'Web App';
                    }
                    else if (eventName === 'door_lock') {
                        action = 'Tự động khóa';
                        method = 'Hệ thống';
                    }
                    else if (eventName === 'physical_door_open') {
                        action = 'Cửa đang mở';
                        method = 'Cảm biến';
                    }
                    else if (eventName === 'physical_door_close') {
                        action = 'Cửa đã khép lại';
                        method = 'Cảm biến';
                    }
                    else if (eventName === 'shipper_unlock') {
                        action = 'Mở khóa';
                        method = 'Mã Nhận Đồ';
                        actor = detail || 'UD';
                    }
                    
                    // Logic to inherit actor name for sensor and auto-lock events
                    if (actor === 'UD' && (eventName === 'physical_door_open' || eventName === 'physical_door_close' || eventName === 'door_lock')) {
                        // Look forward in the array (older events) to find the most recent unlock within 60 seconds
                        for (let j = cleanHistory.indexOf(item) + 1; j < cleanHistory.length; j++) {
                            const olderEvent = cleanHistory[j];
                            if (item.timestamp - olderEvent.timestamp > 60) break; // Only check last 60 seconds
                            
                            // Make sure the event belongs to the same door
                            let olderDoor = 'Cửa Chính';
                            if (olderEvent.detail && olderEvent.detail.includes('DELIVERY BOX')) olderDoor = 'Tủ Nhận Đồ';
                            if (olderEvent.event === 'shipper_unlock') olderDoor = 'Tủ Nhận Đồ';
                            
                            if (olderDoor === doorName) {
                                if (olderEvent.event === 'rfid_scan') {
                                    if (olderEvent.detail && olderEvent.detail.includes('time=')) {
                                        actor = olderEvent.detail.split('time=')[1].split(',')[0] || 'UD';
                                        break;
                                    }
                                } else if (olderEvent.event === 'face_recognized') {
                                    actor = olderEvent.detail || 'UD';
                                    break;
                                } else if (olderEvent.event === 'shipper_unlock') {
                                    actor = olderEvent.detail || 'UD';
                                    break;
                                } else if (olderEvent.event === 'door_unlock') {
                                    // Web unlock - we don't have a specific name, so maybe keep UD or set something else, but we break anyway
                                    break;
                                }
                            }
                        }
                    }
                    
                    tr.innerHTML = `
                        <td style="padding: 10px;">${date}</td>
                        <td style="padding: 10px; font-weight: bold;">${doorName}</td>
                        <td style="padding: 10px;"><span style="color: ${action.includes('Mở') ? 'var(--primary-color)' : 'var(--danger-color)'}; font-weight: 500;">${action}</span></td>
                        <td style="padding: 10px;"><span class="badge" style="background: rgba(255,255,255,0.1); padding: 5px 10px; border-radius: 5px;">${method}</span></td>
                        <td style="padding: 10px;">${actor}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="5" style="padding: 10px; text-align: center;">Chưa có lịch sử nào</td></tr>';
            }
        });
}

function clearHistory() {
    if (!confirm('Bạn có chắc chắn muốn XÓA TOÀN BỘ lịch sử truy cập không? Hành động này không thể hoàn tác!')) return;
    fetch('/api/history', { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            showToast('Thành công', data.message || 'Đã xóa lịch sử');
            loadHistory();
        })
        .catch(err => {
            showToast('Lỗi', 'Không thể xóa lịch sử', true);
        });
}

document.querySelector('[data-tab="logs"]').addEventListener('click', () => loadHistory());
