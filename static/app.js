// ── DNS Messenger — Telegram-style Frontend ─────────────────────────

const socket = io();

// ═══════════════════════════════════════════════════════════════════
// i18n — Russian / English translations
// ═══════════════════════════════════════════════════════════════════

const I18N = {
    ru: {
        // Sidebar
        search: 'Поиск',
        tab_all: 'Все', tab_personal: 'Личные', tab_groups: 'Группы',
        menu: 'Меню', contacts: 'Контакты', new_group: 'Новая группа', new_chat: 'Новый чат',
        privacy: 'Настройки', logout: 'Выйти', admin_panel: 'Админ-панель',
        change_photo: 'Сменить фото', online: 'в сети',
        // Chat area
        empty_title: 'DNS Tunnel Мессенджер',
        empty_desc: 'Зашифрованные сообщения через DNS-запросы. Работает даже при отключениях интернета.',
        message_placeholder: 'Сообщение', voice_msg_btn: 'Голосовое сообщение',
        typing_one: 'печатает...', typing_many: 'печатают...',
        attach_file: 'Прикрепить файл', send: 'Отправить',
        drop_file: 'Отпустите файл для отправки',
        // Header
        voice_call: 'Голосовой вызов', video_call: 'Видеозвонок', add_member: '+ Участник',
        reconnecting: '(переподключение...)',
        // Calls
        calling: 'Вызов...', incoming_voice: 'Входящий вызов...', incoming_video: 'Входящий видеозвонок...',
        call_voice: 'Голосовой вызов', call_video: 'Видеозвонок', call_ended: 'Звонок завершён',
        call_only_dm: 'Звонки доступны только в личных чатах',
        already_in_call: 'Вы уже в звонке',
        call_busy: '{0} занят', call_declined: '{0} отклонил звонок',
        call_no_connection: 'Не удалось установить соединение. Возможно, NAT/фаервол блокирует P2P',
        call_error: 'Ошибка звонка',
        mic_on: 'Включить микрофон', mic_off: 'Выключить микрофон',
        cam_on: 'Включить камеру', cam_off: 'Выключить камеру',
        no_camera: 'В этом звонке нет камеры',
        reject_call: 'Отклонить', accept_voice: 'Голосом', accept_video_btn: 'Видео',
        end_call: 'Завершить', cancel_call: 'Отмена',
        // Context menu
        reply: 'Ответить', copy: 'Копировать', delete: 'Удалить', info: 'Инфо',
        deleted_msg: 'Сообщение удалено', copied: 'Скопировано', no_text_to_copy: 'Нет текста для копирования',
        delete_msg_title: 'Удалить сообщение?',
        delete_mine: 'Это сообщение отправлено вами.',
        delete_theirs: 'Это сообщение от {0}.',
        delete_for_me: 'Удалить у меня', delete_for_all: 'Удалить у всех',
        cancel: 'Отмена', msg_deleted: 'Сообщение удалено', msg_deleted_all: 'Сообщение удалено у всех',
        // Voice
        voice_too_large: 'Голосовое сообщение слишком длинное (макс 512 КБ)',
        voice_sent: 'Голосовое отправлено', voice_from: 'Голосовое от {0}',
        voice_loading: 'Загрузка голосового...', voice_unavailable: 'Голосовое недоступно',
        voice_load_err: 'Не удалось загрузить голосовое',
        // Files
        file_max: 'Макс. размер: 512 КБ (DNS-транспорт)',
        file_sent: 'Файл отправлен', file_from: 'Файл от {0}: {1}',
        file_send_err: 'Ошибка отправки файла', file_dl: 'Скачивание...',
        file_downloaded: 'Файл скачан', file_dl_err: 'Ошибка скачивания',
        // Common
        loading: 'Загрузка...', server_unavailable: 'Сервер недоступен', send_error: 'Ошибка отправки',
        connection_restored: 'Соединение восстановлено',
        new_chat_title: 'Новый чат', username_field: 'Имя пользователя',
        new_group_title: 'Новая группа', group_name_field: 'Название группы (латиница, цифры, _)',
        invite_member: 'Пригласить участника', chat_created: 'Чат с {0} создан',
        user_not_found: 'Пользователь "{0}" не найден', group_created: 'Группа "{0}" создана',
        group_create_err: 'Не удалось создать группу', invited: '{0} приглашён',
        invite_err: 'Не удалось пригласить',
        joined_msg: '{0} присоединился к мессенджеру', invited_group: '{0} приглашён в группу',
        no_users: 'Пока нет других пользователей',
        contacts_err: 'Ошибка загрузки контактов',
        file_too_large: 'Фото слишком большое (макс 100 КБ)',
        photo_updated: 'Фото обновлено',
        close: 'Закрыть', save: 'Сохранить', ok: 'ОК',
        // Privacy
        privacy_title: 'Конфиденциальность',
        ls_visible_to: 'Кто может видеть время моего последнего захода:',
        everyone: 'Все', nobody: 'Никто',
        settings_saved: 'Настройки сохранены',
        // Last seen
        ls_recently: 'был(а) недавно', ls_just_now: 'был(а) только что',
        ls_min: 'был(а) {0} мин назад', ls_hour: 'был(а) {0} ч назад', ls_date: 'был(а) {0}',
        ls_online: 'в сети',
        // Date/Notifs
        message_deleted: 'Сообщение удалено',
        allow_mic: 'Разрешите доступ к микрофону/камере в настройках браузера',
        https_required: 'Для {0} Chrome требует HTTPS. Откройте https://{1} и примите сертификат',
        calls_feature: 'звонков', voice_feature: 'голосовых сообщений',
        language: 'Язык',
    },
    en: {
        search: 'Search',
        tab_all: 'All', tab_personal: 'Personal', tab_groups: 'Groups',
        menu: 'Menu', contacts: 'Contacts', new_group: 'New Group', new_chat: 'New Chat',
        privacy: 'Settings', logout: 'Log Out', admin_panel: 'Admin Panel',
        change_photo: 'Change photo', online: 'online',
        empty_title: 'DNS Tunnel Messenger',
        empty_desc: 'Encrypted messages via DNS queries. Works even during internet shutdowns.',
        message_placeholder: 'Message', voice_msg_btn: 'Voice message',
        typing_one: 'typing...', typing_many: 'are typing...',
        attach_file: 'Attach file', send: 'Send',
        drop_file: 'Drop file to send',
        voice_call: 'Voice call', video_call: 'Video call', add_member: '+ Member',
        reconnecting: '(reconnecting...)',
        calling: 'Calling...', incoming_voice: 'Incoming voice call...', incoming_video: 'Incoming video call...',
        call_voice: 'Voice call', call_video: 'Video call', call_ended: 'Call ended',
        call_only_dm: 'Calls are only available in direct chats',
        already_in_call: 'Already in a call',
        call_busy: '{0} is busy', call_declined: '{0} declined the call',
        call_no_connection: 'Could not establish a connection. NAT/firewall may block P2P',
        call_error: 'Call error',
        mic_on: 'Unmute', mic_off: 'Mute',
        cam_on: 'Camera on', cam_off: 'Camera off',
        no_camera: 'No camera in this call',
        reject_call: 'Decline', accept_voice: 'Audio', accept_video_btn: 'Video',
        end_call: 'End call', cancel_call: 'Cancel',
        reply: 'Reply', copy: 'Copy', delete: 'Delete', info: 'Info',
        deleted_msg: 'Message deleted', copied: 'Copied', no_text_to_copy: 'No text to copy',
        delete_msg_title: 'Delete message?',
        delete_mine: 'This message was sent by you.',
        delete_theirs: 'This message is from {0}.',
        delete_for_me: 'Delete for me', delete_for_all: 'Delete for everyone',
        cancel: 'Cancel', msg_deleted: 'Message deleted', msg_deleted_all: 'Message deleted for everyone',
        voice_too_large: 'Voice message too long (max 512 KB)',
        voice_sent: 'Voice message sent', voice_from: 'Voice message from {0}',
        voice_loading: 'Loading voice...', voice_unavailable: 'Voice message not available',
        voice_load_err: 'Cannot load voice message',
        file_max: 'Max size: 512 KB (DNS transport)',
        file_sent: 'File sent', file_from: 'File from {0}: {1}',
        file_send_err: 'File send error', file_dl: 'Downloading...',
        file_downloaded: 'File downloaded', file_dl_err: 'Download error',
        loading: 'Loading...', server_unavailable: 'Server unavailable', send_error: 'Send error',
        connection_restored: 'Connection restored',
        new_chat_title: 'New Chat', username_field: 'Username',
        new_group_title: 'New Group', group_name_field: 'Group name (latin, digits, _)',
        invite_member: 'Invite Member', chat_created: 'Chat with {0} created',
        user_not_found: 'User "{0}" not found', group_created: 'Group "{0}" created',
        group_create_err: 'Failed to create group', invited: '{0} invited',
        invite_err: 'Failed to invite',
        joined_msg: '{0} joined the messenger', invited_group: '{0} invited to group',
        no_users: 'No other users online yet',
        contacts_err: 'Error loading contacts',
        file_too_large: 'Photo too large (max 100 KB)',
        photo_updated: 'Photo updated',
        close: 'Close', save: 'Save', ok: 'OK',
        privacy_title: 'Privacy',
        ls_visible_to: 'Who can see my last seen time:',
        everyone: 'Everyone', nobody: 'Nobody',
        settings_saved: 'Settings saved',
        ls_recently: 'last seen recently', ls_just_now: 'last seen just now',
        ls_min: 'last seen {0}m ago', ls_hour: 'last seen {0}h ago', ls_date: 'last seen {0}',
        ls_online: 'online',
        message_deleted: 'Message deleted',
        allow_mic: 'Allow microphone/camera access in browser settings',
        https_required: 'Chrome requires HTTPS for {0}. Open https://{1} and accept the certificate',
        calls_feature: 'calls', voice_feature: 'voice messages',
        language: 'Language',
    },
};

