// ── DNS Messenger — Telegram-style Frontend ─────────────────────────

const socket = io();

// ── Color palette for avatars ───────────────────────────────────────
const AVATAR_COLORS = [
    ['#8774e1', '#6c5bbf'], ['#4dcd5e', '#37a34a'], ['#e05d5d', '#b94545'],
    ['#e8a63a', '#c48a2e'], ['#3ea6e1', '#2d85b8'], ['#e06bb0', '#b8508f'],
    ['#6ec4db', '#4fa3b8'], ['#b37de0', '#8f5fbf'], ['#e08d6e', '#b8704f'],
    ['#4dc4c4', '#37a3a3'],
];

function hashStr(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    return Math.abs(h);
}

function avatarColor(name) {
    return AVATAR_COLORS[hashStr(name) % AVATAR_COLORS.length];
}

function avatarHtml(name, isGroup, size) {
    const sz = size || '';
    const colors = avatarColor(name);
    const initial = isGroup ? '#' : name[0].toUpperCase();
    return `<div class="avatar ${sz}" style="background:linear-gradient(135deg,${colors[0]},${colors[1]})">${initial}</div>`;
}

// ── State ───────────────────────────────────────────────────────────
const state = {
    currentChat: null,
    chats: {},
    username: document.body.dataset.username,
    activeTab: 'all',
    knownUsers: [],
};

// ── DOM refs ────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $chatList    = $('#chat-list');
const $chatHeader  = $('#chat-header');
const $messages    = $('#messages');
const $inputArea   = $('#input-area');
const $noChat      = $('#no-chat');
const $msgInput    = $('#msg-input');
const $sendBtn     = $('#send-btn');
const $fileInput   = $('#file-input');
const $searchInput = $('#search-input');
const $toasts      = $('#toast-container');
const $notifs      = $('#notifications');

// ── Toast notifications ─────────────────────────────────────────────
function toast(text, type = 'info') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = text;
    $toasts.appendChild(el);
    setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 300); }, 3000);
}

// ── localStorage persistence ────────────────────────────────────────
const STORAGE_KEY = () => `dns_messenger_${state.username}`;

function saveState() {
    if (!state.username) return;
    try {
        const data = {};
        for (const [id, chat] of Object.entries(state.chats)) {
            data[id] = { type: chat.type, name: chat.name, messages: chat.messages, lastTs: chat.lastTs };
        }
        localStorage.setItem(STORAGE_KEY(), JSON.stringify(data));
    } catch (e) {}
}

function loadState() {
    if (!state.username) return;
    try {
        const raw = localStorage.getItem(STORAGE_KEY());
        if (!raw) return;
        const data = JSON.parse(raw);
        for (const [id, chat] of Object.entries(data)) {
            state.chats[id] = { ...chat, unread: 0 };
        }
    } catch (e) {}
}

// ── Chat management ─────────────────────────────────────────────────
function ensureChat(id, type, name) {
    if (!state.chats[id]) {
        state.chats[id] = { type, name: name || id, messages: [], unread: 0, lastTs: 0 };
    }
    return state.chats[id];
}

function addMessage(chatId, msg) {
    const chat = state.chats[chatId];
    if (!chat) return;
    // Assign unique ID if not present
    if (!msg.id) msg.id = `${msg.ts}_${Math.random().toString(36).slice(2, 8)}`;
    chat.messages.push(msg);
    chat.lastTs = msg.ts;
    saveState();
}

function selectChat(id) {
    const chat = state.chats[id];
    if (!chat) return;
    state.currentChat = { type: chat.type, id };
    chat.unread = 0;
    saveState();
    renderChatList();
    renderMessages();
    renderHeader();
    $noChat.style.display = 'none';
    $chatHeader.style.display = '';
    $messages.style.display = '';
    $inputArea.style.display = '';
    document.body.classList.add('chat-open');
    $msgInput.focus();
}

function goBack() {
    state.currentChat = null;
    document.body.classList.remove('chat-open');
    $chatHeader.style.display = 'none';
    $messages.style.display = 'none';
    $inputArea.style.display = 'none';
    $noChat.style.display = '';
    renderChatList();
}

// ── Tabs ────────────────────────────────────────────────────────────
function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            state.activeTab = tab.dataset.tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            renderChatList();
        });
    });
}

function updateBadges() {
    let allCount = 0, dmCount = 0, groupCount = 0;
    for (const chat of Object.values(state.chats)) {
        if (chat.unread > 0) {
            allCount += chat.unread;
            if (chat.type === 'dm') dmCount += chat.unread;
            else groupCount += chat.unread;
        }
    }
    setBadge('badge-all', allCount);
    setBadge('badge-dm', dmCount);
    setBadge('badge-group', groupCount);
}

function setBadge(id, count) {
    const el = document.getElementById(id);
    if (!el) return;
    if (count > 0) {
        el.textContent = count;
        el.style.display = '';
    } else {
        el.style.display = 'none';
    }
}

// ── Render: Chat List ───────────────────────────────────────────────
function renderChatList() {
    const filter = ($searchInput?.value || '').toLowerCase();
    const entries = Object.entries(state.chats)
        .filter(([id, c]) => {
            if (filter && !c.name.toLowerCase().includes(filter)) return false;
            if (state.activeTab === 'dm') return c.type === 'dm';
            if (state.activeTab === 'group') return c.type === 'group';
            return true;
        })
        .sort((a, b) => b[1].lastTs - a[1].lastTs);

    $chatList.innerHTML = '';
    for (const [id, chat] of entries) {
        const isActive = state.currentChat?.id === id;
        const isGroup = chat.type === 'group';
        const lastMsg = chat.messages[chat.messages.length - 1];
        let preview = '';
        if (lastMsg) {
            if (lastMsg.system) preview = lastMsg.text;
            else if (lastMsg.file) preview = '\uD83D\uDCCE ' + lastMsg.file;
            else {
                const sender = lastMsg.from === state.username ? 'You: ' : (isGroup ? lastMsg.from + ': ' : '');
                preview = sender + (lastMsg.text || '');
            }
        }
        const timeStr = lastMsg ? formatTime(lastMsg.ts) : '';

        const div = document.createElement('div');
        div.className = `chat-item${isActive ? ' active' : ''}`;
        div.onclick = () => selectChat(id);
        div.innerHTML = `
            ${avatarHtml(chat.name, isGroup)}
            <div class="chat-info">
                <div class="chat-name-row">
                    <span class="chat-name">${esc(chat.name)}</span>
                </div>
                <div class="chat-preview">${esc(preview.slice(0, 80))}</div>
            </div>
            <div class="chat-meta">
                <span class="chat-time">${timeStr}</span>
                ${chat.unread ? `<span class="unread-badge">${chat.unread}</span>` : ''}
            </div>
        `;
        $chatList.appendChild(div);
    }
    updateBadges();
}