let currentLang = localStorage.getItem('dns_lang') || 'ru';
function t(key, ...args) {
    const dict = I18N[currentLang] || I18N.ru;
    let s = dict[key] || I18N.ru[key] || key;
    args.forEach((a, i) => { s = s.replace(`{${i}}`, a); });
    return s;
}

function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('dns_lang', lang);
    applyStaticTranslations();
    const ll = document.getElementById('lang-label');
    if (ll) ll.textContent = lang === 'ru' ? 'Язык: Русский' : 'Language: English';
    // Re-render dynamic UI
    if (state.currentChat) {
        renderHeader();
        renderMessages();
    }
    renderChatList();
}

function toggleLanguage() {
    setLanguage(currentLang === 'ru' ? 'en' : 'ru');
}

// Applies translations to static HTML elements (placeholders, titles, etc.)
function applyStaticTranslations() {
    document.documentElement.lang = currentLang;
    document.title = t('empty_title');

    const set = (sel, prop, val) => { const el = document.querySelector(sel); if (el) el[prop] = val; };

    set('#search-input', 'placeholder', t('search'));
    set('#msg-input', 'placeholder', t('message_placeholder'));
    set('#menu-btn', 'title', t('menu'));
    set('#voice-rec-btn', 'title', t('voice_msg_btn'));
    set('.attach-btn', 'title', t('attach_file'));
    set('#send-btn', 'title', t('send'));

    // Tabs
    const tabAll = document.querySelector('.tab[data-tab="all"]');
    const tabDm = document.querySelector('.tab[data-tab="dm"]');
    const tabGr = document.querySelector('.tab[data-tab="group"]');
    if (tabAll) tabAll.innerHTML = t('tab_all') + ' <span class="badge" id="badge-all" style="display:none">0</span>';
    if (tabDm) tabDm.innerHTML = t('tab_personal') + ' <span class="badge" id="badge-dm" style="display:none">0</span>';
    if (tabGr) tabGr.innerHTML = t('tab_groups') + ' <span class="badge" id="badge-group" style="display:none">0</span>';

    // Empty state
    const emptyH2 = document.querySelector('.no-chat h2');
    const emptyP = document.querySelector('.no-chat p');
    if (emptyH2) emptyH2.textContent = t('empty_title');
    if (emptyP) emptyP.textContent = t('empty_desc');

    // Drop overlay
    const drop = document.querySelector('#drop-overlay span');
    if (drop) drop.innerHTML = '\uD83D\uDCCE ' + t('drop_file');

    // Drawer items — order in index.html: contacts, new_group, new_chat, privacy, language, logout, admin
    const drawerItems = document.querySelectorAll('.drawer-item');
    const drawerLabels = [
        t('contacts'), t('new_group'), t('new_chat'), t('privacy'),
        null, // language toggle — handled separately to preserve #lang-label span
        t('logout'), t('admin_panel')
    ];
    drawerItems.forEach((el, i) => {
        const label = drawerLabels[i];
        if (label == null) return;
        const icon = el.querySelector('.drawer-icon');
        if (icon) el.innerHTML = icon.outerHTML + ' ' + label;
    });
    // Language toggle label
    const ll2 = document.getElementById('lang-label');
    if (ll2) ll2.textContent = currentLang === 'ru' ? 'Язык: Русский' : 'Language: English';
    const drawerStatus = document.querySelector('.drawer-status');
    if (drawerStatus) {
        drawerStatus.innerHTML = `<span class="online-dot"></span> ${t('online')} <span class="change-photo-hint" onclick="showProfilePhotoUpload()">\uD83D\uDCF7 ${t('change_photo')}</span>`;
    }
    const drawerFooter = document.querySelector('.drawer-footer');
    if (drawerFooter) drawerFooter.innerHTML = 'DNS Tunnel Messenger &middot; E2E';

    // FAB menu items
    const fabItems = document.querySelectorAll('.fab-menu-item');
    const fabLabels = [t('new_group'), t('new_chat'), t('contacts')];
    fabItems.forEach((el, i) => {
        const icon = el.querySelector('.fab-icon');
        if (icon && fabLabels[i]) {
            el.innerHTML = icon.outerHTML + ' ' + fabLabels[i];
        }
    });

    // Contacts header
    const ch = document.querySelector('.contacts-header h2');
    if (ch) ch.textContent = t('contacts');

    // Context menu actions
    const ctxButtons = document.querySelectorAll('.ctx-actions button');
    const ctxLabels = [['↩', t('reply')], ['📋', t('copy')], ['🗑', t('delete')], ['ℹ', t('info')]];
    ctxButtons.forEach((btn, i) => {
        if (ctxLabels[i]) btn.innerHTML = `<span>${ctxLabels[i][0]}</span> ${ctxLabels[i][1]}`;
    });

    // Call overlay buttons titles
    const callBtnTitles = {
        'btn-mute': 'mic_off',
        'btn-camera': 'cam_off',
    };
    for (const [id, key] of Object.entries(callBtnTitles)) {
        const el = document.getElementById(id);
        if (el) el.title = t(key);
    }
}

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

// Profile photo cache
const profilePhotos = {};

function avatarHtml(name, isGroup, size) {
    const sz = size || '';
    const colors = avatarColor(name);
    const initial = isGroup ? '#' : name[0].toUpperCase();
    const photo = !isGroup && profilePhotos[name];
    if (photo) {
        return `<div class="avatar ${sz}" style="background:linear-gradient(135deg,${colors[0]},${colors[1]})"><img src="${photo}" class="avatar-img" alt=""></div>`;
    }
    return `<div class="avatar ${sz}" style="background:linear-gradient(135deg,${colors[0]},${colors[1]})">${initial}</div>`;
}

// Last seen cache
const lastSeenCache = {};

function formatLastSeen(data) {
    if (!data) return '';
    if (data.hidden) return 'был(а) недавно';
    if (data.online) return 'в сети';
    if (!data.last_seen) return 'был(а) недавно';
    const diff = (Date.now() / 1000) - data.last_seen;
    if (diff < 60) return 'был(а) только что';
    if (diff < 3600) return `был(а) ${Math.floor(diff / 60)} мин назад`;
    if (diff < 86400) return `был(а) ${Math.floor(diff / 3600)} ч назад`;
    const d = new Date(data.last_seen * 1000);
    return 'был(а) ' + d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
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
    // Notify peer that their messages have been read (DM only)
    if (chat.type === 'dm') {
        try { socket.emit('read', { to: id }); } catch(e) {}
    }
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

    const lsData = !isGroup ? lastSeenCache[chat.name] : null;
    const lsText = !isGroup ? formatLastSeen(lsData) : 'E2E group \u00b7 DNS Tunnel';
    const isOnline = lsData?.online;

    $chatHeader.innerHTML = `
        <button class="mobile-back" onclick="goBack()">&#x2190;</button>
        ${avatarHtml(chat.name, isGroup, 'sm')}
        <div class="header-info">
            <div class="chat-title">${esc(chat.name)}</div>
            <div class="chat-subtitle">
                <span class="online-dot" style="background:${isOnline || isGroup ? 'var(--green)' : 'var(--text-muted)'}"></span>
                <span class="subtitle-text">${isGroup ? 'E2E group \u00b7 DNS Tunnel' : esc(lsText)}</span>
                <span class="typing-text" style="display:none;color:var(--green);font-style:italic"></span>
            </div>
        </div>
        <div class="header-actions">
            ${!isGroup ? `
                <button onclick="startCall(false)" title="Голосовой вызов">&#x1F4DE;</button>
                <button onclick="startCall(true)" title="Видеозвонок">&#x1F4F9;</button>
            ` : ''}
            ${isGroup ? `<button class="invite-btn" onclick="showInviteModal()">+ Участник</button>` : ''}
        </div>
    `;

    // Fetch last seen for DM chats
    if (!isGroup) {
        fetchLastSeen(chat.name);
    }
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
            div.innerHTML = `<div class="msg-text">Сообщение удалено<span class="msg-footer">
                <span class="msg-time">${formatTime(msg.ts)}</span>
            </span></div>`;
            $messages.appendChild(div);
            continue;
        }

        // Data attributes for context menu
        div.dataset.msgId = msg.id || '';
        div.dataset.chatId = state.currentChat.id;

        const reactionsHtml = renderReactions(msg);

        // Detect a leading reply quote of the form "> name: text\n..." and split it out
        let replyHtml = '';
        let bodyText = msg.text || '';
        if (bodyText.startsWith('> ')) {
            const nl = bodyText.indexOf('\n');
            if (nl > 0) {
                const quoteLine = bodyText.slice(2, nl);
                bodyText = bodyText.slice(nl + 1);
                const colon = quoteLine.indexOf(':');
                let qName = '', qText = quoteLine;
                if (colon > 0) { qName = quoteLine.slice(0, colon); qText = quoteLine.slice(colon + 1).trim(); }
                replyHtml = `<div class="reply-quote"><div class="reply-name">${esc(qName)}</div><div class="reply-text">${esc(qText)}</div></div>`;
            }
        }
        const checkHtml = isMine ? `<span class="msg-status${msg.read ? ' read' : ''}">${msg.read ? '\u2713\u2713' : '\u2713'}</span>` : '';

        if (msg.videoMsg) {
            div.className = `message ${isMine ? 'sent' : 'received'} video-msg-wrap${isNew ? ' first' : ''}`;
            const dur = msg.duration || 0;
            const durStr = Math.floor(dur / 60) + ':' + (dur % 60).toString().padStart(2, '0');
            div.innerHTML = `
                ${!isMine && isGroup && isNew ? `<div class="sender" style="color:${avatarColor(msg.from)[0]}">${esc(msg.from)}</div>` : ''}
                <div class="video-msg" data-fid="${msg.fid || ''}" data-from="${esc(msg.from)}" data-file="${esc(msg.file)}">
                    <video playsinline></video>
                    <button class="video-play-btn" onclick="playVideoMsg(this)">&#x25B6;</button>
                    <span class="video-duration">${durStr}</span>
                </div>
                <div class="msg-footer">
                    <span class="msg-time">${formatTime(msg.ts)}</span>
                    ${checkHtml}
                </div>
                ${reactionsHtml}
            `;
        } else if (msg.voice) {
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
                    ${checkHtml}
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
                ${replyHtml}
                <div class="msg-text">${esc(bodyText)}<span class="msg-footer">
                    <span class="msg-time">${formatTime(msg.ts)}</span>
                    ${checkHtml}
                </span></div>
                ${reactionsHtml}
            `;
        }

        // Context menu on right-click and long-press
        div.addEventListener('contextmenu', (e) => { e.preventDefault(); showContextMenu(e, msg); });

        // Swipe-to-reply (Telegram-like) + long-press context menu
        let longPressTimer;
        let swipeStartX = 0, swipeStartY = 0, swipeDX = 0, swiping = false, swipeFired = false;
        const SWIPE_THRESHOLD = 60;
        const swipeDir = isMine ? -1 : 1; // own messages swipe left, others right
        div.addEventListener('touchstart', (e) => {
            const t0 = e.touches[0];
            swipeStartX = t0.clientX;
            swipeStartY = t0.clientY;
            swipeDX = 0; swiping = true; swipeFired = false;
            div.classList.add('holding');
            longPressTimer = setTimeout(() => {
                navigator.vibrate?.(15);
                showContextMenu(t0, msg);
                swiping = false;
            }, 500);
        }, { passive: true });
        div.addEventListener('touchmove', (e) => {
            if (!swiping) return;
            const t0 = e.touches[0];
            const dx = t0.clientX - swipeStartX;
            const dy = t0.clientY - swipeStartY;
            if (Math.abs(dy) > 14) { swiping = false; clearTimeout(longPressTimer); div.style.transform = ''; return; }
            if (Math.abs(dx) > 6) clearTimeout(longPressTimer);
            // Only allow swipe in the right direction
            if (Math.sign(dx) !== swipeDir && dx !== 0) return;
            swipeDX = dx;
            const damped = Math.sign(dx) * Math.min(Math.abs(dx), 90);
            div.style.transform = `translateX(${damped}px)`;
            if (!swipeFired && Math.abs(dx) > SWIPE_THRESHOLD) {
                swipeFired = true;
                navigator.vibrate?.(20);
                div.classList.add('swipe-flash');
            }
        }, { passive: true });
        div.addEventListener('touchend', () => {
            clearTimeout(longPressTimer);
            div.classList.remove('holding');
            div.style.transition = 'transform 0.25s ease';
            div.style.transform = '';
            setTimeout(() => { div.style.transition = ''; div.classList.remove('swipe-flash'); }, 300);
            if (swipeFired) startReply(msg);
            swiping = false;
        });

        // Mouse drag swipe (desktop)
        let mDown = false, mStartX = 0, mFired = false;
        let mHoldTimer;
        div.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            mDown = true; mStartX = e.clientX; mFired = false;
            div.classList.add('holding');
            mHoldTimer = setTimeout(() => { showContextMenu(e, msg); }, 500);
        });
        div.addEventListener('mousemove', (e) => {
            if (!mDown) return;
            const dx = e.clientX - mStartX;
            if (Math.abs(dx) > 6) clearTimeout(mHoldTimer);
            if (Math.sign(dx) !== swipeDir && dx !== 0) return;
            const damped = Math.sign(dx) * Math.min(Math.abs(dx), 90);
            div.style.transform = `translateX(${damped}px)`;
            if (!mFired && Math.abs(dx) > SWIPE_THRESHOLD) {
                mFired = true;
                div.classList.add('swipe-flash');
            }
        });
        const mUp = () => {
            if (!mDown) return;
            mDown = false;
            clearTimeout(mHoldTimer);
            div.classList.remove('holding');
            div.style.transition = 'transform 0.25s ease';
            div.style.transform = '';
            setTimeout(() => { div.style.transition = ''; div.classList.remove('swipe-flash'); }, 300);
            if (mFired) startReply(msg);
        };
        div.addEventListener('mouseup', mUp);
        div.addEventListener('mouseleave', mUp);

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
    if (typeof typingSentAt !== 'undefined' && typingSentAt) {
        try { emitTyping(false); } catch(e) {}
        typingSentAt = 0;
        if (typeof typingStopTimer !== 'undefined') clearTimeout(typingStopTimer);
    }

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

        if (!res.ok) toast(res.error || t('send_error'), 'error');
    } catch (e) {
        toast(t('server_unavailable'), 'error');
    }
}

async function sendFile() {
    if (!state.currentChat) return;
    if (state.currentChat.type === 'group') {
        toast(t('call_only_dm'), 'info');
        return;
    }
    $fileInput.click();
}

$fileInput?.addEventListener('change', async () => {
    const file = $fileInput.files[0];
    if (!file || !state.currentChat) return;

    if (file.size > 512 * 1024) {
        toast(t('file_max'), 'error');
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
        if (res.ok) toast(t('file_sent'), 'success');
        else toast(res.error || t('file_send_err'), 'error');
    } catch (e) {
        toast(t('server_unavailable'), 'error');
    }
    $fileInput.value = '';
});

async function downloadFile(fid, from, filename) {
    toast(t('file_dl'), 'info');
    try {
        const res = await fetch('/api/file/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fid, from, filename }),
        }).then(r => r.json());

        if (res.ok && res.token) {
            window.open(`/api/file/get/${res.token}`, '_blank');
            toast(t('file_downloaded'), 'success');
        } else {
            toast(t('file_dl_err'), 'error');
        }
    } catch (e) {
        toast(t('file_dl_err'), 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════
// WebRTC Calls (signaling via SocketIO, media peer-to-peer)
// ═══════════════════════════════════════════════════════════════════

const ICE_SERVERS = [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    { urls: 'stun:stun2.l.google.com:19302' },
    { urls: 'stun:stun3.l.google.com:19302' },
    { urls: 'stun:stun4.l.google.com:19302' },
    { urls: 'stun:stun.services.mozilla.com' },
    // Free TURN servers from Open Relay (helps when direct P2P fails, e.g. strict NATs)
    { urls: 'turn:openrelay.metered.ca:80', username: 'openrelayproject', credential: 'openrelayproject' },
    { urls: 'turn:openrelay.metered.ca:443', username: 'openrelayproject', credential: 'openrelayproject' },
    { urls: 'turn:openrelay.metered.ca:443?transport=tcp', username: 'openrelayproject', credential: 'openrelayproject' },
];

let callState = {
    active: false,
    peer: null,
    pc: null,
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
    iceQueue: [],        // queued ICE candidates received before setRemoteDescription
    remoteDescSet: false,
    ringtoneOsc: null,   // ringing tone oscillator
};

const $callOverlay = document.getElementById('call-overlay');
const $callAvatar = document.getElementById('call-avatar');
const $callName = document.getElementById('call-name');
const $callStatus = document.getElementById('call-status');
const $callTimer = document.getElementById('call-timer');
const $callVideos = document.getElementById('call-videos');
const $remoteVideo = document.getElementById('remote-video');
const $localVideo = document.getElementById('local-video');
const $remoteAudio = document.getElementById('remote-audio');
const $callIncoming = document.getElementById('call-incoming');
const $callActive = document.getElementById('call-active');
const $callOutgoing = document.getElementById('call-outgoing');

function startCall(video) {
    if (!state.currentChat || state.currentChat.type !== 'dm') {
        toast('Звонки доступны только в личных чатах', 'info');
        return;
    }
    if (callState.active) {
        toast('Вы уже в звонке', 'info');
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
        $callStatus.textContent = video ? 'Входящий видеозвонок...' : 'Входящий вызов...';
        $callIncoming.style.display = 'flex';
        $callOverlay.classList.add('ringing');
        startRingtone(true);   // play incoming ringtone
        vibrate([400, 200, 400, 200, 400]);
    } else if (mode === 'outgoing') {
        $callStatus.textContent = 'Вызов...';
        $callOutgoing.style.display = 'flex';
        $callOverlay.classList.add('ringing');
        startRingtone(false);  // play outgoing ringback
    } else {
        $callStatus.textContent = video ? 'Видеозвонок' : 'Голосовой вызов';
        $callActive.style.display = 'flex';
        $callOverlay.classList.remove('ringing');
        stopRingtone();
        if (video) $callVideos.style.display = 'block';
        if (!callState.startTime) startCallTimer();
    }

    $callOverlay.classList.add('show');
}

function hideCallUI() {
    $callOverlay.classList.remove('show', 'ringing');
    stopCallTimer();
    stopRingtone();
    if ($remoteVideo) $remoteVideo.srcObject = null;
    if ($localVideo) $localVideo.srcObject = null;
    if ($remoteAudio) $remoteAudio.srcObject = null;
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
        if (video && $localVideo) {
            $localVideo.srcObject = stream;
            $localVideo.play().catch(()=>{});
        }

        const pc = createPeerConnection(peer);
        callState.pc = pc;

        stream.getTracks().forEach(t => pc.addTrack(t, stream));

        const offer = await pc.createOffer({
            offerToReceiveAudio: true,
            offerToReceiveVideo: video,
        });
        await pc.setLocalDescription(offer);

        socket.emit('call-offer', {
            to: peer,
            offer: pc.localDescription,
            video: video,
        });
    } catch (e) {
        console.error('initOutgoingCall error:', e);
        showMediaError('звонков');
        cleanupCall();
    }
}

function showMediaError(feature) {
    if (location.protocol === 'http:' && location.hostname !== 'localhost') {
        toast(`Для ${feature} Chrome требует HTTPS. Откройте https://${location.host} и примите сертификат`, 'error');
    } else {
        toast('Разрешите доступ к микрофону/камере в настройках браузера', 'error');
    }
}