// ── Render: Header ──────────────────────────────────────────────────
function renderHeader() {
    if (!state.currentChat) return;
    const chat = state.chats[state.currentChat.id];
    if (!chat) return;
    const isGroup = chat.type === 'group';

    $chatHeader.innerHTML = `
        <button class="mobile-back" onclick="goBack()">&#x2190;</button>
        ${avatarHtml(chat.name, isGroup, 'sm')}
        <div class="header-info">
            <div class="chat-title">${esc(chat.name)}</div>
            <div class="chat-subtitle">
                <span class="online-dot"></span>
                ${isGroup ? 'E2E group \u00b7 DNS Tunnel' : 'E2E encrypted \u00b7 DNS Tunnel'}
            </div>
        </div>
        <div class="header-actions">
            ${!isGroup ? `
                <button onclick="startCall(false)" title="Voice call">&#x1F4DE;</button>
                <button onclick="startCall(true)" title="Video call">&#x1F4F9;</button>
            ` : ''}
            ${isGroup ? `<button class="invite-btn" onclick="showInviteModal()">+ Member</button>` : ''}
        </div>
    `;
}

// ── Render: Messages ────────────────────────────────────────────────
function renderMessages() {
    if (!state.currentChat) return;
    const chat = state.chats[state.currentChat.id];
    if (!chat) return;
    const isGroup = chat.type === 'group';
    $messages.innerHTML = '';

    let lastSender = null;
    let lastDate = null;

    for (const msg of chat.messages) {
        const msgDate = new Date(msg.ts).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
        if (msgDate !== lastDate) {
            lastDate = msgDate;
            const sep = document.createElement('div');
            sep.className = 'date-separator';
            sep.innerHTML = `<span>${msgDate}</span>`;
            $messages.appendChild(sep);
        }

        if (msg.system) {
            const sys = document.createElement('div');
            sys.className = 'system-msg';
            sys.innerHTML = `<span>${esc(msg.text)}</span>`;
            $messages.appendChild(sys);
            lastSender = null;
            continue;
        }

        const isMine = msg.from === state.username;
        const isNew = msg.from !== lastSender;
        lastSender = msg.from;

        const div = document.createElement('div');

        // Skip deleted messages or show placeholder
        if (msg.deleted) {
            div.className = `message ${isMine ? 'sent' : 'received'} deleted${isNew ? ' first' : ''}`;
            div.innerHTML = `<div class="msg-text">Message deleted<span class="msg-footer">
                <span class="msg-time">${formatTime(msg.ts)}</span>
            </span></div>`;
            $messages.appendChild(div);
            continue;
        }

        // Data attributes for context menu
        div.dataset.msgId = msg.id || '';
        div.dataset.chatId = state.currentChat.id;

        const reactionsHtml = renderReactions(msg);

        if (msg.voice) {
            // Voice message
            div.className = `message ${isMine ? 'sent' : 'received'}${isNew ? ' first' : ''}`;
            const dur = msg.duration || 0;
            const durStr = Math.floor(dur / 60) + ':' + (dur % 60).toString().padStart(2, '0');
            const bars = [];
            const seed = hashStr(msg.file || '' + msg.ts);
            for (let i = 0; i < 28; i++) {
                const h = 6 + ((seed * (i + 1) * 7) % 22);
                bars.push(`<div class="bar" style="height:${h}px"></div>`);
            }
            div.innerHTML = `
                ${!isMine && isGroup && isNew ? `<div class="sender" style="color:${avatarColor(msg.from)[0]}">${esc(msg.from)}</div>` : ''}
                <div class="voice-msg" data-fid="${msg.fid || ''}" data-from="${esc(msg.from)}" data-file="${esc(msg.file)}">
                    <button class="voice-play-btn" onclick="playVoice(this)">&#x25B6;</button>
                    <div class="voice-wave">${bars.join('')}</div>
                    <span class="voice-duration">${durStr}</span>
                </div>
                <div class="msg-footer">
                    <span class="msg-time">${formatTime(msg.ts)}</span>
                    ${isMine ? '<span class="msg-status">&#x2713;&#x2713;</span>' : ''}
                </div>
                ${reactionsHtml}
            `;
        } else if (msg.file) {
            div.className = `message ${isMine ? 'sent' : 'received'} file-msg${isNew ? ' first' : ''}`;
            div.innerHTML = `
                <div class="file-icon-wrap">&#x1F4C4;</div>
                <div class="file-details">
                    ${!isMine && isGroup && isNew ? `<div class="sender" style="color:${avatarColor(msg.from)[0]}">${esc(msg.from)}</div>` : ''}
                    <div class="file-name">${esc(msg.file)}</div>
                    <div class="file-size">${formatSize(msg.size)}</div>
                </div>
                ${reactionsHtml}
            `;
            if (msg.fid && !isMine) {
                div.onclick = () => downloadFile(msg.fid, msg.from, msg.file);
                div.title = 'Click to download';
            }
        } else {
            div.className = `message ${isMine ? 'sent' : 'received'}${isNew ? ' first' : ''}`;
            div.innerHTML = `
                ${!isMine && isGroup && isNew ? `<div class="sender" style="color:${avatarColor(msg.from)[0]}">${esc(msg.from)}</div>` : ''}
                <div class="msg-text">${esc(msg.text)}<span class="msg-footer">
                    <span class="msg-time">${formatTime(msg.ts)}</span>
                    ${isMine ? '<span class="msg-status">&#x2713;&#x2713;</span>' : ''}
                </span></div>
                ${reactionsHtml}
            `;
        }

        // Context menu on right-click and long-press
        div.addEventListener('contextmenu', (e) => { e.preventDefault(); showContextMenu(e, msg); });
        let longPressTimer;
        div.addEventListener('touchstart', (e) => {
            longPressTimer = setTimeout(() => { showContextMenu(e.touches[0], msg); }, 500);
        }, { passive: true });
        div.addEventListener('touchend', () => clearTimeout(longPressTimer));
        div.addEventListener('touchmove', () => clearTimeout(longPressTimer));

        $messages.appendChild(div);
    }

    requestAnimationFrame(() => {
        $messages.scrollTop = $messages.scrollHeight;
    });
}