function createPeerConnection(peer) {
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

    pc.onicecandidate = (e) => {
        if (e.candidate) {
            socket.emit('ice-candidate', { to: peer, candidate: e.candidate });
        }
    };

    // Remote media arrived — attach to BOTH audio and video elements so audio plays
    // even during pure voice calls (where the <video> container is hidden).
    pc.ontrack = (e) => {
        const stream = e.streams[0];
        callState.remoteStream = stream;
        // Audio always goes to the always-present <audio> element
        if ($remoteAudio) {
            $remoteAudio.srcObject = stream;
            $remoteAudio.play().catch((err) => {
                console.warn('Remote audio autoplay blocked:', err);
                // Try unlocking on user interaction
                const unlock = () => {
                    $remoteAudio.play().catch(()=>{});
                    document.removeEventListener('click', unlock);
                };
                document.addEventListener('click', unlock, { once: true });
            });
        }
        // Also attach to the video element (muted internally; audio plays via the audio element)
        if ($remoteVideo) {
            $remoteVideo.srcObject = stream;
            $remoteVideo.muted = true; // important: prevent double audio
            $remoteVideo.play().catch(()=>{});
        }
    };

    pc.oniceconnectionstatechange = () => {
        const s = pc.iceConnectionState;
        console.log('ICE state:', s);
        if (s === 'connected' || s === 'completed') {
            $callStatus.textContent = callState.isVideo ? 'Видеозвонок' : 'Голосовой вызов';
            $callOverlay.classList.remove('ringing');
            stopRingtone();
            $callOutgoing.style.display = 'none';
            $callActive.style.display = 'flex';
            if (callState.isVideo) $callVideos.style.display = 'block';
            if (!callState.startTime) startCallTimer();
        } else if (s === 'failed') {
            toast('Не удалось установить соединение. Возможно, NAT/фаервол блокирует P2P', 'error');
            cleanupCall();
        } else if (s === 'disconnected') {
            $callStatus.textContent = 'Переподключение...';
        }
    };

    return pc;
}

async function acceptCall(video) {
    if (!callState.pendingOffer) return;

    callState.active = true;
    callState.isVideo = video || callState.pendingVideo;
    callState.isIncoming = false;
    stopRingtone();

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: video ? { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } } : false,
        });
        callState.localStream = stream;
        if (video && $localVideo) {
            $localVideo.srcObject = stream;
            $localVideo.play().catch(()=>{});
        }

        const pc = createPeerConnection(callState.peer);
        callState.pc = pc;

        stream.getTracks().forEach(t => pc.addTrack(t, stream));

        await pc.setRemoteDescription(new RTCSessionDescription(callState.pendingOffer));
        callState.remoteDescSet = true;

        // Flush any queued ICE candidates now that remote description is set
        for (const c of callState.iceQueue) {
            try { await pc.addIceCandidate(new RTCIceCandidate(c)); }
            catch (e) { console.error('Queued ICE add failed:', e); }
        }
        callState.iceQueue = [];

        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

        socket.emit('call-answer', {
            to: callState.peer,
            answer: pc.localDescription,
        });

        showCallUI(callState.peer, callState.isVideo, 'active');
        callState.pendingOffer = null;

    } catch (e) {
        console.error('acceptCall error:', e);
        showMediaError('звонков');
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
        try { callState.pc.close(); } catch(e) {}
    }
    stopRingtone();
    hideCallUI();
    callState = {
        active: false, peer: null, pc: null,
        localStream: null, remoteStream: null,
        isVideo: false, isMuted: false, isCameraOff: false,
        isIncoming: false, startTime: null, timerInterval: null,
        pendingOffer: null, pendingVideo: false,
        iceQueue: [], remoteDescSet: false, ringtoneOsc: null,
    };
}

function toggleMute() {
    if (!callState.localStream) return;
    callState.isMuted = !callState.isMuted;
    callState.localStream.getAudioTracks().forEach(t => { t.enabled = !callState.isMuted; });
    const btn = document.getElementById('btn-mute');
    btn.classList.toggle('off', callState.isMuted);
    btn.title = callState.isMuted ? 'Включить микрофон' : 'Выключить микрофон';
}

function toggleCamera() {
    if (!callState.localStream) return;
    const videoTracks = callState.localStream.getVideoTracks();
    if (videoTracks.length === 0) {
        toast('В этом звонке нет камеры', 'info');
        return;
    }
    callState.isCameraOff = !callState.isCameraOff;
    videoTracks.forEach(t => { t.enabled = !callState.isCameraOff; });
    const btn = document.getElementById('btn-camera');
    btn.classList.toggle('off', callState.isCameraOff);
    btn.title = callState.isCameraOff ? 'Включить камеру' : 'Выключить камеру';
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
        callState.remoteDescSet = true;
        // Flush queued ICE candidates
        for (const c of callState.iceQueue) {
            try { await callState.pc.addIceCandidate(new RTCIceCandidate(c)); }
            catch (e) { console.error('Queued ICE add failed:', e); }
        }
        callState.iceQueue = [];
    } catch (e) {
        console.error('Failed to set remote description:', e);
    }
});

socket.on('ice-candidate', async (data) => {
    if (!callState.pc) {
        // Store for later — peer connection not yet created
        callState.iceQueue.push(data.candidate);
        return;
    }
    if (!callState.remoteDescSet) {
        // Queue until setRemoteDescription completes
        callState.iceQueue.push(data.candidate);
        return;
    }
    try {
        await callState.pc.addIceCandidate(new RTCIceCandidate(data.candidate));
    } catch (e) {
        console.error('Failed to add ICE candidate:', e);
    }
});

socket.on('call-end', () => {
    toast('Звонок завершён', 'info');
    cleanupCall();
});

socket.on('call-reject', (data) => {
    const reason = data.reason === 'busy' ? `${data.from} занят` : `${data.from} отклонил звонок`;
    toast(reason, 'info');
    cleanupCall();
});

socket.on('call-error', (data) => {
    toast(data.error || 'Ошибка звонка', 'error');
    cleanupCall();
});

// ═══════════════════════════════════════════════════════════════════
// Notifications: sound (Web Audio) + vibration
// ═══════════════════════════════════════════════════════════════════

let audioCtx = null;
function getAudioCtx() {
    if (!audioCtx) {
        try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }
        catch (e) { return null; }
    }
    if (audioCtx.state === 'suspended') audioCtx.resume().catch(()=>{});
    return audioCtx;
}

// Unlock audio on first user interaction (browser autoplay policy)
document.addEventListener('click', () => { getAudioCtx(); }, { once: true });
document.addEventListener('touchstart', () => { getAudioCtx(); }, { once: true });

function playBeep(freq = 880, duration = 0.15, volume = 0.15) {
    const ctx = getAudioCtx();
    if (!ctx) return;
    try {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        gain.gain.value = 0;
        gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + 0.01);
        gain.gain.linearRampToValueAtTime(0, ctx.currentTime + duration);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + duration + 0.02);
    } catch (e) {}
}

function playMessageSound() {
    playBeep(880, 0.08, 0.12);
    setTimeout(() => playBeep(1175, 0.1, 0.12), 90);
}

function vibrate(pattern) {
    if (navigator.vibrate) {
        try { navigator.vibrate(pattern); } catch (e) {}
    }
}

// Ringing tone loops for incoming/outgoing calls
function startRingtone(incoming) {
    stopRingtone();
    const ctx = getAudioCtx();
    if (!ctx) return;

    const playPhase = () => {
        if (!callState.ringtoneOsc) return;
        if (incoming) {
            // Incoming: two alternating tones, louder
            playBeep(1000, 0.4, 0.2);
            setTimeout(() => playBeep(800, 0.4, 0.2), 420);
        } else {
            // Outgoing ringback: single long beep
            playBeep(440, 0.6, 0.1);
        }
    };

    callState.ringtoneOsc = setInterval(playPhase, incoming ? 1200 : 2500);
    playPhase();
}

function stopRingtone() {
    if (callState.ringtoneOsc) {
        clearInterval(callState.ringtoneOsc);
        callState.ringtoneOsc = null;
    }
}

// Request Notification permission on first user click (avoids blocking modals)
let notifPermRequested = false;
document.addEventListener('click', () => {
    if (!notifPermRequested && 'Notification' in window && Notification.permission === 'default') {
        notifPermRequested = true;
        try { Notification.requestPermission().catch(()=>{}); } catch(e) {}
    }
}, { once: false });

function showDesktopNotification(title, body) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    // Notify whenever the window isn't focused (covers minimized, hidden tab, other window)
    const focused = document.hasFocus && document.hasFocus();
    if (focused && !document.hidden) return;
    try {
        const n = new Notification(title, { body, icon: '/static/favicon.png' });
        n.onclick = () => { window.focus(); n.close(); };
        setTimeout(() => n.close(), 5000);
    } catch (e) {}
}

// Privacy settings stored locally — last seen visibility
function getPrivacyLastSeen() {
    return localStorage.getItem('dns_privacy_last_seen') || 'everyone'; // 'everyone' | 'nobody'
}

function setPrivacyLastSeen(val) {
    localStorage.setItem('dns_privacy_last_seen', val);
    // Inform server so it hides our last_seen from others
    fetch('/api/privacy/last-seen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visibility: val }),
    }).catch(()=>{});
}

// ═══════════════════════════════════════════════════════════════════
// Settings — Telegram-like multi-section preferences
// ═══════════════════════════════════════════════════════════════════
const SETTINGS_KEYS = {
    notifSound: 'dns_set_notif_sound',
    notifVibro: 'dns_set_notif_vibro',
    notifDesktop: 'dns_set_notif_desktop',
    msgPreview: 'dns_set_msg_preview',
    enterSend: 'dns_set_enter_send',
    theme: 'dns_set_theme',              // dark | light | midnight
    accent: 'dns_set_accent',            // green | blue | purple | orange | red
    fontScale: 'dns_set_font_scale',     // 0.9 | 1 | 1.1 | 1.2
    animations: 'dns_set_animations',
    chatWallpaper: 'dns_set_wallpaper',  // none | dots | grid | aurora
};
function getSetting(key, def) {
    const v = localStorage.getItem(SETTINGS_KEYS[key] || key);
    if (v === null || v === undefined) return def;
    if (v === 'true') return true;
    if (v === 'false') return false;
    return v;
}
function setSetting(key, val) {
    localStorage.setItem(SETTINGS_KEYS[key] || key, String(val));
    applySettings();
}
function applySettings() {
    const theme = getSetting('theme', 'dark');
    const accent = getSetting('accent', 'green');
    const scale = parseFloat(getSetting('fontScale', '1')) || 1;
    const animOn = getSetting('animations', true);
    const wall = getSetting('chatWallpaper', 'none');
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.dataset.accent = accent;
    root.dataset.wallpaper = wall;
    root.style.setProperty('--font-scale', scale);
    root.classList.toggle('no-anim', !animOn);
}
applySettings();