// ── Actions ─────────────────────────────────────────────────────────
async function sendMessage() {
    if (!state.currentChat || !$msgInput.value.trim()) return;
    const text = $msgInput.value.trim();
    $msgInput.value = '';
    $msgInput.style.height = 'auto';

    const chat = state.chats[state.currentChat.id];
    const ts = Date.now();
    addMessage(state.currentChat.id, { from: state.username, text, ts });
    renderMessages();
    renderChatList();

    const url = chat.type === 'group' ? '/api/groups/send' : '/api/send';
    const body = chat.type === 'group'
        ? { group: state.currentChat.id, text }
        : { to: state.currentChat.id, text };

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        }).then(r => r.json());

        if (!res.ok) toast(res.error || 'Send error', 'error');
    } catch (e) {
        toast('Server unavailable', 'error');
    }
}

async function sendFile() {
    if (!state.currentChat) return;
    if (state.currentChat.type === 'group') {
        toast('Files are only available in direct chats', 'info');
        return;
    }
    $fileInput.click();
}

$fileInput?.addEventListener('change', async () => {
    const file = $fileInput.files[0];
    if (!file || !state.currentChat) return;

    if (file.size > 512 * 1024) {
        toast('Max size: 512 KB (DNS transport)', 'error');
        $fileInput.value = '';
        return;
    }

    const ts = Date.now();
    addMessage(state.currentChat.id, { from: state.username, file: file.name, size: file.size, ts });
    renderMessages();
    renderChatList();

    const fd = new FormData();
    fd.append('to', state.currentChat.id);
    fd.append('file', file);

    try {
        const res = await fetch('/api/file/send', { method: 'POST', body: fd }).then(r => r.json());
        if (res.ok) toast('File sent', 'success');
        else toast(res.error || 'File send error', 'error');
    } catch (e) {
        toast('Server unavailable', 'error');
    }
    $fileInput.value = '';
});

async function downloadFile(fid, from, filename) {
    toast('Downloading...', 'info');
    try {
        const res = await fetch('/api/file/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fid, from, filename }),
        }).then(r => r.json());

        if (res.ok && res.token) {
            // Use GET endpoint — works on mobile browsers
            window.open(`/api/file/get/${res.token}`, '_blank');
            toast('File downloaded', 'success');
        } else {
            toast('Download failed', 'error');
        }
    } catch (e) {
        toast('Download error', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════
// WebRTC Calls (signaling via SocketIO, media peer-to-peer)
// ═══════════════════════════════════════════════════════════════════

const ICE_SERVERS = [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    { urls: 'stun:stun.services.mozilla.com' },
];

let callState = {
    active: false,
    peer: null,       // username of other party
    pc: null,         // RTCPeerConnection
    localStream: null,
    remoteStream: null,
    isVideo: false,
    isMuted: false,
    isCameraOff: false,
    isIncoming: false,
    startTime: null,
    timerInterval: null,
    pendingOffer: null,
    pendingVideo: false,
};

const $callOverlay = document.getElementById('call-overlay');
const $callAvatar = document.getElementById('call-avatar');
const $callName = document.getElementById('call-name');
const $callStatus = document.getElementById('call-status');
const $callTimer = document.getElementById('call-timer');
const $callVideos = document.getElementById('call-videos');
const $remoteVideo = document.getElementById('remote-video');
const $localVideo = document.getElementById('local-video');
const $callIncoming = document.getElementById('call-incoming');
const $callActive = document.getElementById('call-active');
const $callOutgoing = document.getElementById('call-outgoing');

function startCall(video) {
    if (!state.currentChat || state.currentChat.type !== 'dm') {
        toast('Calls are only available in direct chats', 'info');
        return;
    }
    if (callState.active) {
        toast('Already in a call', 'info');
        return;
    }

    const peer = state.currentChat.id;
    callState.peer = peer;
    callState.isVideo = video;
    callState.isIncoming = false;
    callState.active = true;

    showCallUI(peer, video, 'outgoing');
    initOutgoingCall(peer, video);
}

function showCallUI(peer, video, mode) {
    const colors = avatarColor(peer);
    $callAvatar.style.background = `linear-gradient(135deg,${colors[0]},${colors[1]})`;
    $callAvatar.textContent = peer[0].toUpperCase();
    $callName.textContent = peer;

    $callIncoming.style.display = 'none';
    $callActive.style.display = 'none';
    $callOutgoing.style.display = 'none';
    $callTimer.style.display = 'none';
    $callVideos.style.display = 'none';

    if (mode === 'incoming') {
        $callStatus.textContent = video ? 'Incoming video call...' : 'Incoming voice call...';
        $callIncoming.style.display = 'flex';
        $callOverlay.classList.add('ringing');
    } else if (mode === 'outgoing') {
        $callStatus.textContent = 'Calling...';
        $callOutgoing.style.display = 'flex';
        $callOverlay.classList.add('ringing');
    } else {
        $callStatus.textContent = video ? 'Video call' : 'Voice call';
        $callActive.style.display = 'flex';
        $callOverlay.classList.remove('ringing');
        if (video) $callVideos.style.display = 'block';
        startCallTimer();
    }

    $callOverlay.classList.add('show');
}

function hideCallUI() {
    $callOverlay.classList.remove('show', 'ringing');
    stopCallTimer();
    if ($remoteVideo) $remoteVideo.srcObject = null;
    if ($localVideo) $localVideo.srcObject = null;
}

function startCallTimer() {
    callState.startTime = Date.now();
    $callTimer.style.display = '';
    $callTimer.textContent = '00:00';
    callState.timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - callState.startTime) / 1000);
        const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const s = (elapsed % 60).toString().padStart(2, '0');
        $callTimer.textContent = `${m}:${s}`;
    }, 1000);
}

function stopCallTimer() {
    if (callState.timerInterval) {
        clearInterval(callState.timerInterval);
        callState.timerInterval = null;
    }
}

async function initOutgoingCall(peer, video) {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: video ? { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } } : false,
        });
        callState.localStream = stream;
        if (video && $localVideo) $localVideo.srcObject = stream;

        const pc = createPeerConnection(peer);
        callState.pc = pc;

        stream.getTracks().forEach(t => pc.addTrack(t, stream));

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        socket.emit('call-offer', {
            to: peer,
            offer: pc.localDescription,
            video: video,
        });
    } catch (e) {
        if (location.protocol === 'http:' && location.hostname !== 'localhost') {
            toast('Microphone/camera requires HTTPS. Restart server without --no-ssl and open https://' + location.host, 'error');
        } else {
            toast('Cannot access microphone/camera: ' + e.message, 'error');
        }
        cleanupCall();
    }
}