function showSettings(initialSection) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay settings-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const sections = [
        { id: 'general',  icon: '\u2699',    title: 'Основные' },
        { id: 'notif',    icon: '\u{1F514}', title: 'Уведомления и звуки' },
        { id: 'privacy',  icon: '\u{1F512}', title: 'Конфиденциальность' },
        { id: 'appear',   icon: '\u{1F3A8}', title: 'Оформление' },
        { id: 'chats',    icon: '\u{1F4AC}', title: 'Чаты' },
        { id: 'data',     icon: '\u{1F4BE}', title: 'Данные и хранилище' },
        { id: 'lang',     icon: '\u{1F310}', title: 'Язык' },
        { id: 'about',    icon: '\u2139',    title: 'О приложении' },
    ];

    overlay.innerHTML = `
        <div class="modal settings-modal">
            <div class="settings-header">
                <h3>Настройки</h3>
                <button class="settings-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
            </div>
            <div class="settings-body">
                <div class="settings-sidebar">
                    ${sections.map(s => `
                        <div class="settings-tab" data-section="${s.id}">
                            <span class="settings-tab-icon">${s.icon}</span>
                            <span>${s.title}</span>
                        </div>`).join('')}
                </div>
                <div class="settings-content" id="settings-content"></div>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    const content = overlay.querySelector('#settings-content');
    const tabs = overlay.querySelectorAll('.settings-tab');
    const renderSection = (id) => {
        tabs.forEach(t => t.classList.toggle('active', t.dataset.section === id));
        content.innerHTML = buildSettingsSection(id);
        wireSettingsSection(id, content, overlay);
    };
    tabs.forEach(t => t.addEventListener('click', () => renderSection(t.dataset.section)));
    renderSection(initialSection || 'general');
}
// Back-compat: existing code/drawer may still call showPrivacySettings
function showPrivacySettings() { showSettings('privacy'); }

function buildSettingsSection(id) {
    const toggleRow = (label, key, def, hint) => {
        const on = getSetting(key, def);
        return `
            <label class="set-row">
                <div>
                    <div class="set-label">${label}</div>
                    ${hint ? `<div class="set-hint">${hint}</div>` : ''}
                </div>
                <span class="switch ${on?'on':''}" data-key="${key}" data-type="bool"></span>
            </label>`;
    };
    const selectRow = (label, key, def, options) => {
        const cur = getSetting(key, def);
        return `
            <div class="set-row">
                <div class="set-label">${label}</div>
                <div class="set-options" data-key="${key}" data-type="select">
                    ${options.map(o => `<button class="set-opt ${o.val===cur?'active':''}" data-val="${o.val}">${o.label}</button>`).join('')}
                </div>
            </div>`;
    };

    if (id === 'general') {
        return `
            <h4 class="set-section-title">Основные</h4>
            ${toggleRow('Отправка по Enter', 'enterSend', true, 'Ctrl+Enter — перевод строки')}
            ${selectRow('Размер шрифта', 'fontScale', '1', [
                { val: '0.9', label: 'Мелкий' },
                { val: '1',   label: 'Обычный' },
                { val: '1.1', label: 'Крупный' },
                { val: '1.2', label: 'Огромный' },
            ])}
            ${toggleRow('Анимации интерфейса', 'animations', true, 'Отключите для слабых устройств')}
        `;
    }
    if (id === 'notif') {
        return `
            <h4 class="set-section-title">Уведомления и звуки</h4>
            ${toggleRow('Звук при сообщении', 'notifSound', true)}
            ${toggleRow('Вибрация', 'notifVibro', true, 'На поддерживаемых устройствах')}
            ${toggleRow('Уведомления на рабочем столе', 'notifDesktop', true)}
            ${toggleRow('Показывать превью сообщений', 'msgPreview', true, 'Текст в уведомлении')}
            <div class="set-row">
                <button class="btn btn-secondary" id="test-notif">Протестировать звук</button>
            </div>
        `;
    }
    if (id === 'privacy') {
        const cur = getPrivacyLastSeen();
        return `
            <h4 class="set-section-title">Конфиденциальность</h4>
            <div class="set-row" style="flex-direction:column;align-items:stretch">
                <div class="set-label" style="margin-bottom:6px">Кто видит время моего последнего захода</div>
                <div class="set-options" data-key="lastSeen" data-type="privacy">
                    <button class="set-opt ${cur==='everyone'?'active':''}" data-val="everyone">Все</button>
                    <button class="set-opt ${cur==='nobody'?'active':''}" data-val="nobody">Никто</button>
                </div>
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">Завершить все сеансы</div>
                    <div class="set-hint">Выйти из аккаунта на всех устройствах</div>
                </div>
                <button class="btn btn-danger" id="logout-all">Выйти</button>
            </div>
        `;
    }
    if (id === 'appear') {
        return `
            <h4 class="set-section-title">Оформление</h4>
            ${selectRow('Тема', 'theme', 'dark', [
                { val: 'dark',     label: 'Тёмная' },
                { val: 'light',    label: 'Светлая' },
                { val: 'midnight', label: 'Полночь' },
            ])}
            ${selectRow('Цвет акцента', 'accent', 'green', [
                { val: 'green',  label: '🟢' },
                { val: 'blue',   label: '🔵' },
                { val: 'purple', label: '🟣' },
                { val: 'orange', label: '🟠' },
                { val: 'red',    label: '🔴' },
            ])}
            ${selectRow('Фон чата', 'chatWallpaper', 'none', [
                { val: 'none',   label: 'Без фона' },
                { val: 'dots',   label: 'Точки' },
                { val: 'grid',   label: 'Сетка' },
                { val: 'aurora', label: 'Сияние' },
            ])}
        `;
    }
    if (id === 'chats') {
        return `
            <h4 class="set-section-title">Чаты</h4>
            <div class="set-row">
                <div>
                    <div class="set-label">Очистить историю всех чатов</div>
                    <div class="set-hint">Удалит сообщения только на этом устройстве</div>
                </div>
                <button class="btn btn-danger" id="clear-history">Очистить</button>
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">Экспорт чатов в JSON</div>
                    <div class="set-hint">Скачать локальную копию всех сообщений</div>
                </div>
                <button class="btn btn-secondary" id="export-chats">Скачать</button>
            </div>
        `;
    }
    if (id === 'data') {
        const bytes = (() => { try { return new Blob([JSON.stringify(state)]).size; } catch(e) { return 0; } })();
        const kb = (bytes / 1024).toFixed(1);
        return `
            <h4 class="set-section-title">Данные и хранилище</h4>
            <div class="set-row">
                <div>
                    <div class="set-label">Локальное хранилище</div>
                    <div class="set-hint">Занято ~${kb} КБ</div>
                </div>
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">Сбросить кеш localStorage</div>
                    <div class="set-hint">Удалит все настройки и локальные данные</div>
                </div>
                <button class="btn btn-danger" id="reset-storage">Сбросить</button>
            </div>
        `;
    }
    if (id === 'lang') {
        return `
            <h4 class="set-section-title">Язык интерфейса</h4>
            <div class="set-row" style="flex-direction:column;align-items:stretch">
                <div class="set-options" data-key="lang" data-type="lang">
                    <button class="set-opt ${currentLang==='ru'?'active':''}" data-val="ru">🇷🇺 Русский</button>
                    <button class="set-opt ${currentLang==='en'?'active':''}" data-val="en">🇬🇧 English</button>
                </div>
            </div>
        `;
    }
    if (id === 'about') {
        return `
            <h4 class="set-section-title">О приложении</h4>
            <div class="about-block">
                <div class="about-logo">&#x1F310;</div>
                <div class="about-title">DNS Tunnel Messenger</div>
                <div class="about-sub">Версия 1.0 · E2E · DNS-туннель</div>
                <p class="about-text">
                    Мессенджер, работающий через DNS-запросы. Сообщения шифруются
                    end-to-end на вашем устройстве и передаются даже при строгих
                    ограничениях сети.
                </p>
                <p class="about-text"><a href="https://github.com/nikitasever/dns-messenger" target="_blank" style="color:var(--accent,#00a884)">Исходный код на GitHub</a></p>
            </div>
        `;
    }
    return '';
}

function wireSettingsSection(id, root, overlay) {
    // Toggle switches
    root.querySelectorAll('.switch[data-type="bool"]').forEach(sw => {
        sw.addEventListener('click', () => {
            const key = sw.dataset.key;
            const cur = getSetting(key, true);
            setSetting(key, !cur);
            sw.classList.toggle('on', !cur);
        });
    });
    // Select rows (theme, accent, fontScale, wallpaper)
    root.querySelectorAll('.set-options[data-type="select"]').forEach(row => {
        row.querySelectorAll('.set-opt').forEach(btn => {
            btn.addEventListener('click', () => {
                row.querySelectorAll('.set-opt').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                setSetting(row.dataset.key, btn.dataset.val);
            });
        });
    });
    // Privacy radio
    root.querySelectorAll('.set-options[data-type="privacy"] .set-opt').forEach(btn => {
        btn.addEventListener('click', () => {
            root.querySelectorAll('.set-options[data-type="privacy"] .set-opt').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            setPrivacyLastSeen(btn.dataset.val);
            toast('Сохранено', 'success');
        });
    });
    // Language
    root.querySelectorAll('.set-options[data-type="lang"] .set-opt').forEach(btn => {
        btn.addEventListener('click', () => setLanguage(btn.dataset.val));
    });

    const byId = (id) => root.querySelector('#' + id);
    if (id === 'notif') {
        byId('test-notif')?.addEventListener('click', () => { playMessageSound(); vibrate(120); });
    }
    if (id === 'privacy') {
        byId('logout-all')?.addEventListener('click', () => {
            if (confirm('Выйти из аккаунта?')) doLogout();
        });
    }
    if (id === 'chats') {
        byId('clear-history')?.addEventListener('click', () => {
            if (!confirm('Удалить все локальные сообщения?')) return;
            for (const cid in state.chats) state.chats[cid].messages = [];
            saveState();
            renderChatList();
            if (state.currentChat) renderMessages();
            toast('История очищена', 'success');
        });
        byId('export-chats')?.addEventListener('click', () => {
            const blob = new Blob([JSON.stringify(state.chats, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `dns-messenger-chats-${Date.now()}.json`;
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 2000);
        });
    }
    if (id === 'data') {
        byId('reset-storage')?.addEventListener('click', () => {
            if (!confirm('Удалить все локальные данные и настройки?')) return;
            localStorage.clear();
            location.reload();
        });
    }
}

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
        showMediaError('voice messages');
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
        toast(t('voice_unavailable'), 'info');
        return;
    }

    btn.innerHTML = '&#x23F8;';
    toast(t('voice_loading'), 'info');

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
            toast(t('voice_load_err'), 'error');
            btn.innerHTML = '&#x25B6;';
        }
    } catch (e) {
        toast(t('file_dl_err'), 'error');
        btn.innerHTML = '&#x25B6;';
    }
}

async function sendVoiceMessage(blob, duration) {
    if (!state.currentChat) return;
    if (blob.size > 512 * 1024) {
        toast(t('voice_too_large'), 'error');
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
        if (res.ok) toast(t('voice_sent'), 'success');
        else toast(res.error || t('send_error'), 'error');
    } catch (e) {
        toast(t('server_unavailable'), 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════
// Video messages — round Telegram-like clips with audio
// ═══════════════════════════════════════════════════════════════════
const videoState = {
    recording: false, mediaRecorder: null, chunks: [], stream: null,
    startTime: null, timerInterval: null, previewEl: null,
};
const $videoBtn = document.getElementById('video-rec-btn');

async function toggleVideoRecord() {
    if (videoState.recording) stopVideoRecord();
    else startVideoRecord();
}

async function startVideoRecord() {
    if (!state.currentChat || state.currentChat.type !== 'dm') {
        toast(t('voice_dm_only') || 'Только в личных чатах', 'info');
        return;
    }
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 320, height: 320, facingMode: 'user' },
            audio: true,
        });
        videoState.stream = stream;
        videoState.chunks = [];

        const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')
            ? 'video/webm;codecs=vp9,opus'
            : (MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')
                ? 'video/webm;codecs=vp8,opus' : 'video/webm');
        const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 500000 });
        videoState.mediaRecorder = recorder;

        recorder.ondataavailable = (e) => { if (e.data.size > 0) videoState.chunks.push(e.data); };
        recorder.onstop = () => {
            const blob = new Blob(videoState.chunks, { type: 'video/webm' });
            const duration = Math.round((Date.now() - videoState.startTime) / 1000);
            sendVideoMessage(blob, duration);
            videoState.stream?.getTracks().forEach(t => t.stop());
            videoState.stream = null;
            hideVideoPreview();
        };

        recorder.start(100);
        videoState.recording = true;
        videoState.startTime = Date.now();
        $videoBtn?.classList.add('recording');
        showVideoPreview(stream);

        // Auto-stop at 60s
        setTimeout(() => { if (videoState.recording) stopVideoRecord(); }, 60000);
    } catch (e) {
        showMediaError('video messages');
    }
}

function stopVideoRecord(cancel) {
    if (!videoState.recording) return;
    videoState.recording = false;
    $videoBtn?.classList.remove('recording');
    if (cancel) {
        try { videoState.mediaRecorder.stop(); } catch(e) {}
        videoState.chunks = [];
        videoState.stream?.getTracks().forEach(t => t.stop());
        videoState.stream = null;
        hideVideoPreview();
        return;
    }
    if (videoState.mediaRecorder?.state === 'recording') videoState.mediaRecorder.stop();
}

function showVideoPreview(stream) {
    hideVideoPreview();
    const wrap = document.createElement('div');
    wrap.className = 'video-rec-preview';
    wrap.id = 'video-rec-preview';
    wrap.innerHTML = `
        <video autoplay muted playsinline></video>
        <div class="rec-dot"></div>
        <div class="video-rec-timer" id="video-rec-timer">0:00</div>
        <button class="video-rec-cancel" onclick="stopVideoRecord(true)">✕</button>
        <button class="video-rec-stop" onclick="stopVideoRecord()">●</button>
    `;
    document.body.appendChild(wrap);
    wrap.querySelector('video').srcObject = stream;
    videoState.previewEl = wrap;
    videoState.timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - videoState.startTime) / 1000);
        const m = Math.floor(elapsed / 60);
        const s = (elapsed % 60).toString().padStart(2, '0');
        const el = document.getElementById('video-rec-timer');
        if (el) el.textContent = `${m}:${s}`;
    }, 500);
}
function hideVideoPreview() {
    if (videoState.timerInterval) { clearInterval(videoState.timerInterval); videoState.timerInterval = null; }
    if (videoState.previewEl) { videoState.previewEl.remove(); videoState.previewEl = null; }
}

async function sendVideoMessage(blob, duration) {
    if (!state.currentChat) return;
    if (blob.size > 4 * 1024 * 1024) { toast('Видео слишком большое (макс 4 МБ)', 'error'); return; }
    const ts = Date.now();
    const filename = `videomsg_${ts}.webm`;
    addMessage(state.currentChat.id, {
        from: state.username, videoMsg: true, file: filename,
        size: blob.size, duration, ts,
    });
    renderMessages();
    renderChatList();
    const fd = new FormData();
    fd.append('to', state.currentChat.id);
    fd.append('file', blob, filename);
    try {
        const res = await fetch('/api/file/send', { method: 'POST', body: fd }).then(r => r.json());
        if (!res.ok) toast(res.error || t('send_error'), 'error');
    } catch (e) { toast(t('server_unavailable'), 'error'); }
}

async function playVideoMsg(btn) {
    const wrap = btn.closest('.video-msg');
    const fid = wrap.dataset.fid, from = wrap.dataset.from, file = wrap.dataset.file;
    if (!fid) { toast(t('voice_unavailable'), 'info'); return; }
    const videoEl = wrap.querySelector('video');
    if (videoEl.dataset.loaded === '1') {
        if (videoEl.paused) videoEl.play(); else videoEl.pause();
        return;
    }
    btn.innerHTML = '⏳';
    try {
        const res = await fetch('/api/file/download', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fid, from, filename: file }),
        }).then(r => r.json());
        if (res.ok && res.data) {
            const binary = atob(res.data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            const blob = new Blob([bytes], { type: 'video/webm' });
            videoEl.src = URL.createObjectURL(blob);
            videoEl.dataset.loaded = '1';
            videoEl.play();
            btn.style.display = 'none';
        } else {
            toast(t('voice_load_err'), 'error');
            btn.innerHTML = '▶';
        }
    } catch (e) {
        toast(t('file_dl_err'), 'error');
        btn.innerHTML = '▶';
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

    // Highlight selected message
    document.querySelectorAll('.message.selected').forEach(el => el.classList.remove('selected'));
    if (msg && msg.id) {
        const el = document.querySelector(`.message[data-msg-id="${msg.id}"]`);
        if (el) el.classList.add('selected');
    }

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
    document.querySelectorAll('.message.selected').forEach(el => el.classList.remove('selected'));
    ctxTargetMsg = null;
}

// Swipe-to-reply: insert quote into the input
function startReply(msg) {
    if (!msg) return;
    const text = msg.text || msg.file || (msg.voice ? '🎤' : '');
    const snippet = (text || '').toString().slice(0, 60);
    const quote = `> ${msg.from}: ${snippet}\n`;
    if ($msgInput) {
        if (!$msgInput.value.startsWith('> ')) $msgInput.value = quote + $msgInput.value;
        $msgInput.focus();
    }
    // Brief highlight on the message
    const el = document.querySelector(`.message[data-msg-id="${msg.id || ''}"]`);
    if (el) {
        el.classList.add('reply-flash');
        setTimeout(() => el.classList.remove('reply-flash'), 700);
    }
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

const EMOJI_FULL = [
    '👍','👎','❤️','🔥','😂','😮','😢','🥰','😡','🤔',
    '👏','🎉','💯','🙏','😎','🤣','💪','😱','🥳','😈',
    '💀','🤡','🤮','💩','👀','🫡','🤝','✅','❌','⭐',
];

function toggleEmojiPanel() {
    const panel = document.getElementById('ctx-emoji-panel');
    if (!panel) return;
    if (panel.classList.contains('show')) {
        panel.classList.remove('show');
        return;
    }
    panel.innerHTML = '';
    for (const em of EMOJI_FULL) {
        const btn = document.createElement('button');
        btn.textContent = em;
        btn.onclick = () => addReaction(em);
        panel.appendChild(btn);
    }
    panel.classList.add('show');
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
        navigator.clipboard?.writeText(text).then(() => toast(t('copied'), 'success')).catch(() => {});
    } else {
        toast(t('no_text_to_copy'), 'info');
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
            <h3>${t('delete_msg_title')}</h3>
            <p style="color:var(--text-secondary);font-size:14px;margin-bottom:16px">
                ${isMine ? t('delete_mine') : t('delete_theirs', esc(ctxTargetMsg.from))}
            </p>
            <div class="modal-actions" style="flex-direction:column;gap:8px">
                <button class="btn btn-primary" style="width:100%;background:var(--red)" id="del-for-me">${t('delete_for_me')}</button>
                ${isMine ? `<button class="btn btn-primary" style="width:100%;background:var(--red);opacity:0.8" id="del-for-all">${t('delete_for_all')}</button>` : ''}
                <button class="btn btn-secondary" style="width:100%" onclick="this.closest('.modal-overlay').remove()">${t('cancel')}</button>
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
        toast(t('msg_deleted'), 'success');
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
            toast(t('msg_deleted_all'), 'success');
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
        const photo = profilePhotos[state.username];
        if (photo) {
            $da.innerHTML = `<img src="${photo}" class="avatar-img" alt="">`;
        } else {
            $da.textContent = state.username[0].toUpperCase();
        }
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
    $list.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted)">${t('loading')}</div>`;

    try {
        const res = await fetch('/api/users').then(r => r.json());
        const users = res.users || [];

        if (users.length === 0) {
            $list.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted)">${t('no_users')}</div>`;
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
                    <div class="contact-status">${t('online')}</div>
                </div>
            `;
            $list.appendChild(div);
        }

        // Check for new users
        checkNewUsers(users);
    } catch (e) {
        $list.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted)">${t('contacts_err')}</div>`;
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
        <div class="notif-text"><strong>${esc(user)}</strong> ${t('joined_msg', '').trim()}</div>
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
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">${t('cancel')}</button>
                <button class="btn btn-primary" id="modal-submit">${t('ok')}</button>
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
    showModal(t('new_chat_title'), [{ id: 'user', placeholder: t('username_field') }], async ({ user }) => {
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
            toast(t('chat_created', user), 'success');
        } else {
            toast(res.error || t('user_not_found', user), 'error');
        }
    });
}