function createPeerConnection(peer) {
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

    pc.onicecandidate = (e) => {
        if (e.candidate) {
            socket.emit('ice-candidate', { to: peer, candidate: e.candidate });
        }
    };

    pc.ontrack = (e) => {
        callState.remoteStream = e.streams[0];
        if ($remoteVideo) $remoteVideo.srcObject = e.streams[0];
    };

    pc.oniceconnectionstatechange = () => {
        const s = pc.iceConnectionState;
        if (s === 'connected' || s === 'completed') {
            $callStatus.textContent = callState.isVideo ? 'Video call' : 'Voice call';
            $callOverlay.classList.remove('ringing');
            $callOutgoing.style.display = 'none';
            $callActive.style.display = 'flex';
            if (callState.isVideo) $callVideos.style.display = 'block';
            if (!callState.startTime) startCallTimer();
        } else if (s === 'failed') {
            toast('Connection failed — WebRTC could not establish a direct connection. Try voice messages instead.', 'error');
            cleanupCall();
        } else if (s === 'disconnected') {
            $callStatus.textContent = 'Reconnecting...';
        }
    };

    return pc;
}

async function acceptCall(video) {
    if (!callState.pendingOffer) return;

    callState.active = true;
    callState.isVideo = video || callState.pendingVideo;
    callState.isIncoming = false;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: video ? { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } } : false,
        });
        callState.localStream = stream;
        if (video && $localVideo) $localVideo.srcObject = stream;

        const pc = createPeerConnection(callState.peer);
        callState.pc = pc;

        stream.getTracks().forEach(t => pc.addTrack(t, stream));

        await pc.setRemoteDescription(new RTCSessionDescription(callState.pendingOffer));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

        socket.emit('call-answer', {
            to: callState.peer,
            answer: pc.localDescription,
        });

        showCallUI(callState.peer, callState.isVideo, 'active');
        callState.pendingOffer = null;

    } catch (e) {
        if (location.protocol === 'http:' && location.hostname !== 'localhost') {
            toast('Microphone/camera requires HTTPS. Open https://' + location.host, 'error');
        } else {
            toast('Cannot access microphone/camera: ' + e.message, 'error');
        }
        cleanupCall();
    }
}

function rejectCall() {
    socket.emit('call-reject', { to: callState.peer, reason: 'rejected' });
    callState.pendingOffer = null;
    cleanupCall();
}

function endCall() {
    if (callState.peer) {
        socket.emit('call-end', { to: callState.peer });
    }
    cleanupCall();
}

function cleanupCall() {
    if (callState.localStream) {
        callState.localStream.getTracks().forEach(t => t.stop());
    }
    if (callState.pc) {
        callState.pc.close();
    }
    hideCallUI();
    callState = {
        active: false, peer: null, pc: null,
        localStream: null, remoteStream: null,
        isVideo: false, isMuted: false, isCameraOff: false,
        isIncoming: false, startTime: null, timerInterval: null,
        pendingOffer: null, pendingVideo: false,
    };
}

function toggleMute() {
    if (!callState.localStream) return;
    callState.isMuted = !callState.isMuted;
    callState.localStream.getAudioTracks().forEach(t => { t.enabled = !callState.isMuted; });
    const btn = document.getElementById('btn-mute');
    btn.classList.toggle('off', callState.isMuted);
    btn.title = callState.isMuted ? 'Unmute' : 'Mute';
}

function toggleCamera() {
    if (!callState.localStream) return;
    const videoTracks = callState.localStream.getVideoTracks();
    if (videoTracks.length === 0) {
        toast('No camera in this call', 'info');
        return;
    }
    callState.isCameraOff = !callState.isCameraOff;
    videoTracks.forEach(t => { t.enabled = !callState.isCameraOff; });
    const btn = document.getElementById('btn-camera');
    btn.classList.toggle('off', callState.isCameraOff);
    btn.title = callState.isCameraOff ? 'Camera on' : 'Camera off';
}

// ── Call signaling listeners ───────────────────────────────────────

socket.on('call-offer', (data) => {
    if (callState.active) {
        socket.emit('call-reject', { to: data.from, reason: 'busy' });
        return;
    }
    callState.peer = data.from;
    callState.pendingOffer = data.offer;
    callState.pendingVideo = data.video;
    callState.isIncoming = true;
    showCallUI(data.from, data.video, 'incoming');
});

socket.on('call-answer', async (data) => {
    if (!callState.pc) return;
    try {
        await callState.pc.setRemoteDescription(new RTCSessionDescription(data.answer));
    } catch (e) {
        console.error('Failed to set remote description:', e);
    }
});

socket.on('ice-candidate', async (data) => {
    if (!callState.pc) return;
    try {
        await callState.pc.addIceCandidate(new RTCIceCandidate(data.candidate));
    } catch (e) {
        console.error('Failed to add ICE candidate:', e);
    }
});

socket.on('call-end', () => {
    toast('Call ended', 'info');
    cleanupCall();
});

socket.on('call-reject', (data) => {
    const reason = data.reason === 'busy' ? `${data.from} is busy` : `${data.from} declined the call`;
    toast(reason, 'info');
    cleanupCall();
});

socket.on('call-error', (data) => {
    toast(data.error || 'Call error', 'error');
    cleanupCall();
});

// ═══════════════════════════════════════════════════════════════════
// Voice Messages (record audio, send as file via DNS tunnel)
// ═══════════════════════════════════════════════════════════════════

let voiceState = {
    recording: false,
    mediaRecorder: null,
    chunks: [],
    stream: null,
    startTime: null,
    timerInterval: null,
};

const $voiceBtn = document.getElementById('voice-rec-btn');

async function toggleVoiceRecord() {
    if (voiceState.recording) {
        stopVoiceRecord();
    } else {
        startVoiceRecord();
    }
}