function showNewGroup() {
    showModal(t('new_group_title'), [{ id: 'name', placeholder: t('group_name_field') }], async ({ name }) => {
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
            toast(t('group_created', name), 'success');
        } else {
            toast(res.error || t('group_create_err'), 'error');
        }
    });
}

function showInviteModal() {
    if (!state.currentChat || state.currentChat.type !== 'group') return;
    showModal(t('invite_member'), [{ id: 'user', placeholder: t('username_field') }], async ({ user }) => {
        if (!user) return;
        const res = await fetch('/api/groups/invite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group: state.currentChat.id, user }),
        }).then(r => r.json());

        if (res.ok) {
            const ts = Date.now();
            addMessage(state.currentChat.id, { system: true, text: t('invited_group', user), ts });
            renderMessages();
            toast(t('invited', user), 'success');
        } else {
            toast(res.error || t('invite_err'), 'error');
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

    const isCurrent = state.currentChat && state.currentChat.id === chatId;
    if (!isCurrent) {
        chat.unread = (chat.unread || 0) + 1;
        saveState();
    }

    // Notify (sound + vibration + desktop) — but not for own messages echo
    if (msg.from !== state.username) {
        if (getSetting('notifSound', true)) playMessageSound();
        if (getSetting('notifVibro', true)) vibrate(100);
        if (getSetting('notifDesktop', true)) {
            const preview = getSetting('msgPreview', true) ? (msg.text || '') : 'Новое сообщение';
            showDesktopNotification(msg.from, preview);
        }
    }

    renderChatList();
    if (isCurrent) renderMessages();
});

socket.on('file', (info) => {
    const chat = ensureChat(info.from, 'dm', info.from);
    const ts = Date.now();
    const isVoice = info.name && info.name.startsWith('voice_') && info.name.endsWith('.webm');
    const isVideoMsg = info.name && info.name.startsWith('videomsg_') && info.name.endsWith('.webm');
    const msg = {
        from: info.from, file: info.name, size: info.size, fid: info.fid, ts,
    };
    if (isVoice) msg.voice = true;
    if (isVideoMsg) msg.videoMsg = true;
    addMessage(info.from, msg);

    if (!state.currentChat || state.currentChat.id !== info.from) {
        chat.unread = (chat.unread || 0) + 1;
        saveState();
    }

    renderChatList();
    if (state.currentChat?.id === info.from) renderMessages();

    // Notify
    if (getSetting('notifSound', true)) playMessageSound();
    if (getSetting('notifVibro', true)) vibrate(100);
    const label = isVoice ? t('voice_from', info.from)
                 : isVideoMsg ? `Видеосообщение от ${info.from}`
                 : t('file_from', info.from, info.name);
    if (getSetting('notifDesktop', true)) showDesktopNotification(info.from, label);
    toast(label, 'info');
});

// ── Connection status ───────────────────────────────────────────────
let isConnected = true;

socket.on('status', (data) => {
    const wasConnected = isConnected;
    isConnected = data.connected;
    updateConnectionStatus();
    if (!wasConnected && isConnected) {
        toast(t('connection_restored'), 'success');
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
            span.textContent = t('reconnecting');
            sub.appendChild(span);
        }
    } else if (sub) {
        const warn = sub.querySelector('.conn-warn');
        if (warn) warn.remove();
    }
}

// ── Input handling ──────────────────────────────────────────────────
$msgInput?.addEventListener('keydown', (e) => {
    const enterSend = getSetting('enterSend', true);
    if (e.key === 'Enter') {
        if (enterSend && !e.shiftKey && !e.ctrlKey) {
            e.preventDefault();
            sendMessage();
        } else if (!enterSend && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendMessage();
        }
    }
});

$sendBtn?.addEventListener('click', sendMessage);

// ── Typing indicator ────────────────────────────────────────────────
let typingSentAt = 0;
let typingStopTimer = null;
function emitTyping(isTyping) {
    if (!state.currentChat) return;
    socket.emit('typing', {
        to: state.currentChat.id,
        group: state.currentChat.type === 'group',
        typing: !!isTyping,
    });
}

$msgInput?.addEventListener('input', () => {
    $msgInput.style.height = 'auto';
    $msgInput.style.height = Math.min($msgInput.scrollHeight, 120) + 'px';
    // Throttle typing event to once every 3s while user is typing
    const now = Date.now();
    if ($msgInput.value.trim()) {
        if (now - typingSentAt > 3000) {
            emitTyping(true);
            typingSentAt = now;
        }
        clearTimeout(typingStopTimer);
        typingStopTimer = setTimeout(() => {
            emitTyping(false);
            typingSentAt = 0;
        }, 3500);
    } else if (typingSentAt) {
        clearTimeout(typingStopTimer);
        emitTyping(false);
        typingSentAt = 0;
    }
});

// Stop typing once message is sent
const _origSendMessage = typeof sendMessage === 'function' ? sendMessage : null;
// Listen for typing events from peers
const typingState = {}; // chatId -> { users: Set, timer }
socket.on('read', (data) => {
    // Peer (data.from) read all messages we sent them. Mark as read.
    const peer = data?.from;
    if (!peer) return;
    const chat = state.chats[peer];
    if (!chat) return;
    let changed = false;
    for (const m of chat.messages) {
        if (m.from === state.username && !m.read) { m.read = true; changed = true; }
    }
    if (changed) {
        saveState();
        if (state.currentChat && state.currentChat.id === peer) renderMessages();
    }
});

socket.on('typing', (data) => {
    const chatId = data.group ? data.chat : data.from;
    if (!chatId || data.from === state.username) return;
    if (!typingState[chatId]) typingState[chatId] = { users: new Set(), timers: {} };
    const st = typingState[chatId];
    if (data.typing) {
        st.users.add(data.from);
        clearTimeout(st.timers[data.from]);
        st.timers[data.from] = setTimeout(() => {
            st.users.delete(data.from);
            updateTypingUI(chatId);
        }, 5000);
    } else {
        st.users.delete(data.from);
        clearTimeout(st.timers[data.from]);
    }
    updateTypingUI(chatId);
});

function updateTypingUI(chatId) {
    if (!state.currentChat || state.currentChat.id !== chatId) return;
    const st = typingState[chatId];
    const subtitle = $chatHeader.querySelector('.subtitle-text');
    const typingEl = $chatHeader.querySelector('.typing-text');
    if (!typingEl || !subtitle) return;
    const users = st ? Array.from(st.users) : [];
    if (users.length === 0) {
        typingEl.style.display = 'none';
        subtitle.style.display = '';
        return;
    }
    let txt;
    if (state.currentChat.type === 'group') {
        txt = users.length === 1
            ? `${users[0]} ${t('typing_one') || 'печатает...'}`
            : `${users.join(', ')} ${t('typing_many') || 'печатают...'}`;
    } else {
        txt = t('typing_one') || 'печатает...';
    }
    typingEl.textContent = txt;
    typingEl.style.display = '';
    subtitle.style.display = 'none';
}

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

// ═══════════════════════════════════════════════════════════════════
// Last Seen & Profile Photos
// ═══════════════════════════════════════════════════════════════════

async function fetchLastSeen(username) {
    try {
        const res = await fetch(`/api/last-seen/${username}`).then(r => r.json());
        lastSeenCache[username] = res;
        // Update header if still viewing this chat
        if (state.currentChat?.id === username) {
            const sub = document.querySelector('.chat-header .chat-subtitle');
            const dot = document.querySelector('.chat-header .online-dot');
            if (sub) {
                const text = formatLastSeen(res);
                sub.innerHTML = `<span class="online-dot" style="background:${res.online ? 'var(--green)' : 'var(--text-muted)'}"></span> ${esc(text)}`;
            }
        }
    } catch (e) {}
}

async function fetchProfilePhotos(usernames) {
    if (!usernames.length) return;
    try {
        const res = await fetch('/api/profile/photos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ users: usernames }),
        }).then(r => r.json());
        let changed = false;
        for (const [u, photo] of Object.entries(res)) {
            if (photo && profilePhotos[u] !== photo) {
                profilePhotos[u] = photo;
                changed = true;
            }
        }
        if (changed) {
            renderChatList();
            if (state.currentChat) renderHeader();
        }
    } catch (e) {}
}