async function startVoiceRecord() {
    if (!state.currentChat || state.currentChat.type !== 'dm') {
        toast('Voice messages are only available in direct chats', 'info');
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        voiceState.stream = stream;
        voiceState.chunks = [];

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : 'audio/webm';

        const recorder = new MediaRecorder(stream, { mimeType });
        voiceState.mediaRecorder = recorder;

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) voiceState.chunks.push(e.data);
        };

        recorder.onstop = () => {
            const blob = new Blob(voiceState.chunks, { type: mimeType });
            const duration = Math.round((Date.now() - voiceState.startTime) / 1000);
            sendVoiceMessage(blob, duration);
            voiceState.stream.getTracks().forEach(t => t.stop());
            voiceState.stream = null;
        };

        recorder.start(100);
        voiceState.recording = true;
        voiceState.startTime = Date.now();
        $voiceBtn.classList.add('recording');

        // Show recording indicator in input area
        showRecordingIndicator();

    } catch (e) {
        if (location.protocol === 'http:' && location.hostname !== 'localhost') {
            toast('Microphone requires HTTPS. Open https://' + location.host, 'error');
        } else {
            toast('Cannot access microphone: ' + e.message, 'error');
        }
    }
}

function stopVoiceRecord(cancel) {
    if (!voiceState.recording) return;
    voiceState.recording = false;
    $voiceBtn.classList.remove('recording');
    hideRecordingIndicator();

    if (cancel) {
        voiceState.mediaRecorder.stop();
        voiceState.chunks = [];
        voiceState.stream?.getTracks().forEach(t => t.stop());
        voiceState.stream = null;
        return;
    }

    if (voiceState.mediaRecorder && voiceState.mediaRecorder.state === 'recording') {
        voiceState.mediaRecorder.stop();
    }
}

function showRecordingIndicator() {
    const $wrap = document.querySelector('.input-wrap');
    const $textarea = document.getElementById('msg-input');
    const $attach = document.querySelector('.attach-btn');
    if ($textarea) $textarea.style.display = 'none';
    if ($attach) $attach.style.display = 'none';

    const indicator = document.createElement('div');
    indicator.className = 'recording-indicator';
    indicator.id = 'rec-indicator';
    indicator.innerHTML = `
        <span class="rec-dot"></span>
        <span class="rec-time" id="rec-timer">0:00</span>
        <span class="rec-cancel" onclick="stopVoiceRecord(true)">Cancel</span>
    `;
    $wrap.appendChild(indicator);

    voiceState.timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - voiceState.startTime) / 1000);
        const m = Math.floor(elapsed / 60);
        const s = (elapsed % 60).toString().padStart(2, '0');
        const el = document.getElementById('rec-timer');
        if (el) el.textContent = `${m}:${s}`;
    }, 500);
}

function hideRecordingIndicator() {
    if (voiceState.timerInterval) {
        clearInterval(voiceState.timerInterval);
        voiceState.timerInterval = null;
    }
    const indicator = document.getElementById('rec-indicator');
    if (indicator) indicator.remove();
    const $textarea = document.getElementById('msg-input');
    const $attach = document.querySelector('.attach-btn');
    if ($textarea) $textarea.style.display = '';
    if ($attach) $attach.style.display = '';
}

// ── Voice playback ─────────────────────────────────────────────────

let currentAudio = null;
let currentPlayBtn = null;

async function playVoice(btn) {
    // If already playing this one, pause
    if (currentPlayBtn === btn && currentAudio && !currentAudio.paused) {
        currentAudio.pause();
        btn.innerHTML = '&#x25B6;';
        return;
    }
    // Stop any previous
    if (currentAudio) {
        currentAudio.pause();
        if (currentPlayBtn) currentPlayBtn.innerHTML = '&#x25B6;';
    }

    const wrap = btn.closest('.voice-msg');
    const fid = wrap.dataset.fid;
    const from = wrap.dataset.from;
    const file = wrap.dataset.file;

    if (!fid) {
        toast('Voice message not available for playback', 'info');
        return;
    }

    btn.innerHTML = '&#x23F8;';
    toast('Loading voice...', 'info');

    try {
        const res = await fetch('/api/file/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fid, from, filename: file }),
        }).then(r => r.json());

        if (res.ok && res.data) {
            const binary = atob(res.data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            const blob = new Blob([bytes], { type: 'audio/webm' });
            const url = URL.createObjectURL(blob);

            const audio = new Audio(url);
            currentAudio = audio;
            currentPlayBtn = btn;

            audio.onended = () => {
                btn.innerHTML = '&#x25B6;';
                URL.revokeObjectURL(url);
                currentAudio = null;
                currentPlayBtn = null;
            };

            audio.play();
        } else {
            toast('Cannot load voice message', 'error');
            btn.innerHTML = '&#x25B6;';
        }
    } catch (e) {
        toast('Download error', 'error');
        btn.innerHTML = '&#x25B6;';
    }
}

async function sendVoiceMessage(blob, duration) {
    if (!state.currentChat) return;
    if (blob.size > 512 * 1024) {
        toast('Voice message too long (max 512 KB via DNS)', 'error');
        return;
    }

    const ts = Date.now();
    const filename = `voice_${ts}.webm`;
    addMessage(state.currentChat.id, {
        from: state.username,
        voice: true,
        file: filename,
        size: blob.size,
        duration: duration,
        ts,
    });
    renderMessages();
    renderChatList();

    const fd = new FormData();
    fd.append('to', state.currentChat.id);
    fd.append('file', blob, filename);

    try {
        const res = await fetch('/api/file/send', { method: 'POST', body: fd }).then(r => r.json());
        if (res.ok) toast('Voice message sent', 'success');
        else toast(res.error || 'Send error', 'error');
    } catch (e) {
        toast('Server unavailable', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════
// Context Menu, Reactions, Deletion
// ═══════════════════════════════════════════════════════════════════

let ctxTargetMsg = null;
const $ctxMenu = document.getElementById('msg-context-menu');

function showContextMenu(e, msg) {
    ctxTargetMsg = msg;
    if (!$ctxMenu) return;

    $ctxMenu.classList.add('show');

    // Position
    const x = e.clientX || e.pageX;
    const y = e.clientY || e.pageY;
    const mw = $ctxMenu.offsetWidth;
    const mh = $ctxMenu.offsetHeight;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    $ctxMenu.style.left = (x + mw > vw ? Math.max(0, x - mw) : x) + 'px';
    $ctxMenu.style.top = (y + mh > vh ? Math.max(0, y - mh) : y) + 'px';
}

function hideContextMenu() {
    $ctxMenu?.classList.remove('show');
    ctxTargetMsg = null;
}

// Close on click outside
document.addEventListener('click', (e) => {
    if ($ctxMenu?.classList.contains('show') && !$ctxMenu.contains(e.target)) {
        hideContextMenu();
    }
});

document.addEventListener('scroll', hideContextMenu, true);

// ── Reactions ──────────────────────────────────────────────────────

function renderReactions(msg) {
    if (!msg.reactions || Object.keys(msg.reactions).length === 0) return '';
    let html = '<div class="msg-reactions">';
    for (const [emoji, users] of Object.entries(msg.reactions)) {
        if (!users || users.length === 0) continue;
        const isMine = users.includes(state.username);
        html += `<span class="reaction${isMine ? ' mine' : ''}" onclick="toggleReactionClick('${msg.id}','${emoji}')" title="${users.join(', ')}">${emoji}<span class="r-count">${users.length > 1 ? users.length : ''}</span></span>`;
    }
    html += '</div>';
    return html;
}

function addReaction(emoji) {
    if (!ctxTargetMsg || !state.currentChat) { hideContextMenu(); return; }

    const chat = state.chats[state.currentChat.id];
    if (!chat) { hideContextMenu(); return; }

    const msg = chat.messages.find(m => m.id === ctxTargetMsg.id);
    if (!msg) { hideContextMenu(); return; }

    if (!msg.reactions) msg.reactions = {};
    if (!msg.reactions[emoji]) msg.reactions[emoji] = [];

    const idx = msg.reactions[emoji].indexOf(state.username);
    if (idx >= 0) {
        msg.reactions[emoji].splice(idx, 1);
        if (msg.reactions[emoji].length === 0) delete msg.reactions[emoji];
    } else {
        msg.reactions[emoji].push(state.username);
    }

    saveState();
    renderMessages();
    hideContextMenu();
}

function toggleReactionClick(msgId, emoji) {
    if (!state.currentChat) return;
    const chat = state.chats[state.currentChat.id];
    if (!chat) return;

    const msg = chat.messages.find(m => m.id === msgId);
    if (!msg) return;

    if (!msg.reactions) msg.reactions = {};
    if (!msg.reactions[emoji]) msg.reactions[emoji] = [];

    const idx = msg.reactions[emoji].indexOf(state.username);
    if (idx >= 0) {
        msg.reactions[emoji].splice(idx, 1);
        if (msg.reactions[emoji].length === 0) delete msg.reactions[emoji];
    } else {
        msg.reactions[emoji].push(state.username);
    }

    saveState();
    renderMessages();
}

// ── Context actions ────────────────────────────────────────────────

function ctxReply() {
    if (!ctxTargetMsg) { hideContextMenu(); return; }
    const text = ctxTargetMsg.text || ctxTargetMsg.file || 'voice';
    const prefix = `> ${ctxTargetMsg.from}: ${text.slice(0, 60)}\n`;
    $msgInput.value = prefix;
    $msgInput.focus();
    $msgInput.setSelectionRange(prefix.length, prefix.length);
    hideContextMenu();
}

function ctxCopy() {
    if (!ctxTargetMsg) { hideContextMenu(); return; }
    const text = ctxTargetMsg.text || '';
    if (text) {
        navigator.clipboard?.writeText(text).then(() => toast('Copied', 'success')).catch(() => {});
    } else {
        toast('No text to copy', 'info');
    }
    hideContextMenu();
}

function ctxDelete() {
    if (!ctxTargetMsg || !state.currentChat) { hideContextMenu(); return; }
    const chat = state.chats[state.currentChat.id];
    if (!chat) { hideContextMenu(); return; }

    const idx = chat.messages.findIndex(m => m.id === ctxTargetMsg.id);
    if (idx < 0) { hideContextMenu(); return; }

    const isMine = ctxTargetMsg.from === state.username;

    // Show delete options
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    overlay.innerHTML = `
        <div class="modal">
            <h3>Delete message?</h3>
            <p style="color:var(--text-secondary);font-size:14px;margin-bottom:16px">
                ${isMine ? 'This message was sent by you.' : `This message is from ${esc(ctxTargetMsg.from)}.`}
            </p>
            <div class="modal-actions" style="flex-direction:column;gap:8px">
                <button class="btn btn-primary" style="width:100%;background:var(--red)" id="del-for-me">Delete for me</button>
                ${isMine ? '<button class="btn btn-primary" style="width:100%;background:var(--red);opacity:0.8" id="del-for-all">Delete for everyone</button>' : ''}
                <button class="btn btn-secondary" style="width:100%" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector('#del-for-me').onclick = () => {
        chat.messages[idx].deleted = true;
        chat.messages[idx].text = '';
        chat.messages[idx].file = '';
        chat.messages[idx].voice = false;
        saveState();
        renderMessages();
        renderChatList();
        overlay.remove();
        toast('Message deleted', 'success');
    };

    const delAll = overlay.querySelector('#del-for-all');
    if (delAll) {
        delAll.onclick = async () => {
            chat.messages[idx].deleted = true;
            chat.messages[idx].text = '';
            chat.messages[idx].file = '';
            chat.messages[idx].voice = false;
            saveState();
            renderMessages();
            renderChatList();
            overlay.remove();
            // Send delete signal to peer (as special message)
            if (chat.type === 'dm') {
                try {
                    await fetch('/api/send', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ to: state.currentChat.id, text: `__DELETE__:${ctxTargetMsg.id}` }),
                    });
                } catch (e) {}
            }
            toast('Message deleted for everyone', 'success');
        };
    }

    hideContextMenu();
}

function ctxInfo() {
    if (!ctxTargetMsg) { hideContextMenu(); return; }
    const msg = ctxTargetMsg;
    const d = new Date(msg.ts);
    const fullDate = d.toLocaleDateString('ru-RU', {
        day: 'numeric', month: 'long', year: 'numeric'
    });
    const fullTime = d.toLocaleTimeString('ru-RU', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });

    let info = `From: ${msg.from}\nDate: ${fullDate}\nTime: ${fullTime}`;
    if (msg.file) info += `\nFile: ${msg.file}`;
    if (msg.size) info += `\nSize: ${formatSize(msg.size)}`;
    if (msg.voice) info += `\nType: Voice message`;
    if (msg.duration) info += `\nDuration: ${msg.duration}s`;
    if (msg.reactions) {
        const rList = Object.entries(msg.reactions)
            .filter(([, u]) => u.length > 0)
            .map(([e, u]) => `${e} ${u.join(', ')}`)
            .join('; ');
        if (rList) info += `\nReactions: ${rList}`;
    }

    // Show as tooltip near mouse
    const tooltip = document.createElement('div');
    tooltip.className = 'msg-info-tooltip';
    tooltip.textContent = info;
    tooltip.style.left = $ctxMenu.style.left;
    tooltip.style.top = $ctxMenu.style.top;
    document.body.appendChild(tooltip);
    setTimeout(() => tooltip.remove(), 4000);

    hideContextMenu();
}

// Handle incoming delete commands
function handleDeleteCommand(chatId, text) {
    if (!text.startsWith('__DELETE__:')) return false;
    const msgId = text.slice(10);
    const chat = state.chats[chatId];
    if (!chat) return true;
    const msg = chat.messages.find(m => m.id === msgId);
    if (msg) {
        msg.deleted = true;
        msg.text = '';
        msg.file = '';
        msg.voice = false;
        saveState();
        if (state.currentChat?.id === chatId) renderMessages();
        renderChatList();
    }
    return true;
}

// ── Drag & Drop ─────────────────────────────────────────────────────
const $dropOverlay = $('#drop-overlay');
let dragCounter = 0;

document.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragCounter++;
    if (state.currentChat && $dropOverlay) $dropOverlay.classList.add('active');
});

document.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) { dragCounter = 0; $dropOverlay?.classList.remove('active'); }
});

document.addEventListener('dragover', (e) => e.preventDefault());

document.addEventListener('drop', async (e) => {
    e.preventDefault();
    dragCounter = 0;
    $dropOverlay?.classList.remove('active');
    if (!state.currentChat || !e.dataTransfer.files.length) return;

    const file = e.dataTransfer.files[0];
    const ts = Date.now();
    addMessage(state.currentChat.id, { from: state.username, file: file.name, size: file.size, ts });
    renderMessages();
    renderChatList();

    const fd = new FormData();
    fd.append('to', state.currentChat.id);
    fd.append('file', file);

    try {
        const res = await fetch('/api/file/send', { method: 'POST', body: fd }).then(r => r.json());
        if (res.ok) toast('File sent', 'success');
        else toast('Send error', 'error');
    } catch (e) {
        toast('Server unavailable', 'error');
    }
});

// ── Drawer ──────────────────────────────────────────────────────────
function openDrawer() {
    const colors = avatarColor(state.username);
    const $da = $('#drawer-avatar');
    if ($da) {
        $da.style.background = `linear-gradient(135deg,${colors[0]},${colors[1]})`;
        $da.textContent = state.username[0].toUpperCase();
    }
    $('#drawer-overlay')?.classList.add('show');
    $('#drawer')?.classList.add('show');
}

function closeDrawer() {
    $('#drawer-overlay')?.classList.remove('show');
    $('#drawer')?.classList.remove('show');
}

async function doLogout() {
    closeDrawer();
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/';
}

// ── FAB ─────────────────────────────────────────────────────────────
let fabOpen = false;

function toggleFab() {
    fabOpen = !fabOpen;
    const $menu = $('#fab-menu');
    const $btn = $('#fab-btn');
    if (fabOpen) {
        $menu?.classList.add('show');
        $btn.innerHTML = '&#x2715;';
    } else {
        closeFab();
    }
}

function closeFab() {
    fabOpen = false;
    $('#fab-menu')?.classList.remove('show');
    const $btn = $('#fab-btn');
    if ($btn) $btn.innerHTML = '&#x270E;';
}

// Click outside FAB to close
document.addEventListener('click', (e) => {
    if (!fabOpen) return;
    const $fab = $('#fab-btn');
    const $menu = $('#fab-menu');
    if ($fab && !$fab.contains(e.target) && $menu && !$menu.contains(e.target)) {
        closeFab();
    }
});

// ── Contacts ────────────────────────────────────────────────────────
function showContacts() {
    const $panel = $('#contacts-panel');
    $panel?.classList.add('show');
    loadContacts();
}

function hideContacts() {
    $('#contacts-panel')?.classList.remove('show');
}

async function loadContacts() {
    const $list = $('#contacts-list');
    if (!$list) return;
    $list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading...</div>';

    try {
        const res = await fetch('/api/users').then(r => r.json());
        const users = res.users || [];

        if (users.length === 0) {
            $list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">No other users online yet</div>';
            return;
        }

        $list.innerHTML = '';
        for (const user of users) {
            const div = document.createElement('div');
            div.className = 'contact-item';
            div.onclick = () => {
                hideContacts();
                ensureChat(user, 'dm', user);
                saveState();
                renderChatList();
                selectChat(user);
            };
            div.innerHTML = `
                ${avatarHtml(user, false, 'sm')}
                <div>
                    <div class="contact-name">${esc(user)}</div>
                    <div class="contact-status">online</div>
                </div>
            `;
            $list.appendChild(div);
        }

        // Check for new users
        checkNewUsers(users);
    } catch (e) {
        $list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Error loading contacts</div>';
    }
}

// ── New user notifications ──────────────────────────────────────────
function checkNewUsers(users) {
    const prev = state.knownUsers;
    const newUsers = users.filter(u => !prev.includes(u));
    state.knownUsers = users;

    for (const user of newUsers) {
        showNewUserNotification(user);
    }
}

function showNewUserNotification(user) {
    if (!$notifs) return;
    const colors = avatarColor(user);
    const div = document.createElement('div');
    div.className = 'notification-banner';
    div.innerHTML = `
        ${avatarHtml(user, false, 'sm')}
        <div class="notif-text"><strong>${esc(user)}</strong> joined the messenger</div>
        <button class="notif-close" onclick="this.parentElement.remove()">&#x2715;</button>
    `;
    div.querySelector('.notif-text').onclick = () => {
        div.remove();
        ensureChat(user, 'dm', user);
        saveState();
        renderChatList();
        selectChat(user);
    };
    div.style.cursor = 'pointer';
    $notifs.appendChild(div);

    // Auto-remove after 10 seconds
    setTimeout(() => div.remove(), 10000);
}

// Poll for new users every 15 seconds
setInterval(async () => {
    try {
        const res = await fetch('/api/users').then(r => r.json());
        const users = res.users || [];
        checkNewUsers(users);
    } catch (e) {}
}, 15000);

// ── Modals ──────────────────────────────────────────────────────────
function showModal(title, fields, onSubmit) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const inputs = fields.map(f =>
        `<input id="modal-${f.id}" placeholder="${f.placeholder}" autocomplete="off">`
    ).join('');

    overlay.innerHTML = `
        <div class="modal">
            <h3>${title}</h3>
            ${inputs}
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                <button class="btn btn-primary" id="modal-submit">OK</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    const first = overlay.querySelector('input');
    if (first) first.focus();

    overlay.querySelector('#modal-submit').onclick = () => {
        const vals = {};
        fields.forEach(f => { vals[f.id] = document.getElementById(`modal-${f.id}`).value.trim(); });
        overlay.remove();
        onSubmit(vals);
    };

    overlay.querySelectorAll('input').forEach(inp => {
        inp.addEventListener('keydown', e => {
            if (e.key === 'Enter') overlay.querySelector('#modal-submit').click();
        });
    });
}

function showNewDM() {
    showModal('New Chat', [{ id: 'user', placeholder: 'Username' }], async ({ user }) => {
        if (!user) return;
        const res = await fetch('/api/resolve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user }),
        }).then(r => r.json());

        if (res.found) {
            ensureChat(user, 'dm', user);
            saveState();
            renderChatList();
            selectChat(user);
            toast(`Chat with ${user} created`, 'success');
        } else {
            toast(res.error || `User "${user}" not found`, 'error');
        }
    });
}

function showNewGroup() {
    showModal('New Group', [{ id: 'name', placeholder: 'Group name (latin, digits, _)' }], async ({ name }) => {
        if (!name) return;
        const res = await fetch('/api/groups/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group: name }),
        }).then(r => r.json());

        if (res.ok) {
            ensureChat(name, 'group', name);
            saveState();
            renderChatList();
            selectChat(name);
            toast(`Group "${name}" created`, 'success');
        } else {
            toast(res.error || 'Failed to create group', 'error');
        }
    });
}

function showInviteModal() {
    if (!state.currentChat || state.currentChat.type !== 'group') return;
    showModal('Invite Member', [{ id: 'user', placeholder: 'Username' }], async ({ user }) => {
        if (!user) return;
        const res = await fetch('/api/groups/invite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group: state.currentChat.id, user }),
        }).then(r => r.json());

        if (res.ok) {
            const ts = Date.now();
            addMessage(state.currentChat.id, { system: true, text: `${user} invited to group`, ts });
            renderMessages();
            toast(`${user} invited`, 'success');
        } else {
            toast(res.error || 'Failed to invite', 'error');
        }
    });
}