function showProfilePhotoUpload() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async () => {
        const file = input.files[0];
        if (!file) return;
        if (file.size > 100 * 1024) {
            toast(t('file_too_large'), 'error');
            return;
        }
        const reader = new FileReader();
        reader.onload = async () => {
            const dataUrl = reader.result;
            try {
                // Resize to 200x200 max
                const resized = await resizeImage(dataUrl, 200);
                const res = await fetch('/api/profile/photo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ photo: resized }),
                }).then(r => r.json());
                if (res.ok) {
                    profilePhotos[state.username] = resized;
                    renderChatList();
                    toast(t('photo_updated'), 'success');
                } else {
                    toast(res.error || t('send_error'), 'error');
                }
            } catch (e) {
                toast(t('send_error'), 'error');
            }
        };
        reader.readAsDataURL(file);
    };
    input.click();
}

function resizeImage(dataUrl, maxSize) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            let w = img.width, h = img.height;
            if (w > h) { if (w > maxSize) { h = h * maxSize / w; w = maxSize; } }
            else { if (h > maxSize) { w = w * maxSize / h; h = maxSize; } }
            canvas.width = w;
            canvas.height = h;
            canvas.getContext('2d').drawImage(img, 0, 0, w, h);
            resolve(canvas.toDataURL('image/jpeg', 0.8));
        };
        img.src = dataUrl;
    });
}

// Periodically refresh last seen for current chat
setInterval(() => {
    if (state.currentChat && state.currentChat.type === 'dm') {
        fetchLastSeen(state.currentChat.id);
    }
}, 10000);

// ── Init ────────────────────────────────────────────────────────────
async function init() {
    loadState();
    initTabs();

    // Apply translations and sync language label
    applyStaticTranslations();
    const ll = document.getElementById('lang-label');
    if (ll) ll.textContent = currentLang === 'ru' ? 'Язык: Русский' : 'Language: English';

    // Sync privacy setting with server
    try {
        const lsVis = localStorage.getItem('dns_privacy_last_seen') || 'everyone';
        fetch('/api/privacy/last-seen', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ visibility: lsVis }),
        }).catch(()=>{});
    } catch(e) {}

    // Fetch groups from server
    try {
        const res = await fetch('/api/groups').then(r => r.json());
        for (const gid of res.groups || []) ensureChat(gid, 'group', gid);
    } catch (e) {}

    // Fetch users for initial known list + photos
    try {
        const res = await fetch('/api/users').then(r => r.json());
        state.knownUsers = res.users || [];
        // Fetch profile photos for all known users + chat partners
        const allUsers = new Set(state.knownUsers);
        allUsers.add(state.username);
        for (const id of Object.keys(state.chats)) {
            if (state.chats[id].type === 'dm') allUsers.add(id);
        }
        fetchProfilePhotos([...allUsers]);
    } catch (e) {}

    renderChatList();
}

init();