// ── Socket.IO events ────────────────────────────────────────────────
socket.on('message', (msg) => {
    let chatId, chatType, chatName;
    if (msg.type === 'dm') {
        chatId = msg.from;
        chatType = 'dm';
        chatName = msg.from;
    } else {
        chatId = msg.group;
        chatType = 'group';
        chatName = msg.group;
    }

    // Handle delete commands silently
    if (msg.text && handleDeleteCommand(chatId, msg.text)) return;

    const chat = ensureChat(chatId, chatType, chatName);
    const ts = Date.now();
    addMessage(chatId, { from: msg.from, text: msg.text, ts });

    if (!state.currentChat || state.currentChat.id !== chatId) {
        chat.unread = (chat.unread || 0) + 1;
        saveState();
    }

    renderChatList();
    if (state.currentChat?.id === chatId) renderMessages();
});

socket.on('file', (info) => {
    const chat = ensureChat(info.from, 'dm', info.from);
    const ts = Date.now();
    const isVoice = info.name && info.name.startsWith('voice_') && info.name.endsWith('.webm');
    const msg = {
        from: info.from, file: info.name, size: info.size, fid: info.fid, ts,
    };
    if (isVoice) msg.voice = true;
    addMessage(info.from, msg);

    if (!state.currentChat || state.currentChat.id !== info.from) {
        chat.unread = (chat.unread || 0) + 1;
        saveState();
    }

    renderChatList();
    if (state.currentChat?.id === info.from) renderMessages();
    toast(isVoice ? `Voice message from ${info.from}` : `File from ${info.from}: ${info.name}`, 'info');
});

// ── Connection status ───────────────────────────────────────────────
let isConnected = true;

socket.on('status', (data) => {
    const wasConnected = isConnected;
    isConnected = data.connected;
    updateConnectionStatus();
    if (!wasConnected && isConnected) {
        toast('Connection restored', 'success');
    }
});

socket.on('disconnect', () => {
    isConnected = false;
    updateConnectionStatus();
});

socket.on('connect', () => {
    isConnected = true;
    updateConnectionStatus();
});

function updateConnectionStatus() {
    const dot = document.querySelector('.chat-header .online-dot');
    if (dot) {
        dot.style.background = isConnected ? 'var(--green)' : 'var(--red)';
    }
    // Update subtitle if in chat
    const sub = document.querySelector('.chat-header .chat-subtitle');
    if (sub && !isConnected) {
        const existingWarn = sub.querySelector('.conn-warn');
        if (!existingWarn) {
            const span = document.createElement('span');
            span.className = 'conn-warn';
            span.style.cssText = 'color:var(--red);margin-left:8px;font-size:12px';
            span.textContent = '(reconnecting...)';
            sub.appendChild(span);
        }
    } else if (sub) {
        const warn = sub.querySelector('.conn-warn');
        if (warn) warn.remove();
    }
}

// ── Input handling ──────────────────────────────────────────────────
$msgInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

$sendBtn?.addEventListener('click', sendMessage);

$msgInput?.addEventListener('input', () => {
    $msgInput.style.height = 'auto';
    $msgInput.style.height = Math.min($msgInput.scrollHeight, 120) + 'px';
});

$searchInput?.addEventListener('input', () => renderChatList());

// ── Utilities ───────────────────────────────────────────────────────
function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function formatTime(ts) {
    const d = new Date(ts);
    return d.getHours().toString().padStart(2, '0') + ':' +
           d.getMinutes().toString().padStart(2, '0');
}

function formatFullDateTime(ts) {
    const d = new Date(ts);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }) +
           ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

// ── Init ────────────────────────────────────────────────────────────
async function init() {
    loadState();
    initTabs();

    // Fetch groups from server
    try {
        const res = await fetch('/api/groups').then(r => r.json());
        for (const gid of res.groups || []) ensureChat(gid, 'group', gid);
    } catch (e) {}

    // Fetch users for initial known list
    try {
        const res = await fetch('/api/users').then(r => r.json());
        state.knownUsers = res.users || [];
    } catch (e) {}

    renderChatList();
}

init();
