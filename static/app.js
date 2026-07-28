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
        you_prefix: 'Вы: ',
        label_voice: 'Голосовое', label_video: 'Видео',
        push_unsupported: 'Push-уведомления не поддерживаются этим браузером',
        push_denied: 'Разрешение на уведомления не выдано',
        push_blocked: 'Уведомления заблокированы для этого сайта — разрешите их в настройках браузера (значок замка в адресной строке)',
        push_enabled: 'Push включён', push_disabled: 'Push выключен',
        push_failed: 'Не удалось подписаться на push',
        push_test_sent: 'Пробное уведомление отправлено',
        push_test_failed: 'Не удалось отправить',
        push_no_sw: 'Service worker не зарегистрирован (нужен HTTPS с доверенным сертификатом или localhost)',
        session_expired: 'Сессия истекла — нужно войти заново',
        auth_forged: 'Подпись не совпадает — отправитель может быть поддельным',
        auth_keychg: 'Ключ собеседника изменился — возможна подмена',
        edited: 'изменено', editing: 'Редактирование',
        forward_to: 'Переслать в…', forwarded_from: 'Переслано от', forwarded_to: 'Переслано в',
        no_other_chats: 'Нет других чатов',
        edit_own_only: 'Можно менять только свои сообщения', edit_text_only: 'Можно менять только текстовые сообщения',
        forward: 'Переслать', edit: 'Изменить',
        pin: 'Закрепить', unpin: 'Открепить', pinned: 'Закреплено', unpinned: 'Откреплено',
        pinned_message: 'Закреплённое сообщение', chat_pinned: 'Чат закреплён', chat_unpinned: 'Чат откреплён',
        chat_search_ph: 'Поиск по сообщениям…',
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
        cmd_placeholder: 'Поиск чатов и команд…', cmd_empty: 'Ничего не найдено',
        cmd_chats: 'Чаты', cmd_actions: 'Команды',
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
        you_prefix: 'You: ',
        label_voice: 'Voice', label_video: 'Video',
        push_unsupported: 'Push notifications are not supported by this browser',
        push_denied: 'Notification permission was not granted',
        push_blocked: 'Notifications are blocked for this site — allow them in your browser settings (lock icon in the address bar)',
        push_enabled: 'Push enabled', push_disabled: 'Push disabled',
        push_failed: 'Could not subscribe to push',
        push_test_sent: 'Test notification sent',
        push_test_failed: 'Could not send',
        push_no_sw: 'Service worker is not registered (needs HTTPS with a trusted certificate, or localhost)',
        session_expired: 'Session expired — please sign in again',
        auth_forged: 'Signature mismatch — sender may be spoofed',
        auth_keychg: 'Peer key changed — possible impersonation',
        edited: 'edited', editing: 'Editing',
        forward_to: 'Forward to…', forwarded_from: 'Forwarded from', forwarded_to: 'Forwarded to',
        no_other_chats: 'No other chats',
        edit_own_only: 'You can only edit your own messages', edit_text_only: 'Only text messages can be edited',
        forward: 'Forward', edit: 'Edit',
        pin: 'Pin', unpin: 'Unpin', pinned: 'Pinned', unpinned: 'Unpinned',
        pinned_message: 'Pinned message', chat_pinned: 'Chat pinned', chat_unpinned: 'Chat unpinned',
        chat_search_ph: 'Search messages…',
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
        cmd_placeholder: 'Search chats and commands…', cmd_empty: 'Nothing found',
        cmd_chats: 'Chats', cmd_actions: 'Commands',
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
    set('#chat-search-input', 'placeholder', t('chat_search_ph'));
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

    // Context menu actions (DOM order: reply, forward, pin, edit, copy, delete, info)
    const ctxButtons = document.querySelectorAll('.ctx-actions button');
    const ctxLabels = [
        ['↩', t('reply')], ['↪', t('forward')],
        ['📌', t('pin')], ['✏️', t('edit')],
        ['📋', t('copy')], ['🗑', t('delete')], ['ℹ', t('info')],
    ];
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
function hashStr(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    return Math.abs(h);
}

// Hue picked straight from the hash instead of indexing into a fixed
// palette - a 10-entry table gave two users a 1-in-10 chance of sharing an
// identical gradient; a continuous hue wheel makes that a 1-in-360 chance
// instead, at the same saturation/lightness the old palette used (so
// contrast against .sender text and the avatar's own initial stays as
// tuned before).
function avatarColor(name) {
    const hue = hashStr(name) % 360;
    return [`hsl(${hue}, 62%, 58%)`, `hsl(${hue}, 62%, 42%)`];
}

// Profile photo cache
const profilePhotos = {};

function avatarHtml(name, isGroup, size) {
    const sz = size || '';
    const colors = avatarColor(name);
    const initial = isGroup ? '#' : name[0].toUpperCase();
    const photo = !isGroup && profilePhotos[name];
    if (photo) {
        return `<div class="avatar ${sz}" style="background:linear-gradient(135deg,${colors[0]},${colors[1]})"><img src="${esc(photo)}" class="avatar-img" alt=""></div>`;
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
    isAnon: document.body.dataset.anon === 'true',
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

// ── Split view: pane A is the original single-pane UI (its currentChat
// getter/setter proxies straight to state.currentChat, so every existing
// piece of code that reads/writes state.currentChat directly - calls,
// uploads, reactions, context menu, forwarding, all of it - keeps working
// completely unchanged). Pane B is a second, independent chat viewer added
// this stage: chat selection + virtualized read view + plain text send
// only, its own currentChat that nothing else touches.
const paneA = {
    suffix: '',
    $chatHeader, $messages, $inputArea, $noChat, $msgInput, $sendBtn,
    $scrollBtn: document.getElementById('scroll-bottom-btn'),
    $scrollUnread: document.getElementById('scroll-unread'),
    get currentChat() { return state.currentChat; },
    set currentChat(v) { state.currentChat = v; },
    msgRows: [], msgRowTop: [], msgWindowStart: 0, msgWindowEnd: -1,
    pendingScrollTarget: null,
    scrollRenderQueued: false,
    forceBottom: false,
    replyingTo: null,
    editingMsg: null,
    searchMatches: [], searchIdx: -1,
    typingSentAt: 0, typingStopTimer: null,
};
let paneB = null;
function ensurePaneB() {
    if (paneB) return paneB;
    paneB = {
        suffix: 'b',
        $chatHeader: document.getElementById('chat-header-b'),
        $messages: document.getElementById('messages-b'),
        $inputArea: document.getElementById('input-area-b'),
        $noChat: document.getElementById('no-chat-b'),
        $msgInput: document.getElementById('msg-input-b'),
        $sendBtn: document.getElementById('send-btn-b'),
        $scrollBtn: document.getElementById('scroll-bottom-btn-b'),
        $scrollUnread: document.getElementById('scroll-unread-b'),
        currentChat: null,
        msgRows: [], msgRowTop: [], msgWindowStart: 0, msgWindowEnd: -1,
        pendingScrollTarget: null,
        scrollRenderQueued: false,
        forceBottom: false,
        replyingTo: null,
        editingMsg: null,
        searchMatches: [], searchIdx: -1,
        typingSentAt: 0, typingStopTimer: null,
    };
    paneB.$sendBtn.addEventListener('click', () => sendMessageInPane(paneB));
    paneB.$msgInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessageInPane(paneB); }
    });
    paneB.$msgInput.addEventListener('input', () => {
        paneB.$msgInput.style.height = 'auto';
        paneB.$msgInput.style.height = Math.min(paneB.$msgInput.scrollHeight, 120) + 'px';
        handleTypingInput(paneB);
    });
    paneB.$messages.addEventListener('scroll', () => {
        if (paneB.scrollRenderQueued) return;
        paneB.scrollRenderQueued = true;
        requestAnimationFrame(() => {
            paneB.scrollRenderQueued = false;
            renderWindowAt(paneB, paneB.$messages.scrollTop, false);
            updateScrollBtn(paneB);
        });
    });
    document.getElementById('chat-search-input-b')?.addEventListener('input', () => runChatSearch(paneB));
    document.getElementById('chat-search-input-b')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); chatSearchStep(e.shiftKey ? -1 : 1, paneB); }
        if (e.key === 'Escape') closeChatSearch(paneB);
    });
    return paneB;
}

function toggleSplitView() {
    const el = document.getElementById('chat-area-b');
    const btn = document.getElementById('split-view-btn');
    if (!el) return;
    const isOpen = el.style.display !== 'none';
    if (isOpen) {
        el.style.display = 'none';
        btn?.classList.remove('active');
    } else {
        ensurePaneB();
        el.style.display = 'flex';
        btn?.classList.add('active');
    }
}
const $notifs      = $('#notifications');

// ── Toast notifications ─────────────────────────────────────────────
function toast(text, type = 'info') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = text;
    $toasts.appendChild(el);
    setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 300); }, 3000);
}

// ── localStorage persistence (optional AES-GCM encryption) ──────────
const STORAGE_KEY = () => `dns_messenger_${state.username}`;
const ENC_FLAG_KEY = () => `dns_enc_${state.username}`;   // '1' when encryption is enabled
const ENC_SALT_KEY = () => `dns_enc_salt_${state.username}`;

let cryptoKey = null;        // in-memory CryptoKey (AES-GCM) when unlocked
let saveDebounce = null;

function isEncEnabled() { return localStorage.getItem(ENC_FLAG_KEY()) === '1'; }

function b64(bytes) { return btoa(String.fromCharCode(...new Uint8Array(bytes))); }
function unb64(str) { return Uint8Array.from(atob(str), c => c.charCodeAt(0)); }

async function deriveKey(passphrase, salt) {
    const enc = new TextEncoder();
    const baseKey = await crypto.subtle.importKey('raw', enc.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey(
        { name: 'PBKDF2', salt, iterations: 150000, hash: 'SHA-256' },
        baseKey,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt']
    );
}

function collectState() {
    const data = {};
    for (const [id, chat] of Object.entries(state.chats)) {
        data[id] = {
            type: chat.type, name: chat.name, messages: chat.messages, lastTs: chat.lastTs,
            pinnedId: chat.pinnedId || null, chatPinned: !!chat.chatPinned,
        };
    }
    return data;
}

// How to persist state:
//   'encrypt'   — we hold the key → AES-GCM.
//   'skip'      — encryption is ENABLED but we don't hold the key (the unlock
//                 prompt was cancelled or failed). Writing plaintext here would
//                 both leak the history the user asked to encrypt AND overwrite
//                 the existing encrypted blob — so we persist NOTHING this
//                 session instead of silently downgrading to plaintext.
//   'plaintext' — encryption is genuinely off (user's choice).
function storageWriteMode(hasKey, encEnabled) {
    if (hasKey) return 'encrypt';
    if (encEnabled) return 'skip';
    return 'plaintext';
}

async function writeState(data) {
    const mode = storageWriteMode(!!cryptoKey, isEncEnabled());
    if (mode === 'skip') {
        if (!writeState._warned) {
            writeState._warned = true;
            console.warn('storage is locked — not persisting (refusing plaintext fallback)');
            if (typeof toast === 'function') {
                toast('Хранилище заблокировано: история не сохраняется без пароля', 'info');
            }
        }
        return;
    }
    const json = JSON.stringify(data);
    if (mode === 'encrypt') {
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, cryptoKey, new TextEncoder().encode(json));
        localStorage.setItem(STORAGE_KEY(), 'enc:' + b64(iv) + ':' + b64(ct));
    } else {
        localStorage.setItem(STORAGE_KEY(), json);
    }
}

function saveState() {
    if (!state.username) return;
    // Debounce async writes; keep a synchronous plaintext fallback if not encrypting
    clearTimeout(saveDebounce);
    const data = collectState();
    saveDebounce = setTimeout(() => { writeState(data).catch(() => {}); }, 120);
}

async function loadState() {
    if (!state.username) return;
    try {
        const raw = localStorage.getItem(STORAGE_KEY());
        if (!raw) return;
        let json;
        if (raw.startsWith('enc:')) {
            if (!cryptoKey) return; // can't decrypt without key (should have been unlocked)
            const [, ivB, ctB] = raw.split(':');
            const pt = await crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: unb64(ivB) }, cryptoKey, unb64(ctB)
            );
            json = new TextDecoder().decode(pt);
        } else {
            json = raw;
        }
        const data = JSON.parse(json);
        for (const [id, chat] of Object.entries(data)) {
            state.chats[id] = { ...chat, unread: 0 };
        }
    } catch (e) { console.warn('loadState failed', e); }
}

// Unlock encrypted storage at startup (prompt for passphrase)
async function unlockStorage() {
    if (!isEncEnabled()) return true;
    const saltStr = localStorage.getItem(ENC_SALT_KEY());
    if (!saltStr) return true;
    const salt = unb64(saltStr);
    for (let attempt = 0; attempt < 3; attempt++) {
        const pass = prompt(attempt === 0
            ? 'Введите пароль для расшифровки переписки:'
            : 'Неверный пароль. Попробуйте ещё раз:');
        if (pass === null) return false; // user cancelled → run without decrypting
        try {
            cryptoKey = await deriveKey(pass, salt);
            // Verify by trying to decrypt current blob
            const raw = localStorage.getItem(STORAGE_KEY());
            if (raw && raw.startsWith('enc:')) {
                const [, ivB, ctB] = raw.split(':');
                await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(ivB) }, cryptoKey, unb64(ctB));
            }
            return true;
        } catch (e) { cryptoKey = null; }
    }
    return false;
}

// Enable encryption with a new passphrase (re-encrypts current state)
async function enableEncryption(passphrase) {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    cryptoKey = await deriveKey(passphrase, salt);
    localStorage.setItem(ENC_SALT_KEY(), b64(salt));
    localStorage.setItem(ENC_FLAG_KEY(), '1');
    await writeState(collectState());
}

// Disable encryption (decrypts and stores plaintext)
async function disableEncryption() {
    const data = collectState();
    cryptoKey = null;
    localStorage.removeItem(ENC_FLAG_KEY());
    localStorage.removeItem(ENC_SALT_KEY());
    await writeState(data);
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
    renderHeader();
    $noChat.style.display = 'none';
    $chatHeader.style.display = '';
    // Must be visible before renderMessages() runs: it reads
    // $messages.clientHeight to size the virtualized window and sets
    // scrollTop to jump to the bottom, both no-ops on a display:none element.
    $messages.style.display = '';
    $inputArea.style.display = '';
    renderMessages();
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

// Pane B's chat selection - kept separate from selectChat() rather than
// generalizing it, so the primary pane's entry point (called from ~dozens
// of onclick handlers throughout the file) stays completely untouched.
function selectChatInPane(pane, id) {
    const chat = state.chats[id];
    if (!chat) return;
    pane.currentChat = { type: chat.type, id };
    chat.unread = 0;
    if (chat.type === 'dm') {
        try { socket.emit('read', { to: id }); } catch(e) {}
    }
    saveState();
    renderChatList();
    pane.$noChat.style.display = 'none';
    pane.$chatHeader.style.display = '';
    pane.$messages.style.display = '';
    pane.$inputArea.style.display = '';
    renderHeaderB();
    renderMessagesForPane(pane);
}

// Minimal header for the second pane - Stage 1 doesn't duplicate calls
// or group member management there yet.
function renderHeaderB() {
    if (!paneB || !paneB.currentChat) return;
    const chat = state.chats[paneB.currentChat.id];
    if (!chat) return;
    const isGroup = chat.type === 'group';
    paneB.$chatHeader.innerHTML = `
        ${avatarHtml(chat.name, isGroup, 'sm')}
        <div class="header-info">
            <div class="chat-title">${esc(chat.name)}</div>
            <div class="chat-subtitle">
                <span class="typing-text" style="display:none;color:var(--green);font-style:italic"></span>
            </div>
        </div>
        <div class="header-actions">
            <button onclick="openChatSearch(paneB)" title="Поиск по чату">&#x1F50D;</button>
            <button onclick="closePaneB()" title="Закрыть">&times;</button>
        </div>
    `;
}

function closePaneB() {
    if (paneB) paneB.currentChat = null;
    toggleSplitView();
}

async function sendMessageInPane(pane) {
    if (pane === paneA) return sendMessage();
    if (!pane.currentChat || !pane.$msgInput.value.trim()) return;
    let text = pane.$msgInput.value.trim();
    pane.$msgInput.value = '';
    if (pane.typingSentAt) {
        try { emitTyping(false, pane); } catch (e) {}
        pane.typingSentAt = 0;
        clearTimeout(pane.typingStopTimer);
    }
    pane.$msgInput.style.height = 'auto';

    const chat = state.chats[pane.currentChat.id];

    // ── Edit mode ──
    if (pane.editingMsg) {
        const target = pane.editingMsg;
        hideComposerBar(pane);
        target.text = text;
        target.edited = true;
        saveState();
        renderMessagesForPane(pane);
        renderChatList();
        if (chat.type === 'dm') {
            try {
                await fetch('/api/send', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ to: pane.currentChat.id, text: `__EDIT__:${target.id}:${text}` }),
                });
            } catch (e) {}
        }
        return;
    }

    if (pane.replyingTo) {
        text = `> ${pane.replyingTo.from}: ${pane.replyingTo.text.slice(0, 60)}\n${text}`;
        hideComposerBar(pane);
    }

    const ts = Date.now();
    addMessage(pane.currentChat.id, { from: state.username, text, ts });
    pane.forceBottom = true;
    renderMessagesForPane(pane);
    renderChatList();

    const url = chat.type === 'group' ? '/api/groups/send' : '/api/send';
    const body = chat.type === 'group'
        ? { group: pane.currentChat.id, text }
        : { to: pane.currentChat.id, text };

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

function toggleChatPin(id) {
    const chat = state.chats[id];
    if (!chat) return;
    chat.chatPinned = !chat.chatPinned;
    if (chat.chatPinned) {
        // New pins go to the bottom of the pinned group, not the top -
        // matches where a freshly-dragged-in item would land in most
        // reorderable lists, and avoids bumping an existing manual order
        // the user just set up.
        const maxOrder = Object.values(state.chats)
            .filter(c => c.chatPinned && c !== chat)
            .reduce((m, c) => Math.max(m, c.pinOrder || 0), 0);
        chat.pinOrder = maxOrder + 1;
    }
    saveState();
    renderChatList();
    toast(chat.chatPinned ? (t('chat_pinned') || 'Чат закреплён') : (t('chat_unpinned') || 'Чат откреплён'), 'success');
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
        .sort((a, b) => {
            // Pinned chats float to the top
            const pa = a[1].chatPinned ? 1 : 0;
            const pb = b[1].chatPinned ? 1 : 0;
            if (pa !== pb) return pb - pa;
            // Within the pinned group, respect manual drag order instead of
            // recency - that's the whole point of pinning something.
            if (pa && pb) return (a[1].pinOrder || 0) - (b[1].pinOrder || 0);
            return b[1].lastTs - a[1].lastTs;
        });

    $chatList.innerHTML = '';
    for (const [id, chat] of entries) {
        const isActive = state.currentChat?.id === id;
        const isGroup = chat.type === 'group';
        const lastMsg = chat.messages[chat.messages.length - 1];
        let preview = '';
        if (lastMsg) {
            if (lastMsg.system) preview = lastMsg.text;
            else {
                const sender = lastMsg.from === state.username ? t('you_prefix') : (isGroup ? lastMsg.from + ': ' : '');
                // bodyOf strips the "> name: quoted\n" reply prefix and labels voice/video/file
                preview = sender + bodyOf(lastMsg);
            }
        }
        const timeStr = lastMsg ? formatTime(lastMsg.ts) : '';

        const div = document.createElement('div');
        div.className = `chat-item${isActive ? ' active' : ''}${chat.chatPinned ? ' chat-pinned' : ''}`;
        div.dataset.chatId = id;
        div.onclick = (e) => {
            // Ctrl/Cmd-click routes into the second pane instead of the
            // primary one, when split view is actually open - otherwise a
            // stray modifier-click would silently do nothing.
            if ((e.ctrlKey || e.metaKey) && document.getElementById('chat-area-b')?.style.display !== 'none' && paneB) {
                selectChatInPane(paneB, id);
            } else {
                selectChat(id);
            }
        };
        div.oncontextmenu = (e) => { e.preventDefault(); toggleChatPin(id); };
        div.innerHTML = `
            ${chat.chatPinned ? '<span class="pin-drag-handle" title="Перетащить">⠿</span>' : ''}
            ${avatarHtml(chat.name, isGroup)}
            <div class="chat-info">
                <div class="chat-name-row">
                    <span class="chat-name">${esc(chat.name)}</span>
                </div>
                <div class="chat-preview">${esc(preview.slice(0, 80))}</div>
            </div>
            <div class="chat-meta">
                ${chat.chatPinned ? '<span class="chat-pin-icon">📌</span>' : ''}
                <span class="chat-time">${timeStr}</span>
                ${chat.unread ? `<span class="unread-badge">${chat.unread}</span>` : ''}
            </div>
        `;
        // Long-press to pin/unpin, plus swipe (either direction - it's a
        // toggle, not two separate actions like the message swipe-to-reply)
        // as a faster alternative on touch. Mirrors the swipe mechanics
        // already used for messages (damped drag, flash past threshold,
        // spring back on release).
        let cpTimer;
        let swipeStartX = 0, swipeStartY = 0, chatSwiping = false, chatSwipeFired = false;
        const CHAT_SWIPE_THRESHOLD = 70;
        div.addEventListener('touchstart', (e) => {
            // The drag handle runs its own pointer-based reorder - don't
            // also arm the swipe/long-press-to-pin gesture underneath it.
            if (e.target.closest('.pin-drag-handle')) return;
            const t0 = e.touches[0];
            swipeStartX = t0.clientX; swipeStartY = t0.clientY;
            chatSwiping = true; chatSwipeFired = false;
            cpTimer = setTimeout(() => { toggleChatPin(id); chatSwiping = false; }, 550);
        }, { passive: true });
        div.addEventListener('touchmove', (e) => {
            clearTimeout(cpTimer);
            if (!chatSwiping) return;
            const t0 = e.touches[0];
            const dx = t0.clientX - swipeStartX;
            const dy = t0.clientY - swipeStartY;
            if (Math.abs(dy) > 14) { chatSwiping = false; div.style.transform = ''; return; }
            const damped = Math.sign(dx) * Math.min(Math.abs(dx), 90);
            div.style.transform = `translateX(${damped}px)`;
            if (!chatSwipeFired && Math.abs(dx) > CHAT_SWIPE_THRESHOLD) {
                chatSwipeFired = true;
                navigator.vibrate?.(20);
                div.classList.add('swipe-flash');
            }
        }, { passive: true });
        div.addEventListener('touchend', () => {
            clearTimeout(cpTimer);
            div.style.transition = 'transform 0.25s ease';
            div.style.transform = '';
            setTimeout(() => { div.style.transition = ''; div.classList.remove('swipe-flash'); }, 300);
            if (chatSwipeFired) toggleChatPin(id);
            chatSwiping = false;
        });
        $chatList.appendChild(div);
    }
    updateBadges();
}

// ── Pinned-chat drag reorder ─────────────────────────────────────────
// Pointer Events (not separate touch/mouse handlers, unlike the swipe
// gestures above) since this needs one continuous drag path either way,
// and doing it twice would double an already-fiddly piece of code. Only
// starts from the .pin-drag-handle grip - a plain drag on the row itself
// would collide with the swipe-to-pin/long-press-to-pin gestures chat
// items already have.
(function initPinDragReorder() {
    let dragEl = null;

    function onPointerDown(e) {
        const handle = e.target.closest('.pin-drag-handle');
        if (!handle) return;
        const item = handle.closest('.chat-item');
        if (!item) return;
        e.preventDefault();
        dragEl = item;
        dragEl.classList.add('dragging');
        handle.setPointerCapture(e.pointerId);
    }

    function onPointerMove(e) {
        if (!dragEl) return;
        // Only reorder against other pinned rows - dragging past the
        // pinned/unpinned boundary doesn't unpin anything, it just has
        // nothing left to swap with.
        const siblings = [...$chatList.querySelectorAll('.chat-item.chat-pinned')].filter(el => el !== dragEl);
        for (const sib of siblings) {
            const r = sib.getBoundingClientRect();
            const mid = r.top + r.height / 2;
            const sibIsAfter = !!(dragEl.compareDocumentPosition(sib) & Node.DOCUMENT_POSITION_FOLLOWING);
            if (sibIsAfter && e.clientY > mid) {
                $chatList.insertBefore(dragEl, sib.nextSibling);
                break;
            } else if (!sibIsAfter && e.clientY < mid) {
                $chatList.insertBefore(dragEl, sib);
                break;
            }
        }
    }

    function onPointerUp() {
        if (!dragEl) return;
        dragEl.classList.remove('dragging');
        // Persist whatever order the drag left the pinned rows in.
        [...$chatList.querySelectorAll('.chat-item.chat-pinned')].forEach((el, i) => {
            const chat = state.chats[el.dataset.chatId];
            if (chat) chat.pinOrder = i;
        });
        saveState();
        dragEl = null;
    }

    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('pointermove', onPointerMove);
    document.addEventListener('pointerup', onPointerUp);
    document.addEventListener('pointercancel', onPointerUp);
})();

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
            <button onclick="openChatSearch()" title="Поиск по чату">&#x1F50D;</button>
            ${!isGroup ? `
                <button onclick="showSafetyNumber('${esc(chat.name)}')" title="Число безопасности">&#x1F512;</button>
                <button onclick="startCall(false)" title="Голосовой вызов">&#x1F4DE;</button>
                <button onclick="startCall(true)" title="Видеозвонок">&#x1F4F9;</button>
            ` : ''}
            ${isGroup ? `
                <button onclick="showGroupMembers()" title="Участники">&#x1F465;</button>
                <button class="invite-btn" onclick="showInviteModal()">+ Участник</button>
            ` : ''}
        </div>
    `;

    // Refresh pinned bar for this chat
    renderPinnedBar();

    // Fetch last seen for DM chats
    if (!isGroup) {
        fetchLastSeen(chat.name);
    }
}

// ── Render: Messages ────────────────────────────────────────────────
// Virtualized: chat.messages has no cap (kept forever locally), so a long
// history could mean thousands of rows. Rebuilding all of them as DOM on
// every renderMessages() call (new message, reaction toggle, edit...) would
// cost O(history) every time. Instead we build lightweight per-row metadata
// (no DOM, cheap even for thousands of rows) once per call, then only
// materialize DOM for rows inside the current scroll viewport + overscan,
// using two spacer elements to stand in for the rest so scrollHeight/
// scrollTop still behave like the full list is there.
const rowHeightCache = new Map();
const DEFAULT_ROW_HEIGHT = 56;
const ROW_OVERSCAN = 8;
// msgRows/msgRowTop/msgWindowStart/msgWindowEnd/pendingScrollTarget all
// live on each pane object now (paneA/paneB) instead of as module globals -
// scrollToQuoted/scrollToPinned/focusSearchMatch set paneA.pendingScrollTarget
// to force the window onto a specific message before scrolling to it.

// Metadata-only pass: exactly the grouping/date-separator logic the old
// single-pass loop used, just producing descriptors instead of DOM so it
// stays cheap to run on every render regardless of history length.
function buildMessageRows(chat) {
    const isGroup = chat.type === 'group';
    const rows = [];
    let lastSender = null;
    let lastDate = null;
    for (const msg of chat.messages) {
        const msgDate = new Date(msg.ts).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
        if (msgDate !== lastDate) {
            lastDate = msgDate;
            rows.push({ type: 'date', key: 'date:' + rows.length, label: msgDate });
        }
        if (msg.system) {
            rows.push({ type: 'sys', key: 'sys:' + (msg.id || rows.length), msg });
            lastSender = null;
            continue;
        }
        const isNew = msg.from !== lastSender;
        lastSender = msg.from;
        rows.push({ type: 'msg', key: msg.id || ('idx:' + rows.length), msg, isNew, isGroup });
    }
    return rows;
}

function computeRowTops(rows) {
    const tops = new Array(rows.length + 1);
    let acc = 0;
    for (let i = 0; i < rows.length; i++) {
        tops[i] = acc;
        acc += rowHeightCache.get(rows[i].key) || DEFAULT_ROW_HEIGHT;
    }
    tops[rows.length] = acc;
    return tops;
}

// Row counts here top out at a few thousand even for a very long chat, so a
// linear scan (run at most once per animation frame - see the scroll
// listener) stays well under a frame budget; not worth a binary search.
function findRowAtOffset(rowTop, offset) {
    for (let i = 0; i < rowTop.length - 1; i++) {
        if (rowTop[i + 1] > offset) return i;
    }
    return Math.max(0, rowTop.length - 2);
}

function buildRowNode(row, pane) {
    if (row.type === 'date') {
        const sep = document.createElement('div');
        sep.className = 'date-separator';
        sep.innerHTML = `<span>${row.label}</span>`;
        return sep;
    }
    if (row.type === 'sys') {
        const sys = document.createElement('div');
        sys.className = 'system-msg';
        sys.innerHTML = `<span>${esc(row.msg.text)}</span>`;
        return sys;
    }
    return buildMessageNode(row.msg, row.isNew, row.isGroup, pane);
}

// Builds one .message DOM node - unchanged from the previous single-pass
// renderMessages() loop body (every message-type branch and its
// swipe/context-menu/reaction wiring), just extracted so it can be called
// per-row from the windowed renderer instead of once per message in the
// full history.
//
// Reactions, context menu, swipe-to-reply, and search highlighting are all
// pane-aware (via ctxTargetPane / pane.searchMatches / pane.replyingTo).
// Reply-quote-click and Edit still only make sense in pane A: quoting jumps
// via paneA.pendingScrollTarget, and Edit needs a flow that isn't built for
// pane B yet.
function buildMessageNode(msg, isNew, isGroup, pane) {
    const isMine = msg.from === state.username;
    const div = document.createElement('div');

    // Skip deleted messages or show placeholder
    if (msg.deleted) {
        div.className = `message ${isMine ? 'sent' : 'received'} deleted${isNew ? ' first' : ''}`;
        div.innerHTML = `<div class="msg-text">Сообщение удалено<span class="msg-footer">
            <span class="msg-time">${formatTime(msg.ts)}</span>
        </span></div>`;
        return div;
    }

    // Data attributes for context menu
    div.dataset.msgId = msg.id || '';
    div.dataset.chatId = pane.currentChat.id;

    const reactionsHtml = renderReactions(msg, pane);

        // Detect a leading reply quote of the form "> name: text\n..." and split it out.
        // qName/qText come straight from the message's own (fully attacker-controlled)
        // text — any user can type "> x: y" as their first line, no reply feature needed.
        let replyHtml = '';
        let replyQName = '', replyQText = '';
        let bodyText = msg.text || '';
        if (bodyText.startsWith('> ')) {
            const nl = bodyText.indexOf('\n');
            if (nl > 0) {
                const quoteLine = bodyText.slice(2, nl);
                bodyText = bodyText.slice(nl + 1);
                const colon = quoteLine.indexOf(':');
                if (colon > 0) { replyQName = quoteLine.slice(0, colon); replyQText = quoteLine.slice(colon + 1).trim(); }
                else { replyQText = quoteLine; }
                // No onclick attribute: interpolating qName into an inline JS-string
                // argument was exploitable even through esc() — the browser decodes
                // HTML entities before the handler body is parsed as JS, so an escaped
                // quote still lands as a real quote at the JS-string layer and breaks
                // out (confirmed live: alert() fired via a hand-typed "> name: text").
                // The click behavior is now wired below via addEventListener, passing
                // replyQName/replyQText as real JS values — never serialized into code.
                replyHtml = `<div class="reply-quote"><div class="reply-name">${esc(replyQName)}</div><div class="reply-text">${esc(replyQText)}</div></div>`;
            }
        }
        const editedHtml = msg.edited ? `<span class="msg-edited">${t('edited') || '\u0438\u0437\u043c\u0435\u043d\u0435\u043d\u043e'}</span>` : '';
        const checkHtml = isMine ? `<span class="msg-status${msg.read ? ' read' : ''}">${msg.read ? '\u2713\u2713' : '\u2713'}</span>` : '';
        // \u041f\u043e\u0434\u043f\u0438\u0441\u044c \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u0435\u043b\u044f \u043d\u0435 \u0441\u043e\u0448\u043b\u0430\u0441\u044c (\u043f\u043e\u0434\u0434\u0435\u043b\u043a\u0430) \u0438\u043b\u0438 \u043a\u043b\u044e\u0447 \u043f\u0438\u0440\u0430 \u0441\u043c\u0435\u043d\u0438\u043b\u0441\u044f \u2014
        // \u043f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0430\u0435\u043c \u044f\u0432\u043d\u043e, \u044d\u0442\u043e \u0432\u0430\u0436\u043d\u0435\u0435 \u043a\u043e\u0441\u043c\u0435\u0442\u0438\u043a\u0438.
        const authWarn = (msg.auth === 'forged' || msg.auth === 'unverified' || msg.auth === 'key_changed')
            ? `<div class="msg-authwarn">\u26a0 ${msg.auth === 'key_changed' ? t('auth_keychg') : t('auth_forged')}</div>`
            : '';

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
            const progressHtml = msg.uploading ? `
                <div class="upload-progress">
                    <div class="upload-progress-fill" style="width:0%"></div>
                </div>
                <div class="upload-progress-pct">0%</div>` : '';
            const failedHtml = msg.uploadFailed ? `<div class="upload-failed">⚠ ${t('file_send_err') || 'Ошибка отправки'}</div>` : '';
            div.innerHTML = `
                <div class="file-icon-wrap">${msg.uploading ? '⬆️' : '📄'}</div>
                <div class="file-details">
                    ${!isMine && isGroup && isNew ? `<div class="sender" style="color:${avatarColor(msg.from)[0]}">${esc(msg.from)}</div>` : ''}
                    <div class="file-name">${esc(msg.file)}</div>
                    <div class="file-size">${formatSize(msg.size)}</div>
                    ${progressHtml}
                    ${failedHtml}
                </div>
                ${reactionsHtml}
            `;
            if (msg.fid && !isMine && !msg.uploading) {
                div.onclick = () => downloadFile(msg.fid, msg.from, msg.file);
                div.title = 'Click to download';
            }
        } else {
            div.className = `message ${isMine ? 'sent' : 'received'}${isNew ? ' first' : ''}`;
            const previewUrl = firstUrl(bodyText);
            const previewHtml = previewUrl ? linkPreviewHtml(previewUrl) : '';
            div.innerHTML = `
                ${!isMine && isGroup && isNew ? `<div class="sender" style="color:${avatarColor(msg.from)[0]}">${esc(msg.from)}</div>` : ''}
                ${replyHtml}
                <div class="msg-text">${linkify(esc(bodyText))}<span class="msg-footer">
                    ${editedHtml}
                    <span class="msg-time">${formatTime(msg.ts)}</span>
                    ${checkHtml}
                </span></div>
                ${previewHtml}
                ${reactionsHtml}
            `;
        }

        if (authWarn) { div.classList.add('msg-unverified'); div.insertAdjacentHTML('afterbegin', authWarn); }

        // Pinned highlight uses this pane's own chat, not a global - pane B
        // has an independent currentChat.
        const curChat = pane.currentChat && state.chats[pane.currentChat.id];
        if (curChat && curChat.pinnedId === msg.id) div.classList.add('is-pinned');

        // Context menu on right-click - works in both panes (reactions,
        // copy/pin/delete/forward/info are pane-aware via ctxTargetPane).
        // Reply/Edit hide themselves inside showContextMenu when pane !== paneA,
        // since the composer bar they need only exists in pane A so far.
        div.addEventListener('contextmenu', (e) => { e.preventDefault(); showContextMenu(e, msg, pane); });

        // Search highlight - data-driven off this pane's own searchMatches
        // rather than a post-render DOM query, so it stays correct however the
        // virtualized window happens to be sliced (a match scrolled out of the
        // DOM still gets highlighted the moment it scrolls back into the window).
        if (msg.id && pane.searchMatches.includes(msg.id)) {
            div.classList.add('search-hit');
            if (msg.id === pane.searchMatches[pane.searchIdx]) div.classList.add('search-current');
        }

        if (pane === paneA) {
            // Reply-quote click: attached here (not inline onclick) so replyQName/
            // replyQText travel as real JS values, never serialized into an attribute
            // that gets parsed as code.
            const quoteEl = div.querySelector('.reply-quote');
            if (quoteEl) {
                quoteEl.addEventListener('click', (e) => {
                    e.stopPropagation();
                    scrollToQuoted(replyQName, replyQText);
                });
            }
        }

        // Swipe-to-reply (Telegram-like) + long-press context menu - works in
        // both panes; startReply/showContextMenu take pane so the reply lands
        // in whichever pane's composer the swipe happened in.
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
                showContextMenu(t0, msg, pane);
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
            if (swipeFired) startReply(msg, pane);
            swiping = false;
        });

        // Mouse drag swipe (desktop)
        let mDown = false, mStartX = 0, mFired = false;
        let mHoldTimer;
        div.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            mDown = true; mStartX = e.clientX; mFired = false;
            div.classList.add('holding');
            mHoldTimer = setTimeout(() => { showContextMenu(e, msg, pane); }, 500);
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
            if (mFired) startReply(msg, pane);
        };
        div.addEventListener('mouseup', mUp);
        div.addEventListener('mouseleave', mUp);

    return div;
}

// Rebuilds the visible slice [start, end] into $messages behind two spacer
// divs, then measures what actually got rendered to refine rowHeightCache.
// force=true always rebuilds (used after data changes, e.g. a new message
// or a toggled reaction, even if the index range happens to match).
function renderWindowAt(pane, scrollTop, force) {
    if (!pane.msgRows.length) {
        pane.$messages.innerHTML = '';
        pane.msgWindowStart = 0; pane.msgWindowEnd = -1;
        return;
    }
    const viewport = pane.$messages.clientHeight || 400;
    let start = findRowAtOffset(pane.msgRowTop, scrollTop);
    let end = start;
    while (end < pane.msgRows.length - 1 && pane.msgRowTop[end + 1] < scrollTop + viewport) end++;
    start = Math.max(0, start - ROW_OVERSCAN);
    end = Math.min(pane.msgRows.length - 1, end + ROW_OVERSCAN);

    if (!force && start === pane.msgWindowStart && end === pane.msgWindowEnd) {
        pane.$messages.scrollTop = scrollTop;
        return;
    }
    pane.msgWindowStart = start;
    pane.msgWindowEnd = end;

    pane.$messages.innerHTML = '';
    const topSpacer = document.createElement('div');
    topSpacer.className = 'msg-spacer';
    topSpacer.style.height = pane.msgRowTop[start] + 'px';
    pane.$messages.appendChild(topSpacer);

    for (let i = start; i <= end; i++) pane.$messages.appendChild(buildRowNode(pane.msgRows[i], pane));

    const bottomSpacer = document.createElement('div');
    bottomSpacer.className = 'msg-spacer';
    bottomSpacer.style.height = Math.max(0, pane.msgRowTop[pane.msgRows.length] - pane.msgRowTop[end + 1]) + 'px';
    pane.$messages.appendChild(bottomSpacer);

    pane.$messages.scrollTop = scrollTop;
    remeasureVisibleRows(pane);
}

// Measures the actual on-screen gap between consecutive rendered rows
// (rather than el.offsetHeight alone) so the cached height already
// includes whatever the CSS layout adds between rows (currently .messages'
// flex `gap`) without this code needing to know that detail exists.
// rowHeightCache is shared across panes (keyed by message id, so a row's
// measured height is valid regardless of which pane rendered it first).
function remeasureVisibleRows(pane) {
    const nodes = pane.$messages.children; // [topSpacer, ...rows, bottomSpacer]
    if (nodes.length < 3) return;
    let changed = false;
    for (let i = 1; i < nodes.length - 1; i++) {
        const row = pane.msgRows[pane.msgWindowStart + (i - 1)];
        if (!row) continue;
        const slot = nodes[i + 1].getBoundingClientRect().top - nodes[i].getBoundingClientRect().top;
        if (slot > 0 && Math.abs((rowHeightCache.get(row.key) || 0) - slot) > 0.5) {
            rowHeightCache.set(row.key, slot);
            changed = true;
        }
    }
    if (!changed) return;
    pane.msgRowTop = computeRowTops(pane.msgRows);
    nodes[0].style.height = pane.msgRowTop[pane.msgWindowStart] + 'px';
    nodes[nodes.length - 1].style.height = Math.max(0, pane.msgRowTop[pane.msgRows.length] - pane.msgRowTop[pane.msgWindowEnd + 1]) + 'px';
}

paneA.$messages.addEventListener('scroll', () => {
    if (paneA.scrollRenderQueued) return;
    paneA.scrollRenderQueued = true;
    requestAnimationFrame(() => {
        paneA.scrollRenderQueued = false;
        renderWindowAt(paneA, paneA.$messages.scrollTop, false);
        updateScrollBtn(paneA);
    });
});

// renderMessages() stays the single chokepoint every existing call site
// already uses ("something changed, refresh whatever's on screen") - it
// now also refreshes pane B when it has a chat open, so none of those 25+
// call sites throughout the file needed to change.
function renderMessages() {
    if (state.currentChat) renderMessagesForPane(paneA);
    if (paneB && paneB.currentChat) renderMessagesForPane(paneB);
}

function renderMessagesForPane(pane) {
    const chat = state.chats[pane.currentChat.id];
    if (!chat) return;
    const wasNearBottom = pane.forceBottom || isNearBottomIn(pane);
    pane.forceBottom = false;

    pane.msgRows = buildMessageRows(chat);
    pane.msgRowTop = computeRowTops(pane.msgRows);

    if (!pane.msgRows.length) {
        pane.$messages.innerHTML = '';
        pane.msgWindowStart = 0; pane.msgWindowEnd = -1;
        if (pane === paneA) renderPinnedBar();
        updateScrollBtn(pane);
        return;
    }

    let scrollTop;
    const pending = pane.pendingScrollTarget;
    pane.pendingScrollTarget = null;
    let pendingIdx = -1;
    if (pending) {
        pendingIdx = pane.msgRows.findIndex(r => r.type === 'msg' && r.msg.id === pending.id);
        if (pendingIdx >= 0) {
            const viewport = pane.$messages.clientHeight || 400;
            scrollTop = Math.max(0, pane.msgRowTop[pendingIdx] - viewport / 2);
        }
    }
    if (scrollTop === undefined) {
        scrollTop = wasNearBottom ? pane.msgRowTop[pane.msgRows.length] : pane.$messages.scrollTop;
    }

    renderWindowAt(pane, scrollTop, true);

    if (pending && pendingIdx >= 0) {
        const el = pane.$messages.querySelector(`.message[data-msg-id="${pending.id}"]`);
        if (el && pending.flash) {
            el.classList.add(pending.flash);
            setTimeout(() => el.classList.remove(pending.flash), 900);
        }
    }

    if (pane === paneA) renderPinnedBar();
    updateScrollBtn(pane);
}

// ── Actions ─────────────────────────────────────────────────────────
async function sendMessage() {
    if (!state.currentChat || !$msgInput.value.trim()) return;
    let text = $msgInput.value.trim();
    $msgInput.value = '';
    $msgInput.style.height = 'auto';
    if (paneA.typingSentAt) {
        try { emitTyping(false, paneA); } catch(e) {}
        paneA.typingSentAt = 0;
        clearTimeout(paneA.typingStopTimer);
    }

    const chat = state.chats[state.currentChat.id];

    // ── Edit mode ──
    if (paneA.editingMsg) {
        const target = paneA.editingMsg;
        hideComposerBar();
        target.text = text;
        target.edited = true;
        saveState();
        renderMessages();
        renderChatList();
        if (chat.type === 'dm') {
            try {
                await fetch('/api/send', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ to: state.currentChat.id, text: `__EDIT__:${target.id}:${text}` }),
                });
            } catch (e) {}
        }
        return;
    }

    // ── Reply mode: prepend quote line ──
    if (paneA.replyingTo) {
        text = `> ${paneA.replyingTo.from}: ${paneA.replyingTo.text.slice(0, 60)}\n${text}`;
        hideComposerBar(paneA);
    }

    const ts = Date.now();
    addMessage(state.currentChat.id, { from: state.username, text, ts });
    paneA.forceBottom = true;
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

async function sendFile(pane = paneA) {
    if (!pane.currentChat) return;
    if (pane.currentChat.type === 'group') {
        toast(t('call_only_dm'), 'info');
        return;
    }
    (pane === paneA ? $fileInput : $fileInputB).click();
}

async function handleFilePicked(pane, fileInput) {
    const file = fileInput.files[0];
    if (!file || !pane.currentChat) return;

    if (file.size > 512 * 1024) {
        toast(t('file_max'), 'error');
        fileInput.value = '';
        return;
    }

    const ts = Date.now();
    const uploadId = 'up_' + ts;
    addMessage(pane.currentChat.id, { from: state.username, file: file.name, size: file.size, ts, uploading: true, uploadId, id: uploadId });
    pane.forceBottom = true;
    renderMessagesForPane(pane);
    renderChatList();

    const fd = new FormData();
    fd.append('to', pane.currentChat.id);
    fd.append('file', file);

    try {
        await uploadFileWithProgress('/api/file/send', fd, uploadId);
        markUploadDone(uploadId, true, pane);
        toast(t('file_sent'), 'success');
    } catch (e) {
        markUploadDone(uploadId, false, pane);
        toast((e && e.message) || t('file_send_err'), 'error');
    }
    fileInput.value = '';
}
$fileInput?.addEventListener('change', () => handleFilePicked(paneA, $fileInput));
const $fileInputB = document.getElementById('file-input-b');
$fileInputB?.addEventListener('change', () => handleFilePicked(paneB || ensurePaneB(), $fileInputB));

// Upload with progress via XHR; updates the progress bar on the placeholder message
function uploadFileWithProgress(url, formData, uploadId) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', url);
        xhr.upload.onprogress = (e) => {
            if (!e.lengthComputable) return;
            const pct = Math.round((e.loaded / e.total) * 100);
            const bar = document.querySelector(`.message[data-msg-id="${uploadId}"] .upload-progress-fill`);
            const label = document.querySelector(`.message[data-msg-id="${uploadId}"] .upload-progress-pct`);
            if (bar) bar.style.width = pct + '%';
            if (label) label.textContent = pct + '%';
        };
        xhr.onload = () => {
            try {
                const res = JSON.parse(xhr.responseText || '{}');
                if (res.ok) resolve(res);
                else reject(new Error(res.error || t('file_send_err')));
            } catch (e) { reject(new Error(t('file_send_err'))); }
        };
        xhr.onerror = () => reject(new Error(t('server_unavailable')));
        xhr.send(formData);
    });
}
function markUploadDone(uploadId, ok, pane = paneA) {
    const chat = pane.currentChat && state.chats[pane.currentChat.id];
    if (!chat) return;
    const msg = chat.messages.find(m => m.id === uploadId);
    if (msg) {
        msg.uploading = false;
        if (!ok) msg.uploadFailed = true;
        saveState();
        if (pane.currentChat) renderMessagesForPane(pane);
    }
}

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
    // Prefer the service worker so notifications persist even when the tab is backgrounded/closing
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        try {
            navigator.serviceWorker.controller.postMessage({ type: 'notify', title, body, tag: 'dns-msg-' + title });
            return;
        } catch (e) {}
    }
    try {
        const n = new Notification(title, { body, icon: '/static/icon-192.png' });
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
    chatWallpaper: 'dns_set_wallpaper',  // none | dots | grid | aurora | solid | custom
    chatWallpaperColor: 'dns_set_wallpaper_color',
    chatWallpaperImage: 'dns_set_wallpaper_image',  // data URL
    listWallpaper: 'dns_set_list_wallpaper',        // none | dots | grid | aurora | solid | custom
    listWallpaperColor: 'dns_set_list_wallpaper_color',
    listWallpaperImage: 'dns_set_list_wallpaper_image',
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
    const wallColor = getSetting('chatWallpaperColor', '#0e1621');
    const wallImg = getSetting('chatWallpaperImage', '');
    const listWall = getSetting('listWallpaper', 'none');
    const listWallColor = getSetting('listWallpaperColor', '#17212b');
    const listWallImg = getSetting('listWallpaperImage', '');
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.dataset.accent = accent;
    root.dataset.wallpaper = wall;
    root.dataset.listWallpaper = listWall;
    root.style.setProperty('--font-scale', scale);
    root.style.setProperty('--chat-wall-color', wallColor);
    root.style.setProperty('--chat-wall-image', wallImg ? `url("${wallImg}")` : 'none');
    root.style.setProperty('--list-wall-color', listWallColor);
    root.style.setProperty('--list-wall-image', listWallImg ? `url("${listWallImg}")` : 'none');
    root.classList.toggle('no-anim', !animOn);
}
applySettings();

// ── Empty-state parallax ─────────────────────────────────────────────
// Subtle pointer-follow on the "no chat selected" placeholder. Respects the
// animations toggle and prefers-reduced-motion directly (unlike CSS
// transitions, a JS-computed inline transform isn't stopped by --no-anim's
// duration override, so it needs its own check).
(function initEmptyStateParallax() {
    const content = document.getElementById('no-chat-content');
    if (!content) return;
    const noChat = document.getElementById('no-chat');
    const MAX_PX = 14;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    document.addEventListener('mousemove', (e) => {
        if (document.documentElement.classList.contains('no-anim') || reduceMotion.matches) return;
        if (!noChat || noChat.offsetParent === null) return;
        const rect = noChat.getBoundingClientRect();
        const relX = (e.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
        const relY = (e.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
        const px = Math.max(-1, Math.min(1, relX)) * MAX_PX;
        const py = Math.max(-1, Math.min(1, relY)) * MAX_PX;
        content.style.setProperty('--px', px.toFixed(1) + 'px');
        content.style.setProperty('--py', py.toFixed(1) + 'px');
    });
})();

// ── Avatar 3D tilt ────────────────────────────────────────────────────
// Delegated on document (not per-element listeners) since avatars are
// re-created constantly by renderChatList()/renderMessages() innerHTML
// replaces - attaching directly to each .avatar would mean rebinding on
// every re-render.
(function initAvatarTilt() {
    if (!window.matchMedia('(hover: hover)').matches) return; // no hover on touch
    const MAX_TILT = 14;
    document.addEventListener('mousemove', (e) => {
        const el = e.target.closest && e.target.closest('.avatar');
        if (!el) return;
        if (document.documentElement.classList.contains('no-anim')) return;
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        const rect = el.getBoundingClientRect();
        const px = (e.clientX - rect.left) / rect.width - 0.5;
        const py = (e.clientY - rect.top) / rect.height - 0.5;
        const rx = (-py * MAX_TILT).toFixed(1);
        const ry = (px * MAX_TILT).toFixed(1);
        el.style.transform = `perspective(300px) rotateX(${rx}deg) rotateY(${ry}deg)`;
    });
    document.addEventListener('mouseout', (e) => {
        const el = e.target.closest && e.target.closest('.avatar');
        if (!el || el.contains(e.relatedTarget)) return;
        el.style.transform = '';
    });
})();

// ── Command palette (Ctrl+K) ─────────────────────────────────────────
let cmdkItems = [];
let cmdkActive = 0;

function cmdkActionList() {
    return [
        { icon: '\u{1F4AC}', label: t('new_chat'), run: () => showNewDM() },
        { icon: '\u{1F465}', label: t('new_group'), run: () => showNewGroup() },
        { icon: '\u{1F464}', label: t('contacts'), run: () => showContacts() },
        { icon: '⚙', label: t('privacy'), run: () => showSettings() },
        { icon: '⚙', label: t('admin_panel'), run: () => { window.location.href = '/admin'; } },
        { icon: '\u{1F6AA}', label: t('logout'), run: () => doLogout() },
    ];
}

function openCommandPalette() {
    if (document.getElementById('cmdk-overlay')) return;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay cmdk-overlay';
    overlay.id = 'cmdk-overlay';
    overlay.innerHTML = `
        <div class="modal cmdk-modal">
            <input type="text" class="cmdk-input" id="cmdk-input" placeholder="${esc(t('cmd_placeholder'))}" autocomplete="off" spellcheck="false">
            <div class="cmdk-list" id="cmdk-list"></div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) closeCommandPalette(); });

    const input = overlay.querySelector('#cmdk-input');
    input.addEventListener('input', () => renderCommandPalette(input.value));
    input.addEventListener('keydown', onCmdkKeydown);

    const list = overlay.querySelector('#cmdk-list');
    list.addEventListener('click', (e) => {
        const item = e.target.closest('.cmdk-item');
        if (item) runCommandItem(parseInt(item.dataset.idx, 10));
    });
    list.addEventListener('mousemove', (e) => {
        const item = e.target.closest('.cmdk-item');
        if (!item) return;
        const idx = parseInt(item.dataset.idx, 10);
        if (idx !== cmdkActive) { cmdkActive = idx; highlightCmdkActive(); }
    });

    renderCommandPalette('');
    input.focus();
}

function closeCommandPalette() {
    document.getElementById('cmdk-overlay')?.remove();
}

function renderCommandPalette(query) {
    const q = query.trim().toLowerCase();
    const list = document.getElementById('cmdk-list');
    if (!list) return;

    const chatMatches = Object.entries(state.chats)
        .filter(([id, c]) => !q || (c.name || id).toLowerCase().includes(q))
        .sort((a, b) => (b[1].lastTs || 0) - (a[1].lastTs || 0))
        .slice(0, 8);
    const actionMatches = cmdkActionList().filter(a => !q || a.label.toLowerCase().includes(q));

    cmdkItems = [];
    cmdkActive = 0;
    let html = '';

    if (chatMatches.length) {
        html += `<div class="cmdk-section-label">${esc(t('cmd_chats'))}</div>`;
        for (const [id, c] of chatMatches) {
            const idx = cmdkItems.length;
            cmdkItems.push({ run: () => selectChat(id) });
            html += `<div class="cmdk-item" data-idx="${idx}">${avatarHtml(c.name || id, c.type === 'group', 'xs')}<span>${esc(c.name || id)}</span></div>`;
        }
    }
    if (actionMatches.length) {
        html += `<div class="cmdk-section-label">${esc(t('cmd_actions'))}</div>`;
        for (const a of actionMatches) {
            const idx = cmdkItems.length;
            cmdkItems.push({ run: a.run });
            html += `<div class="cmdk-item" data-idx="${idx}"><span class="cmdk-item-icon">${a.icon}</span><span>${esc(a.label)}</span></div>`;
        }
    }
    if (!cmdkItems.length) {
        html = `<div class="cmdk-empty">${esc(t('cmd_empty'))}</div>`;
    }

    list.innerHTML = html;
    highlightCmdkActive();
}

function highlightCmdkActive() {
    document.querySelectorAll('#cmdk-list .cmdk-item').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.idx, 10) === cmdkActive);
    });
}

function runCommandItem(idx) {
    const item = cmdkItems[idx];
    if (!item) return;
    closeCommandPalette();
    item.run();
}

function onCmdkKeydown(e) {
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (cmdkItems.length) { cmdkActive = (cmdkActive + 1) % cmdkItems.length; highlightCmdkActive(); }
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (cmdkItems.length) { cmdkActive = (cmdkActive - 1 + cmdkItems.length) % cmdkItems.length; highlightCmdkActive(); }
    } else if (e.key === 'Enter') {
        e.preventDefault();
        runCommandItem(cmdkActive);
    } else if (e.key === 'Escape') {
        e.preventDefault();
        closeCommandPalette();
    }
}

document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const open = document.getElementById('cmdk-overlay');
        if (open) closeCommandPalette(); else openCommandPalette();
    }
});

function showSettings(initialSection) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay settings-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const sections = [
        { id: 'general',  icon: '\u2699',    title: 'Основные' },
        { id: 'notif',    icon: '\u{1F514}', title: 'Уведомления и звуки' },
        { id: 'privacy',  icon: '\u{1F512}', title: 'Конфиденциальность' },
        { id: 'security', icon: '\u{1F5DD}', title: 'Passkeys' },
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

// Показывает набор запасных кодов РОВНО ОДИН РАЗ (сервер отдаёт их в открытом
// виде только в ответ на генерацию — второй раз получить их же уже нельзя,
// на диске лежат только хэши). Копирование — единственное действие, кроме
// закрытия: удалить показанное с экрана мы не можем, но хотя бы не оставляем
// лишних путей его продублировать.
function showBackupCodesModal(codes) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <h3>Запасные коды входа</h3>
            <p style="color:var(--text-muted);font-size:13px;margin-bottom:12px">
                Каждый код работает один раз — используйте, если потеряли устройство
                с passkey. Сохраните их сейчас: повторно показать их будет нельзя,
                только сгенерировать новый набор (старые при этом перестанут работать).
            </p>
            <pre style="background:var(--bg-input);padding:12px;border-radius:8px;
                        font-size:14px;line-height:1.8;user-select:all;white-space:pre-wrap">${esc(codes.join('\n'))}</pre>
            <div class="modal-actions">
                <button class="btn btn-secondary" id="copy-backup-codes">Скопировать</button>
                <button class="btn" onclick="this.closest('.modal-overlay').remove()">Готово</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#copy-backup-codes')?.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(codes.join('\n'));
            toast('Скопировано', 'success');
        } catch (e) {
            toast('Не удалось скопировать', 'error');
        }
    });
}

// Код восстановления пароля отдаётся в открытом виде РОВНО ОДИН РАЗ (как и
// backup-коды выше) — на диске лежит только шифротекст ключей под ним,
// повторно код с сервера получить нельзя, только перегенерировать (и тогда
// старый безвозвратно перестаёт работать).
function showRecoveryCodeModal(code) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <h3>Код восстановления пароля</h3>
            <p style="color:var(--text-muted);font-size:13px;margin-bottom:12px">
                Единственный способ задать новый пароль, если забудете текущий —
                без него забытый пароль не восстановить никак. Сохраните код
                сейчас в надёжном месте, отдельно от этого устройства: повторно
                показать его будет нельзя, только сгенерировать новый (старый
                тогда перестанет работать).
            </p>
            <pre style="background:var(--bg-input);padding:12px;border-radius:8px;
                        font-size:16px;letter-spacing:1px;text-align:center;user-select:all">${esc(code)}</pre>
            <div class="modal-actions">
                <button class="btn btn-secondary" id="copy-recovery-code">Скопировать</button>
                <button class="btn" onclick="this.closest('.modal-overlay').remove()">Готово</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#copy-recovery-code')?.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(code);
            toast('Скопировано', 'success');
        } catch (e) {
            toast('Не удалось скопировать', 'error');
        }
    });
}

// Число безопасности (фаза 3, docs/ratchet-plan.md) — опциональная ручная
// сверка identity-ключей вне канала (лично/голосом), не блокирует отправку.
// TOFU-пиннинг уже ловит подмену ключа на лету — это дополнительная сверка
// именно для первого контакта, до того как есть с чем сравнивать пин.
async function showSafetyNumber(peer) {
    let data;
    try {
        data = await fetch(`/api/safety-number/${encodeURIComponent(peer)}`).then(r => r.json());
    } catch (e) {
        toast('Не удалось получить число безопасности', 'error');
        return;
    }
    if (!data.ok) {
        toast(data.error || 'Число безопасности недоступно', 'error');
        return;
    }
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <h3>Число безопасности с ${esc(peer)}</h3>
            <p style="color:var(--text-muted);font-size:13px;margin-bottom:12px">
                Сверьте это число с собеседником по другому каналу (лично, голосом) —
                если оно совпадает посимвольно с обеих сторон, ключи шифрования
                подлинные и никто не подменил их посередине. Необязательный шаг:
                переписка и так защищена сквозным шифрованием без этой сверки.
            </p>
            <pre style="background:var(--bg-input);padding:12px;border-radius:8px;
                        font-size:15px;letter-spacing:1px;text-align:center;
                        user-select:all;line-height:1.6">${esc(data.number)}</pre>
            <label style="display:flex;align-items:center;gap:8px;margin:12px 0;cursor:pointer">
                <input type="checkbox" id="safety-verified-check" ${data.verified ? 'checked' : ''}>
                <span>Число сверено, ключи подтверждены</span>
            </label>
            <div class="modal-actions">
                <button class="btn btn-secondary" id="copy-safety-number">Скопировать</button>
                <button class="btn" onclick="this.closest('.modal-overlay').remove()">Готово</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#copy-safety-number')?.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(data.number);
            toast('Скопировано', 'success');
        } catch (e) {
            toast('Не удалось скопировать', 'error');
        }
    });
    overlay.querySelector('#safety-verified-check')?.addEventListener('change', async (e) => {
        try {
            const res = await fetch(`/api/safety-number/${encodeURIComponent(peer)}/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ verified: e.target.checked }),
            }).then(r => r.json());
            if (!res.ok) throw new Error(res.error || 'failed');
            toast(e.target.checked ? 'Отмечено как сверено' : 'Отметка снята', 'success');
        } catch (err) {
            e.target.checked = !e.target.checked;
            toast('Не удалось сохранить отметку', 'error');
        }
    });
}

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
            <label class="set-row">
                <div>
                    <div class="set-label">Push при закрытой вкладке</div>
                    <div class="set-hint">Уведомления от сервера, когда мессенджер полностью закрыт. Требует интернета.</div>
                </div>
                <span class="switch ${isPushEnabled()?'on':''}" id="push-switch"></span>
            </label>
            <div class="set-row">
                <button class="btn btn-secondary" id="test-notif">Протестировать звук</button>
                <button class="btn btn-secondary" id="test-push">Проверить push</button>
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
    if (id === 'security' && state.isAnon) {
        return `
            <h4 class="set-section-title">Passkeys (вход по биометрии)</h4>
            <div class="set-hint">
                Недоступно для анонимного режима — тут нет пароля, а passkey
                защищает именно вход по паролю как второй фактор. Для этого
                выберите «Регистрация» на экране входа.
            </div>
        `;
    }
    if (id === 'security') {
        // Список заполняется асинхронно в wireSettingsSection.
        return `
            <h4 class="set-section-title">Passkeys (вход по биометрии)</h4>
            <div class="set-hint" style="margin-bottom:14px">
                Отпечаток пальца, Face ID или ключ устройства как второй фактор входа —
                в дополнение к паролю, не вместо него. Приватный ключ никогда не
                покидает ваше устройство и не передаётся на сервер.
            </div>
            <div id="passkey-list" class="set-row" style="flex-direction:column;align-items:stretch">
                <div class="set-hint">Загрузка…</div>
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">Добавить passkey с этого устройства</div>
                    <div class="set-hint">Потребует пароль при следующем входе, если ещё не зарегистрирован ни один passkey — после добавления входить будет нужно паролем + подтверждением здесь.</div>
                </div>
                <button class="btn btn-secondary" id="add-passkey">Добавить</button>
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">Запасные коды</div>
                    <div class="set-hint">На случай утери устройства с passkey. Каждый код одноразовый.
                        <span id="backup-codes-status"></span>
                    </div>
                </div>
                <button class="btn btn-secondary" id="regen-backup-codes">Создать новые</button>
            </div>
            <h4 class="set-section-title" style="margin-top:22px">Восстановление аккаунта</h4>
            <div class="set-hint" style="margin-bottom:14px">
                Пароль не хранится на сервере в открытом виде — он же шифрует ваши
                ключи переписки, поэтому забытый пароль восстановить нельзя. Код
                восстановления — единственный запасной путь: сохраните его в
                надёжном месте (менеджер паролей, сейф) отдельно от устройства.
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">Код восстановления пароля</div>
                    <div class="set-hint">Позволяет задать новый пароль, если забыли текущий.
                        <span id="recovery-code-status"></span>
                    </div>
                </div>
                <button class="btn btn-secondary" id="regen-recovery-code">Создать код</button>
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
            ${selectRow('Фон переписки', 'chatWallpaper', 'none', [
                { val: 'none',    label: 'По умолчанию' },
                { val: 'dots',    label: 'Точки' },
                { val: 'grid',    label: 'Сетка' },
                { val: 'aurora',  label: 'Сияние' },
                { val: 'sunset',  label: '🌅 Закат' },
                { val: 'ocean',   label: '🌊 Океан' },
                { val: 'forest',  label: '🌲 Лес' },
                { val: 'candy',   label: '🍬 Карамель' },
                { val: 'nebula',  label: '🌌 Туманность' },
                { val: 'emerald', label: '💚 Изумруд' },
                { val: 'snow',    label: '❄️ Снег' },
                { val: 'solid',   label: 'Цвет' },
                { val: 'custom',  label: 'Изображение' },
            ])}
            <div class="set-row">
                <div class="set-label">Цвет фона переписки</div>
                <input type="color" class="set-color" data-color-key="chatWallpaperColor" value="${getSetting('chatWallpaperColor', '#0e1621')}">
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">Своё изображение (переписка)</div>
                    <div class="set-hint">Сохраняется локально, до ~1 МБ</div>
                </div>
                <div style="display:flex;gap:8px">
                    <button class="btn btn-secondary" id="upload-chat-wall">Загрузить</button>
                    <button class="btn btn-secondary" id="clear-chat-wall">Сбросить</button>
                </div>
            </div>

            ${selectRow('Фон списка чатов', 'listWallpaper', 'none', [
                { val: 'none',    label: 'По умолчанию' },
                { val: 'dots',    label: 'Точки' },
                { val: 'grid',    label: 'Сетка' },
                { val: 'aurora',  label: 'Сияние' },
                { val: 'sunset',  label: '🌅 Закат' },
                { val: 'ocean',   label: '🌊 Океан' },
                { val: 'forest',  label: '🌲 Лес' },
                { val: 'candy',   label: '🍬 Карамель' },
                { val: 'nebula',  label: '🌌 Туманность' },
                { val: 'emerald', label: '💚 Изумруд' },
                { val: 'snow',    label: '❄️ Снег' },
                { val: 'solid',   label: 'Цвет' },
                { val: 'custom',  label: 'Изображение' },
            ])}
            <div class="set-row">
                <div class="set-label">Цвет фона списка</div>
                <input type="color" class="set-color" data-color-key="listWallpaperColor" value="${getSetting('listWallpaperColor', '#17212b')}">
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">Своё изображение (список чатов)</div>
                    <div class="set-hint">Сохраняется локально, до ~1 МБ</div>
                </div>
                <div style="display:flex;gap:8px">
                    <button class="btn btn-secondary" id="upload-list-wall">Загрузить</button>
                    <button class="btn btn-secondary" id="clear-list-wall">Сбросить</button>
                </div>
            </div>
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
                    <div class="set-label">🔐 Шифрование переписки</div>
                    <div class="set-hint">${isEncEnabled() ? 'Включено — история зашифрована паролем' : 'Защитить локальную историю паролем (AES-256)'}</div>
                </div>
                <span class="switch ${isEncEnabled()?'on':''}" id="enc-toggle"></span>
            </div>
            <div class="set-row">
                <div>
                    <div class="set-label">📲 Установить приложение</div>
                    <div class="set-hint">Добавить на рабочий стол (PWA), работает офлайн</div>
                </div>
                <button class="btn btn-secondary" id="install-app">Установить</button>
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
    // Color pickers
    root.querySelectorAll('.set-color').forEach(inp => {
        inp.addEventListener('input', () => setSetting(inp.dataset.colorKey, inp.value));
    });

    if (id === 'appear') {
        const pickImage = (storageKey, wallKey) => {
            const inp = document.createElement('input');
            inp.type = 'file';
            inp.accept = 'image/*';
            inp.onchange = () => {
                const f = inp.files?.[0];
                if (!f) return;
                if (f.size > 1024 * 1024) { toast('Файл слишком большой (макс 1 МБ)', 'error'); return; }
                const reader = new FileReader();
                reader.onload = () => {
                    try {
                        localStorage.setItem(SETTINGS_KEYS[storageKey], reader.result);
                        setSetting(wallKey, 'custom');
                        toast('Фон обновлён', 'success');
                    } catch (e) {
                        toast('Недостаточно места в хранилище', 'error');
                    }
                };
                reader.readAsDataURL(f);
            };
            inp.click();
        };
        byId('upload-chat-wall')?.addEventListener('click', () => pickImage('chatWallpaperImage', 'chatWallpaper'));
        byId('clear-chat-wall')?.addEventListener('click', () => {
            localStorage.removeItem(SETTINGS_KEYS.chatWallpaperImage);
            setSetting('chatWallpaper', 'none');
            toast('Сброшено', 'success');
        });
        byId('upload-list-wall')?.addEventListener('click', () => pickImage('listWallpaperImage', 'listWallpaper'));
        byId('clear-list-wall')?.addEventListener('click', () => {
            localStorage.removeItem(SETTINGS_KEYS.listWallpaperImage);
            setSetting('listWallpaper', 'none');
            toast('Сброшено', 'success');
        });
    }

    if (id === 'notif') {
        byId('test-notif')?.addEventListener('click', () => { playMessageSound(); vibrate(120); });
        byId('test-push')?.addEventListener('click', sendTestPush);
        const pushSw = byId('push-switch');
        // Флаг в localStorage — намерение, а не факт. Разрешение могли отозвать
        // в настройках браузера, подписку — сбросить: сверяемся и не показываем
        // включённым то, что на деле не работает.
        if (pushSw && isPushEnabled()) {
            hasLivePushSubscription().then((live) => {
                if (!live) {
                    localStorage.removeItem(PUSH_FLAG_KEY());
                    pushSw.classList.remove('on');
                }
            });
        }
        pushSw?.addEventListener('click', async (e) => {
            e.preventDefault();
            const turningOn = !pushSw.classList.contains('on');
            pushSw.classList.toggle('on', turningOn);   // отклик сразу, до запроса разрешения
            if (turningOn) {
                const ok = await enablePush();
                pushSw.classList.toggle('on', ok);      // откат, если отказали
            } else {
                await disablePush();
            }
        });
    }
    if (id === 'privacy') {
        byId('logout-all')?.addEventListener('click', () => {
            if (confirm('Выйти из аккаунта?')) doLogout();
        });
    }
    if (id === 'security' && !state.isAnon) {
        const listEl = byId('passkey-list');
        const renderList = async () => {
            if (!listEl) return;
            if (!webauthnSupported()) {
                listEl.innerHTML = '<div class="set-hint">Этот браузер не поддерживает passkeys.</div>';
                byId('add-passkey')?.setAttribute('disabled', 'disabled');
                return;
            }
            try {
                const res = await fetch('/api/webauthn/credentials').then(r => r.json());
                const creds = (res.ok && res.credentials) || [];
                if (!creds.length) {
                    listEl.innerHTML = '<div class="set-hint">Passkeys ещё не добавлены — вход только по паролю.</div>';
                    return;
                }
                listEl.innerHTML = '';
                for (const c of creds) {
                    const row = document.createElement('div');
                    row.className = 'set-row';
                    const info = document.createElement('div');
                    const label = document.createElement('div');
                    label.className = 'set-label';
                    label.textContent = c.label;               // textContent — метка это пользовательский ввод
                    const hint = document.createElement('div');
                    hint.className = 'set-hint';
                    hint.textContent = 'Добавлен ' + new Date(c.added_ts * 1000).toLocaleDateString();
                    info.appendChild(label);
                    info.appendChild(hint);
                    const removeBtn = document.createElement('button');
                    removeBtn.className = 'btn btn-danger';
                    removeBtn.textContent = 'Удалить';
                    removeBtn.addEventListener('click', async () => {
                        if (!confirm('Удалить этот passkey?')) return;
                        await fetch('/api/webauthn/credentials/remove', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ id: c.id }),
                        });
                        renderList();
                    });
                    row.appendChild(info);
                    row.appendChild(removeBtn);
                    listEl.appendChild(row);
                }
            } catch (e) {
                listEl.innerHTML = '<div class="set-hint">Не удалось загрузить список.</div>';
            }
        };
        renderList();
        byId('add-passkey')?.addEventListener('click', async () => {
            const label = prompt('Название устройства (для себя же)', 'Мой ноутбук') || 'Passkey';
            const addBtn = byId('add-passkey');
            if (addBtn) { addBtn.disabled = true; addBtn.textContent = 'Ожидание устройства…'; }
            try {
                const res = await registerPasskey(label);
                toast('Passkey добавлен', 'success');
                await renderList();
                await renderBackupStatus();
                if (res.backup_codes) showBackupCodesModal(res.backup_codes);
            } catch (e) {
                toast(e.message || 'Не удалось добавить passkey', 'error');
            } finally {
                if (addBtn) { addBtn.disabled = false; addBtn.textContent = 'Добавить'; }
            }
        });

        const backupEl = byId('backup-codes-status');
        const renderBackupStatus = async () => {
            if (!backupEl) return;
            try {
                const res = await fetch('/api/webauthn/backup-codes/status').then(r => r.json());
                if (!res.ok) { backupEl.textContent = ''; return; }
                backupEl.textContent = res.total
                    ? `Осталось ${res.remaining} из ${res.total}`
                    : 'Ещё не созданы';
            } catch (e) {
                backupEl.textContent = '';
            }
        };
        renderBackupStatus();
        byId('regen-backup-codes')?.addEventListener('click', async () => {
            if (!confirm('Сгенерировать новый набор запасных кодов? Старые (даже неиспользованные) перестанут работать.')) return;
            try {
                const res = await fetch('/api/webauthn/backup-codes/generate', { method: 'POST' }).then(r => r.json());
                if (!res.ok) { toast(res.error || 'Не удалось создать коды', 'error'); return; }
                showBackupCodesModal(res.codes);
                renderBackupStatus();
            } catch (e) {
                toast('Не удалось создать коды', 'error');
            }
        });

        const recoveryEl = byId('recovery-code-status');
        const renderRecoveryStatus = async () => {
            if (!recoveryEl) return;
            try {
                const res = await fetch('/api/recovery/status').then(r => r.json());
                if (!res.ok) { recoveryEl.textContent = ''; return; }
                recoveryEl.textContent = res.has_code ? 'Код создан' : 'Ещё не создан';
            } catch (e) {
                recoveryEl.textContent = '';
            }
        };
        renderRecoveryStatus();
        byId('regen-recovery-code')?.addEventListener('click', async () => {
            const already = byId('recovery-code-status')?.textContent === 'Код создан';
            const warn = already
                ? 'Создать новый код восстановления? Старый (даже неиспользованный) перестанет работать.'
                : 'Создать код восстановления? Он единственный способ вернуть доступ, если вы забудете пароль — сохраните его в надёжном месте, отдельно от этого устройства.';
            if (!confirm(warn)) return;
            try {
                const res = await fetch('/api/recovery/generate', { method: 'POST' }).then(r => r.json());
                if (!res.ok) { toast(res.error || 'Не удалось создать код', 'error'); return; }
                showRecoveryCodeModal(res.code);
                renderRecoveryStatus();
            } catch (e) {
                toast('Не удалось создать код', 'error');
            }
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
        byId('install-app')?.addEventListener('click', () => promptInstall());
        byId('enc-toggle')?.addEventListener('click', async (e) => {
            const sw = e.currentTarget;
            if (isEncEnabled()) {
                // Disable
                if (!confirm('Отключить шифрование? История будет храниться в открытом виде.')) return;
                await disableEncryption();
                sw.classList.remove('on');
                toast('Шифрование отключено', 'success');
                buildSettingsSection && renderSettingsData(root, overlay);
            } else {
                const p1 = prompt('Придумайте пароль для шифрования переписки (мин. 8 символов):');
                if (p1 === null) return;
                if (p1.length < 8) { toast('Слишком короткий пароль', 'error'); return; }
                const p2 = prompt('Повторите пароль:');
                if (p2 === null) return;
                if (p1 !== p2) { toast('Пароли не совпадают', 'error'); return; }
                try {
                    await enableEncryption(p1);
                    sw.classList.add('on');
                    toast('Шифрование включено. Пароль потребуется при следующем входе.', 'success');
                    renderSettingsData(root, overlay);
                } catch (err) {
                    toast('Не удалось включить шифрование', 'error');
                }
            }
        });
    }
}

// Re-render the "data" settings section in place (after enc toggle)
function renderSettingsData(root, overlay) {
    root.innerHTML = buildSettingsSection('data');
    wireSettingsSection('data', root, overlay);
}

// ═══════════════════════════════════════════════════════════════════
// Voice Messages (record audio, send as file via DNS tunnel)
// ═══════════════════════════════════════════════════════════════════

// Only one voice recording can be in flight at a time (one MediaRecorder,
// one mic) - same rationale as calls staying singular in split view.
// voiceState.pane tracks which pane's chat it's recording for and which
// pane's input area shows the indicator; pressing the mic button in
// either pane targets that pane.
let voiceState = {
    recording: false,
    mediaRecorder: null,
    chunks: [],
    stream: null,
    startTime: null,
    timerInterval: null,
    pane: null,
};

const $voiceBtn = document.getElementById('voice-rec-btn');
const $voiceBtnB = document.getElementById('voice-rec-btn-b');
function voiceBtnFor(pane) { return pane === paneA ? $voiceBtn : $voiceBtnB; }

async function toggleVoiceRecord(pane = paneA) {
    if (voiceState.recording) {
        stopVoiceRecord();
    } else {
        startVoiceRecord(pane);
    }
}

async function startVoiceRecord(pane = paneA) {
    if (!pane.currentChat || pane.currentChat.type !== 'dm') {
        toast('Voice messages are only available in direct chats', 'info');
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        voiceState.stream = stream;
        voiceState.chunks = [];
        voiceState.pane = pane;

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
            sendVoiceMessage(blob, duration, voiceState.pane);
            voiceState.stream.getTracks().forEach(t => t.stop());
            voiceState.stream = null;
        };

        recorder.start(100);
        voiceState.recording = true;
        voiceState.startTime = Date.now();
        voiceBtnFor(pane)?.classList.add('recording');

        // Show recording indicator in input area
        showRecordingIndicator(pane);

    } catch (e) {
        showMediaError('voice messages');
    }
}

function stopVoiceRecord(cancel) {
    if (!voiceState.recording) return;
    voiceState.recording = false;
    voiceBtnFor(voiceState.pane)?.classList.remove('recording');
    hideRecordingIndicator(voiceState.pane);

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

function showRecordingIndicator(pane = paneA) {
    const $wrap = pane.$inputArea.querySelector('.input-wrap');
    const $textarea = pane.$msgInput;
    const $attach = pane.$inputArea.querySelector('.attach-btn');
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

function hideRecordingIndicator(pane = paneA) {
    if (voiceState.timerInterval) {
        clearInterval(voiceState.timerInterval);
        voiceState.timerInterval = null;
    }
    const indicator = document.getElementById('rec-indicator');
    if (indicator) indicator.remove();
    const $textarea = pane.$msgInput;
    const $attach = pane.$inputArea.querySelector('.attach-btn');
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

async function sendVoiceMessage(blob, duration, pane = paneA) {
    if (!pane.currentChat) return;
    if (blob.size > 512 * 1024) {
        toast(t('voice_too_large'), 'error');
        return;
    }

    const ts = Date.now();
    const filename = `voice_${ts}.webm`;
    addMessage(pane.currentChat.id, {
        from: state.username,
        voice: true,
        file: filename,
        size: blob.size,
        duration: duration,
        ts,
    });
    pane.forceBottom = true;
    renderMessagesForPane(pane);
    renderChatList();

    const fd = new FormData();
    fd.append('to', pane.currentChat.id);
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
    startTime: null, timerInterval: null, previewEl: null, pane: null,
};
const $videoBtn = document.getElementById('video-rec-btn');
const $videoBtnB = document.getElementById('video-rec-btn-b');
function videoBtnFor(pane) { return pane === paneA ? $videoBtn : $videoBtnB; }

async function toggleVideoRecord(pane = paneA) {
    if (videoState.recording) stopVideoRecord();
    else startVideoRecord(pane);
}

async function startVideoRecord(pane = paneA) {
    if (!pane.currentChat || pane.currentChat.type !== 'dm') {
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
        videoState.pane = pane;

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
            sendVideoMessage(blob, duration, videoState.pane);
            videoState.stream?.getTracks().forEach(t => t.stop());
            videoState.stream = null;
            hideVideoPreview();
        };

        recorder.start(100);
        videoState.recording = true;
        videoState.startTime = Date.now();
        videoBtnFor(pane)?.classList.add('recording');
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
    videoBtnFor(videoState.pane)?.classList.remove('recording');
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

async function sendVideoMessage(blob, duration, pane = paneA) {
    if (!pane.currentChat) return;
    if (blob.size > 4 * 1024 * 1024) { toast('Видео слишком большое (макс 4 МБ)', 'error'); return; }
    const ts = Date.now();
    const filename = `videomsg_${ts}.webm`;
    addMessage(pane.currentChat.id, {
        from: state.username, videoMsg: true, file: filename,
        size: blob.size, duration, ts,
    });
    pane.forceBottom = true;
    renderMessagesForPane(pane);
    renderChatList();
    const fd = new FormData();
    fd.append('to', pane.currentChat.id);
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
let ctxTargetPane = null;
let ctxOpenedAt = 0;
const $ctxMenu = document.getElementById('msg-context-menu');

function showContextMenu(e, msg, pane = paneA) {
    ctxTargetMsg = msg;
    ctxTargetPane = pane;
    ctxOpenedAt = Date.now();
    if (!$ctxMenu) return;

    // Highlight selected message
    document.querySelectorAll('.message.selected').forEach(el => el.classList.remove('selected'));
    if (msg && msg.id) {
        const el = document.querySelector(`.message[data-msg-id="${msg.id}"]`);
        if (el) el.classList.add('selected');
    }

    // Reply and Edit both have their own composer bar in each pane now.
    const replyBtn = document.getElementById('ctx-reply-btn');
    if (replyBtn) replyBtn.style.display = '';

    // Show Edit only for own text messages
    const editBtn = document.getElementById('ctx-edit-btn');
    if (editBtn) {
        const canEdit = msg && msg.from === state.username && !msg.voice && !msg.file && !msg.videoMsg && !msg.deleted;
        editBtn.style.display = canEdit ? '' : 'none';
    }
    // Pin/Unpin label
    const pinBtn = document.getElementById('ctx-pin-btn');
    if (pinBtn) {
        const chat = pane.currentChat && state.chats[pane.currentChat.id];
        const isPinned = chat && chat.pinnedId === (msg && msg.id);
        pinBtn.innerHTML = isPinned
            ? `<span>📌</span> ${t('unpin') || 'Открепить'}`
            : `<span>📌</span> ${t('pin') || 'Закрепить'}`;
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

// ── Reply / Edit composer ───────────────────────────────────────────
// replyingTo/editingMsg both live on each pane so pane A and pane B can
// each have their own reply/edit-in-progress independently.

function bodyOf(msg) {
    let b = msg.text || (msg.voice ? '🎤 ' + t('label_voice') : '') || (msg.videoMsg ? '🎥 ' + t('label_video') : '') || (msg.file ? '📎 ' + msg.file : '');
    if (b.startsWith('> ')) { const nl = b.indexOf('\n'); if (nl > 0) b = b.slice(nl + 1); }
    return b;
}

function ensureComposerBar(pane) {
    const barId = pane === paneA ? 'composer-bar' : 'composer-bar-b';
    let bar = document.getElementById(barId);
    if (bar) return bar;
    bar = document.createElement('div');
    bar.id = barId;
    bar.className = 'composer-bar';
    pane.$inputArea?.parentNode.insertBefore(bar, pane.$inputArea);
    return bar;
}
function hideComposerBar(pane = paneA) {
    pane.replyingTo = null;
    pane.editingMsg = null;
    document.getElementById(pane === paneA ? 'composer-bar' : 'composer-bar-b')?.remove();
}
// Bridges the composer's inline onclick="" (a plain string, can't carry a
// pane object reference) back to the right pane via its suffix.
function hideComposerBarPane(suffix) {
    hideComposerBar(suffix === 'b' ? paneB : paneA);
}
function showComposerBar(mode, msg, pane = paneA) {
    const bar = ensureComposerBar(pane);
    const icon = mode === 'edit' ? '✏️' : '↩';
    const title = mode === 'edit' ? (t('editing') || 'Редактирование') : msg.from;
    bar.innerHTML = `
        <div class="composer-accent"></div>
        <span class="composer-icon">${icon}</span>
        <div class="composer-info">
            <div class="composer-title">${esc(title)}</div>
            <div class="composer-text">${esc(bodyOf(msg).slice(0, 80))}</div>
        </div>
        <button class="composer-close" onclick="hideComposerBarPane('${pane.suffix}')">✕</button>
    `;
}

// Swipe-to-reply / context reply: open reply composer
function startReply(msg, pane = paneA) {
    if (!msg) return;
    pane.editingMsg = null;
    pane.replyingTo = { id: msg.id, from: msg.from, text: bodyOf(msg) };
    showComposerBar('reply', msg, pane);
    pane.$msgInput?.focus();
    const el = pane.$messages.querySelector(`.message[data-msg-id="${msg.id || ''}"]`);
    if (el) { el.classList.add('reply-flash'); setTimeout(() => el.classList.remove('reply-flash'), 700); }
}

function startEdit(msg, pane = paneA) {
    if (!msg || msg.from !== state.username) return;
    pane.replyingTo = null;
    pane.editingMsg = msg;
    showComposerBar('edit', msg, pane);
    if (pane.$msgInput) {
        pane.$msgInput.value = bodyOf(msg);
        pane.$msgInput.focus();
        pane.$msgInput.setSelectionRange(pane.$msgInput.value.length, pane.$msgInput.value.length);
    }
}

// Scroll to the quoted original message (best-effort match by sender + text).
// qText is now passed directly as a real JS value from the click listener in
// renderMessages(), rather than round-tripped through a DOM attribute — see
// the comment there for why that round-trip used to be exploitable.
function scrollToQuoted(qName, qText) {
    const chat = state.currentChat && state.chats[state.currentChat.id];
    if (!chat) return;
    // Find the most recent matching message
    let target = null;
    for (let i = chat.messages.length - 1; i >= 0; i--) {
        const m = chat.messages[i];
        if (m.deleted) continue;
        if (m.from === qName && bodyOf(m).startsWith(qText.slice(0, 40))) { target = m; break; }
    }
    if (!target) return;
    // Virtualized: the target row may not be in the DOM right now if it's
    // scrolled far out of view. Force the window onto it and let
    // renderMessages() do the actual scroll+flash once it's rendered.
    paneA.pendingScrollTarget = { id: target.id, flash: 'reply-flash' };
    renderMessages();
}

// Close on click outside (but ignore the mouseup/click that opened the menu)
document.addEventListener('click', (e) => {
    if ($ctxMenu?.classList.contains('show') && !$ctxMenu.contains(e.target)) {
        if (Date.now() - ctxOpenedAt < 350) return;
        hideContextMenu();
    }
});

document.addEventListener('scroll', hideContextMenu, true);

// ── Reactions ──────────────────────────────────────────────────────

function renderReactions(msg, pane) {
    if (!msg.reactions || Object.keys(msg.reactions).length === 0) return '';
    let html = '<div class="msg-reactions">';
    for (const [emoji, users] of Object.entries(msg.reactions)) {
        if (!users || users.length === 0) continue;
        const isMine = users.includes(state.username);
        html += `<span class="reaction${isMine ? ' mine' : ''}" onclick="toggleReactionClick('${msg.id}','${emoji}',event,'${pane.suffix}')" title="${users.join(', ')}">${emoji}<span class="r-count">${users.length > 1 ? users.length : ''}</span></span>`;
    }
    html += '</div>';
    return html;
}

// One-shot emoji that flies up from (x,y) and fades — feedback for adding
// (not removing) a reaction. Self-removing via animationend so a burst spam
// can't leak nodes.
function spawnReactionBurst(emoji, x, y) {
    if (typeof x !== 'number' || typeof y !== 'number') return;
    const el = document.createElement('span');
    el.className = 'reaction-burst';
    el.textContent = emoji;
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    el.addEventListener('animationend', () => el.remove());
    document.body.appendChild(el);
}

function addReaction(emoji, ev) {
    if (!ctxTargetMsg || !ctxTargetPane || !ctxTargetPane.currentChat) { hideContextMenu(); return; }

    const chat = state.chats[ctxTargetPane.currentChat.id];
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
        if (ev) spawnReactionBurst(emoji, ev.clientX, ev.clientY);
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
        btn.onclick = (e) => addReaction(em, e);
        panel.appendChild(btn);
    }
    panel.classList.add('show');
}

// ── Emoji picker for the input ──────────────────────────────────────
const EMOJI_CATEGORIES = {
    '😀': ['😀','😃','😄','😁','😆','😅','🤣','😂','🙂','🙃','😉','😊','😇','🥰','😍','🤩','😘','😗','😚','😙','😋','😛','😜','🤪','😝','🤑','🤗','🤭','🤫','🤔','🤐','😐','😑','😶','😏','😒','🙄','😬','😌','😔','😪','🤤','😴','😷','🤒','🤕','🤢','🤮','🥵','🥶','🥴','😵','🤯','🤠','🥳','😎','🤓','🧐','😕','😟','🙁','😮','😯','😲','😳','🥺','😦','😧','😨','😰','😥','😢','😭','😱','😖','😣','😞','😓','😩','😫','🥱','😤','😡','😠','🤬','😈','👿','💀','💩','🤡','👻','👽','🤖'],
    '👍': ['👍','👎','👌','🤌','🤏','✌️','🤞','🤟','🤘','🤙','👈','👉','👆','👇','☝️','👋','🤚','🖐️','✋','🖖','👏','🙌','🤲','🙏','🤝','💪','🦾','✍️','💅','👀','👁️','👅','👄','🫀','🫁','🧠','🦷'],
    '❤️': ['❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💔','❣️','💕','💞','💓','💗','💖','💘','💝','💟','♥️','💯','💥','💫','💦','💨','🔥','⭐','🌟','✨','⚡','🎉','🎊'],
    '🐶': ['🐶','🐱','🐭','🐹','🐰','🦊','🐻','🐼','🐨','🐯','🦁','🐮','🐷','🐸','🐵','🐔','🐧','🐦','🐤','🦆','🦅','🦉','🐺','🐗','🐴','🦄','🐝','🐛','🦋','🐌','🐞','🐢','🐍','🐙','🦑','🦀','🐠','🐟','🐬','🐳','🦈'],
    '🍎': ['🍎','🍐','🍊','🍋','🍌','🍉','🍇','🍓','🫐','🍈','🍒','🍑','🥭','🍍','🥥','🥝','🍅','🍆','🥑','🥦','🌽','🥕','🍔','🍟','🍕','🌭','🥪','🌮','🌯','🍜','🍲','🍣','🍱','🍰','🎂','🍦','🍩','🍪','☕','🍺','🍷','🥂'],
    '⚽': ['⚽','🏀','🏈','⚾','🎾','🏐','🏉','🎱','🏓','🏸','🥅','⛳','🎯','🎮','🎲','🎸','🎹','🥁','🎺','🎬','🎤','🚗','✈️','🚀','🏆','🥇','🎁','🎈','🎄','🔒','💡','📱','💻','⌚','📷','🔋','💰','💎'],
};
let emojiInsertPos = null;
function pickerIdFor(pane) { return pane === paneA ? 'input-emoji-picker' : 'input-emoji-picker-b'; }
function toggleInputEmoji(ev, pane = paneA) {
    ev?.stopPropagation();
    const picker = document.getElementById(pickerIdFor(pane));
    if (!picker) return;
    if (picker.style.display !== 'none') { picker.style.display = 'none'; return; }
    buildEmojiPicker(picker, pane);
    picker.style.display = '';
}
function buildEmojiPicker(picker, pane = paneA) {
    const cats = Object.keys(EMOJI_CATEGORIES);
    picker.innerHTML = `
        <div class="emoji-tabs">${cats.map((c, i) => `<button class="emoji-tab${i===0?' active':''}" data-cat="${c}">${c}</button>`).join('')}</div>
        <div class="emoji-grid" id="emoji-grid"></div>
    `;
    const grid = picker.querySelector('#emoji-grid');
    const fill = (cat) => { grid.innerHTML = EMOJI_CATEGORIES[cat].map(e => `<button class="emoji-cell">${e}</button>`).join(''); };
    fill(cats[0]);
    picker.querySelectorAll('.emoji-tab').forEach(tab => {
        tab.onclick = () => {
            picker.querySelectorAll('.emoji-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            fill(tab.dataset.cat);
        };
    });
    grid.onclick = (e) => {
        const cell = e.target.closest('.emoji-cell');
        if (cell) insertEmoji(cell.textContent, pane);
    };
}
function insertEmoji(emoji, pane = paneA) {
    const inp = pane.$msgInput;
    if (!inp) return;
    const start = inp.selectionStart ?? inp.value.length;
    const end = inp.selectionEnd ?? inp.value.length;
    inp.value = inp.value.slice(0, start) + emoji + inp.value.slice(end);
    const pos = start + emoji.length;
    inp.focus();
    inp.setSelectionRange(pos, pos);
    inp.dispatchEvent(new Event('input', { bubbles: true }));
}
// Close emoji picker(s) when clicking elsewhere
document.addEventListener('click', (e) => {
    for (const pane of [paneA, paneB]) {
        if (!pane) continue;
        const picker = document.getElementById(pickerIdFor(pane));
        const btnId = pane === paneA ? 'emoji-btn' : 'emoji-btn-b';
        if (!picker || picker.style.display === 'none') continue;
        if (e.target.closest(`#${pickerIdFor(pane)}`) || e.target.closest(`#${btnId}`)) continue;
        picker.style.display = 'none';
    }
});

function toggleReactionClick(msgId, emoji, ev, paneSuffix) {
    const pane = paneSuffix === 'b' ? paneB : paneA;
    if (!pane || !pane.currentChat) return;
    const chat = state.chats[pane.currentChat.id];
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
        if (ev) spawnReactionBurst(emoji, ev.clientX, ev.clientY);
    }

    saveState();
    renderMessages();
}

// ── Context actions ────────────────────────────────────────────────

function ctxReply() {
    if (!ctxTargetMsg) { hideContextMenu(); return; }
    startReply(ctxTargetMsg, ctxTargetPane || paneA);
    hideContextMenu();
}

function ctxEdit() {
    if (!ctxTargetMsg) { hideContextMenu(); return; }
    if (ctxTargetMsg.from !== state.username) { toast(t('edit_own_only') || 'Можно менять только свои сообщения', 'info'); hideContextMenu(); return; }
    if (ctxTargetMsg.voice || ctxTargetMsg.file || ctxTargetMsg.videoMsg) { toast(t('edit_text_only') || 'Можно менять только текстовые сообщения', 'info'); hideContextMenu(); return; }
    startEdit(ctxTargetMsg, ctxTargetPane || paneA);
    hideContextMenu();
}

function ctxForward() {
    if (!ctxTargetMsg || !ctxTargetPane || !ctxTargetPane.currentChat) { hideContextMenu(); return; }
    const msg = ctxTargetMsg;
    const sourceChatId = ctxTargetPane.currentChat.id;
    hideContextMenu();
    // Build a chat picker
    const chats = Object.values(state.chats)
        .filter(c => c.id !== sourceChatId)
        .sort((a, b) => (b.lastTs || 0) - (a.lastTs || 0));
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    overlay.innerHTML = `
        <div class="modal">
            <h3>${t('forward_to') || 'Переслать в…'}</h3>
            <div class="forward-list">
                ${chats.length ? chats.map(c => `
                    <div class="forward-item" data-id="${esc(c.id)}">
                        ${avatarHtml(c.name, c.type === 'group', 'sm')}
                        <span>${esc(c.name)}</span>
                    </div>`).join('') : `<p style="color:var(--text-muted);text-align:center">${t('no_other_chats') || 'Нет других чатов'}</p>`}
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">${t('cancel')}</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelectorAll('.forward-item').forEach(item => {
        item.onclick = () => { forwardMessageTo(item.dataset.id, msg); overlay.remove(); };
    });
}

async function forwardMessageTo(chatId, msg) {
    const chat = state.chats[chatId];
    if (!chat) return;
    const origin = msg.from;
    const bodyText = bodyOf(msg);
    const text = `↪ ${t('forwarded_from') || 'Переслано от'} ${origin}\n${bodyText}`;
    const ts = Date.now();
    addMessage(chatId, { from: state.username, text, ts, forwarded: true });
    const url = chat.type === 'group' ? '/api/groups/send' : '/api/send';
    const body = chat.type === 'group' ? { group: chatId, text } : { to: chatId, text };
    try {
        const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json());
        if (!res.ok) { toast(res.error || t('send_error'), 'error'); return; }
        toast((t('forwarded_to') || 'Переслано в') + ' ' + chat.name, 'success');
        renderChatList();
        if (state.currentChat?.id === chatId || (paneB && paneB.currentChat?.id === chatId)) renderMessages();
    } catch (e) { toast(t('server_unavailable'), 'error'); }
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
    if (!ctxTargetMsg || !ctxTargetPane || !ctxTargetPane.currentChat) { hideContextMenu(); return; }
    const chat = state.chats[ctxTargetPane.currentChat.id];
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
                        body: JSON.stringify({ to: ctxTargetPane.currentChat.id, text: `__DELETE__:${ctxTargetMsg.id}` }),
                    });
                } catch (e) {}
            }
            toast(t('msg_deleted_all'), 'success');
        };
    }

    hideContextMenu();
}

function ctxPin() {
    if (!ctxTargetMsg || !ctxTargetPane || !ctxTargetPane.currentChat) { hideContextMenu(); return; }
    const chat = state.chats[ctxTargetPane.currentChat.id];
    if (!chat) { hideContextMenu(); return; }
    if (chat.pinnedId === ctxTargetMsg.id) {
        chat.pinnedId = null;
        toast(t('unpinned') || 'Откреплено', 'success');
    } else {
        chat.pinnedId = ctxTargetMsg.id;
        toast(t('pinned') || 'Закреплено', 'success');
    }
    saveState();
    renderMessages();
    renderPinnedBar();
    hideContextMenu();
}

// ── Pinned message bar ──────────────────────────────────────────────
function renderPinnedBar() {
    const bar = document.getElementById('pinned-bar');
    if (!bar) return;
    const chat = state.currentChat && state.chats[state.currentChat.id];
    const msg = chat && chat.pinnedId && chat.messages.find(m => m.id === chat.pinnedId && !m.deleted);
    if (!msg) { bar.style.display = 'none'; return; }
    bar.style.display = '';
    bar.innerHTML = `
        <span class="pinned-icon">📌</span>
        <div class="pinned-info">
            <div class="pinned-title">${t('pinned_message') || 'Закреплённое сообщение'}</div>
            <div class="pinned-text">${esc(msg.from)}: ${esc(bodyOf(msg).slice(0, 80))}</div>
        </div>
        <button class="pinned-unpin" onclick="event.stopPropagation();unpinCurrent()" title="Открепить">✕</button>
    `;
}
function unpinCurrent() {
    const chat = state.currentChat && state.chats[state.currentChat.id];
    if (!chat) return;
    chat.pinnedId = null;
    saveState();
    renderMessages();
    renderPinnedBar();
    toast(t('unpinned') || 'Откреплено', 'success');
}
function scrollToPinned() {
    const chat = state.currentChat && state.chats[state.currentChat.id];
    if (!chat || !chat.pinnedId) return;
    paneA.pendingScrollTarget = { id: chat.pinnedId, flash: 'reply-flash' };
    renderMessages();
}

// ── In-chat message search ──────────────────────────────────────────
// Search state lives on each pane (pane.searchMatches/searchIdx) so pane A
// and pane B can each search their own (independent) open chat.
function barId(pane) { return pane === paneA ? 'chat-search-bar' : 'chat-search-bar-b'; }
function inputId(pane) { return pane === paneA ? 'chat-search-input' : 'chat-search-input-b'; }
function countId(pane) { return pane === paneA ? 'chat-search-count' : 'chat-search-count-b'; }

function openChatSearch(pane = paneA) {
    const bar = document.getElementById(barId(pane));
    if (!bar) return;
    bar.style.display = 'flex';
    const inp = document.getElementById(inputId(pane));
    inp.value = '';
    inp.focus();
    pane.searchMatches = [];
    pane.searchIdx = -1;
    updateChatSearchCount(pane);
}
function closeChatSearch(pane = paneA) {
    const bar = document.getElementById(barId(pane));
    if (bar) bar.style.display = 'none';
    pane.searchMatches = [];
    pane.searchIdx = -1;
    renderMessagesForPane(pane);
}
function runChatSearch(pane = paneA) {
    const q = (document.getElementById(inputId(pane))?.value || '').trim().toLowerCase();
    const chat = pane.currentChat && state.chats[pane.currentChat.id];
    pane.searchMatches = [];
    pane.searchIdx = -1;
    if (q && chat) {
        for (const m of chat.messages) {
            if (m.deleted) continue;
            if (bodyOf(m).toLowerCase().includes(q)) pane.searchMatches.push(m.id);
        }
    }
    // search-hit/search-current are applied data-driven inside
    // buildMessageNode() off pane.searchMatches/searchIdx, so any render
    // (including the jump focusSearchMatch() below triggers) picks up
    // whatever's current here - no separate DOM-highlighting pass needed,
    // which also means it stays correct for matches outside the virtualized
    // window instead of silently skipping them.
    if (pane.searchMatches.length) { pane.searchIdx = 0; focusSearchMatch(pane); }
    else renderMessagesForPane(pane);
    updateChatSearchCount(pane);
}
function chatSearchStep(dir, pane = paneA) {
    if (!pane.searchMatches.length) return;
    pane.searchIdx = (pane.searchIdx + dir + pane.searchMatches.length) % pane.searchMatches.length;
    focusSearchMatch(pane);
    updateChatSearchCount(pane);
}
function focusSearchMatch(pane = paneA) {
    const id = pane.searchMatches[pane.searchIdx];
    if (id == null) return;
    pane.pendingScrollTarget = { id };
    renderMessagesForPane(pane);
}
function updateChatSearchCount(pane = paneA) {
    const el = document.getElementById(countId(pane));
    if (!el) return;
    el.textContent = pane.searchMatches.length ? `${pane.searchIdx + 1}/${pane.searchMatches.length}` : '0/0';
}

// ── Scroll-to-bottom button ─────────────────────────────────────────
let scrollUnread = 0;
function scrollMessagesToBottom(smooth, pane) {
    pane = pane || paneA;
    if (pane === paneA) { scrollUnread = 0; updateScrollUnread(); }
    if (!pane.$messages) return;
    pane.$messages.scrollTo({ top: pane.$messages.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
}
function isNearBottomIn(pane) {
    if (!pane.$messages) return true;
    return pane.$messages.scrollHeight - pane.$messages.scrollTop - pane.$messages.clientHeight < 120;
}
function isNearBottom() { return isNearBottomIn(paneA); }
function updateScrollBtn(pane) {
    pane = pane || paneA;
    if (!pane.$scrollBtn) return;
    pane.$scrollBtn.style.display = isNearBottomIn(pane) ? 'none' : 'flex';
}
function updateScrollUnread() {
    const el = document.getElementById('scroll-unread');
    if (!el) return;
    if (scrollUnread > 0) { el.textContent = scrollUnread; el.style.display = ''; }
    else el.style.display = 'none';
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
        if (state.currentChat?.id === chatId) renderMessagesForPane(paneA);
        if (paneB?.currentChat?.id === chatId) renderMessagesForPane(paneB);
        renderChatList();
    }
    return true;
}

// Handle incoming edit commands: __EDIT__:<id>:<newtext>
function handleEditCommand(chatId, text) {
    if (!text.startsWith('__EDIT__:')) return false;
    const rest = text.slice('__EDIT__:'.length);
    const sep = rest.indexOf(':');
    if (sep < 0) return true;
    const msgId = rest.slice(0, sep);
    const newText = rest.slice(sep + 1);
    const chat = state.chats[chatId];
    if (!chat) return true;
    const msg = chat.messages.find(m => m.id === msgId);
    if (msg) {
        msg.text = newText;
        msg.edited = true;
        saveState();
        if (state.currentChat?.id === chatId) renderMessagesForPane(paneA);
        if (paneB?.currentChat?.id === chatId) renderMessagesForPane(paneB);
        renderChatList();
    }
    return true;
}

// ── Drag & Drop ─────────────────────────────────────────────────────
// The listeners are on document (a drag can start over the sidebar, a
// message, anywhere), so which pane a drop belongs to is resolved from
// the drop target itself: over pane B's chat area targets pane B,
// everything else defaults to pane A - same as it always has.
const $dropOverlay = $('#drop-overlay');
const $dropOverlayB = document.getElementById('drop-overlay-b');
let dragCounter = 0;

function paneForDropTarget(target) {
    if (paneB && target?.closest?.('#chat-area-b')) return paneB;
    return paneA;
}
function overlayFor(pane) { return pane === paneA ? $dropOverlay : $dropOverlayB; }

document.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragCounter++;
    const pane = paneForDropTarget(e.target);
    if (pane.currentChat) overlayFor(pane)?.classList.add('active');
});

document.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) {
        dragCounter = 0;
        $dropOverlay?.classList.remove('active');
        $dropOverlayB?.classList.remove('active');
    }
});

// Fires continuously while dragging - used to swap which pane's overlay
// is showing if the drag moves from over one pane's area to the other's.
document.addEventListener('dragover', (e) => {
    e.preventDefault();
    const pane = paneForDropTarget(e.target);
    const active = overlayFor(pane);
    const inactive = pane === paneA ? $dropOverlayB : $dropOverlay;
    inactive?.classList.remove('active');
    if (pane.currentChat) active?.classList.add('active');
});

document.addEventListener('drop', async (e) => {
    e.preventDefault();
    dragCounter = 0;
    $dropOverlay?.classList.remove('active');
    $dropOverlayB?.classList.remove('active');
    const pane = paneForDropTarget(e.target);
    if (!pane.currentChat || !e.dataTransfer.files.length) return;

    const file = e.dataTransfer.files[0];
    const ts = Date.now();
    addMessage(pane.currentChat.id, { from: state.username, file: file.name, size: file.size, ts });
    pane.forceBottom = true;
    renderMessagesForPane(pane);
    renderChatList();

    const fd = new FormData();
    fd.append('to', pane.currentChat.id);
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
            $da.innerHTML = `<img src="${esc(photo)}" class="avatar-img" alt="">`;
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

// ── Session guard ───────────────────────────────────────────────────
// Протухшую сессию сервер отдаёт как 200 с {ok:false, error:'Not authorized'}.
// Без единой точки перехвата интерфейс продолжал выглядеть залогиненным, а
// действия молча не срабатывали — так и потерялась подписка на push.
let sessionExpiredHandled = false;

function onSessionExpired() {
    if (sessionExpiredHandled) return;
    sessionExpiredHandled = true;
    toast(t('session_expired'), 'error');
    setTimeout(() => { window.location.href = '/'; }, 1800);
}

function installSessionGuard() {
    const origFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
        const res = await origFetch(input, init);
        if (sessionExpiredHandled) return res;
        try {
            const url = typeof input === 'string' ? input : (input && input.url) || '';
            const ct = res.headers.get('content-type') || '';
            if (url.includes('/api/') && !url.includes('/api/login') && ct.includes('json')) {
                const peek = await res.clone().json();
                if (peek && peek.ok === false && peek.error === 'Not authorized') onSessionExpired();
            }
        } catch (e) { /* не JSON или тело уже прочитано — не наше дело */ }
        return res;
    };
}
installSessionGuard();

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
            // Use the canonical id from the server (it lowercases group names) so
            // the local chat key matches what /api/groups will report on reload.
            const gid = res.group || name.toLowerCase();
            ensureChat(gid, 'group', gid);
            saveState();
            renderChatList();
            selectChat(gid);
            toast(t('group_created', gid), 'success');
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

// Кик/leave (фаза 4, docs/ratchet-plan.md) — любой участник может выкинуть
// любого другого (та же ungated-модель доверия, что у инвайта); при выходе
// или киках группа сама себя ре-кеит на сервере/у клиентов, здесь только UI.
async function showGroupMembers() {
    if (!state.currentChat || state.currentChat.type !== 'group') return;
    const gid = state.currentChat.id;
    let data;
    try {
        data = await fetch(`/api/groups/members?group=${encodeURIComponent(gid)}`).then(r => r.json());
    } catch (e) {
        toast('Не удалось получить список участников', 'error');
        return;
    }
    if (!data.ok) {
        toast(data.error || 'Не удалось получить список участников', 'error');
        return;
    }
    const members = data.members || [];
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <h3>Участники группы</h3>
            <div class="member-list" style="text-align:left;margin:12px 0;max-height:300px;overflow-y:auto">
                ${members.map(u => `
                    <div class="member-row" style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
                        <span>${esc(u)}${u === state.username ? ' (вы)' : ''}</span>
                        ${u !== state.username ? `<button class="btn btn-secondary" data-kick="${esc(u)}" style="padding:4px 10px;font-size:12px">Исключить</button>` : ''}
                    </div>
                `).join('')}
            </div>
            <div class="modal-actions" style="flex-direction:column;gap:8px">
                <button class="btn btn-secondary" id="leave-group-btn">Покинуть группу</button>
                <button class="btn" onclick="this.closest('.modal-overlay').remove()">Закрыть</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelectorAll('[data-kick]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const target = btn.dataset.kick;
            btn.disabled = true;
            try {
                const res = await fetch('/api/groups/kick', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ group: gid, user: target }),
                }).then(r => r.json());
                if (res.ok) {
                    toast(`${target} исключён(а)`, 'success');
                    btn.closest('.member-row').remove();
                } else {
                    toast(res.error || 'Не удалось исключить', 'error');
                    btn.disabled = false;
                }
            } catch (e) {
                toast('Не удалось исключить', 'error');
                btn.disabled = false;
            }
        });
    });
    overlay.querySelector('#leave-group-btn')?.addEventListener('click', async () => {
        if (!confirm('Покинуть эту группу?')) return;
        try {
            const res = await fetch('/api/groups/leave', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ group: gid }),
            }).then(r => r.json());
            if (res.ok) {
                overlay.remove();
                delete state.chats[gid];
                saveState();
                goBack();
                toast('Вы покинули группу', 'success');
            } else {
                toast(res.error || 'Не удалось покинуть группу', 'error');
            }
        } catch (e) {
            toast('Не удалось покинуть группу', 'error');
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
    if (msg.text && handleEditCommand(chatId, msg.text)) return;

    const chat = ensureChat(chatId, chatType, chatName);
    const ts = Date.now();
    addMessage(chatId, { from: msg.from, text: msg.text, ts, auth: msg.auth });

    const isCurrent = state.currentChat && state.currentChat.id === chatId;
    const isCurrentB = paneB && paneB.currentChat && paneB.currentChat.id === chatId;
    if (!isCurrent && !isCurrentB) {
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
    if (isCurrent) {
        const wasNear = isNearBottom();
        renderMessages(); // covers pane B too if it happens to show this same chat
        if (!wasNear && msg.from !== state.username) { scrollUnread++; updateScrollUnread(); updateScrollBtn(); }
    } else if (isCurrentB) {
        renderMessagesForPane(paneB);
    }
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

    const isCurrentB = paneB && paneB.currentChat && paneB.currentChat.id === info.from;
    if ((!state.currentChat || state.currentChat.id !== info.from) && !isCurrentB) {
        chat.unread = (chat.unread || 0) + 1;
        saveState();
    }

    renderChatList();
    if (state.currentChat?.id === info.from) renderMessages();
    else if (isCurrentB) renderMessagesForPane(paneB);

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
// typingSentAt/typingStopTimer live on each pane (like replyingTo/search)
// so pane A and pane B each throttle+emit typing for their own open chat.
function emitTyping(isTyping, pane = paneA) {
    if (!pane.currentChat) return;
    socket.emit('typing', {
        to: pane.currentChat.id,
        group: pane.currentChat.type === 'group',
        typing: !!isTyping,
    });
}

function handleTypingInput(pane) {
    // Throttle typing event to once every 3s while user is typing
    const now = Date.now();
    if (pane.$msgInput.value.trim()) {
        if (now - pane.typingSentAt > 3000) {
            emitTyping(true, pane);
            pane.typingSentAt = now;
        }
        clearTimeout(pane.typingStopTimer);
        pane.typingStopTimer = setTimeout(() => {
            emitTyping(false, pane);
            pane.typingSentAt = 0;
        }, 3500);
    } else if (pane.typingSentAt) {
        clearTimeout(pane.typingStopTimer);
        emitTyping(false, pane);
        pane.typingSentAt = 0;
    }
}

$msgInput?.addEventListener('input', () => {
    $msgInput.style.height = 'auto';
    $msgInput.style.height = Math.min($msgInput.scrollHeight, 120) + 'px';
    handleTypingInput(paneA);
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

// A typing event names a chat, not a pane - if that chat happens to be open
// in both panes at once, both headers should reflect it.
function updateTypingUI(chatId) {
    updateTypingUIForPane(paneA, chatId);
    if (paneB) updateTypingUIForPane(paneB, chatId);
}
function updateTypingUIForPane(pane, chatId) {
    if (!pane.currentChat || pane.currentChat.id !== chatId) return;
    const st = typingState[chatId];
    const subtitle = pane.$chatHeader.querySelector('.subtitle-text');
    const typingEl = pane.$chatHeader.querySelector('.typing-text');
    if (!typingEl) return;
    const users = st ? Array.from(st.users) : [];
    if (users.length === 0) {
        typingEl.style.display = 'none';
        if (subtitle) subtitle.style.display = '';
        return;
    }
    let txt;
    const chat = state.chats[chatId];
    if (chat && chat.type === 'group') {
        txt = users.length === 1
            ? `${users[0]} ${t('typing_one') || 'печатает...'}`
            : `${users.join(', ')} ${t('typing_many') || 'печатают...'}`;
    } else {
        txt = t('typing_one') || 'печатает...';
    }
    typingEl.textContent = txt;
    typingEl.style.display = '';
    if (subtitle) subtitle.style.display = 'none';
}

$searchInput?.addEventListener('input', () => renderChatList());

// In-chat search input + navigation
document.getElementById('chat-search-input')?.addEventListener('input', runChatSearch);
document.getElementById('chat-search-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); chatSearchStep(e.shiftKey ? -1 : 1); }
    if (e.key === 'Escape') closeChatSearch();
});

// Scroll-to-bottom button visibility
$messages?.addEventListener('scroll', () => {
    updateScrollBtn();
    if (isNearBottom()) { scrollUnread = 0; updateScrollUnread(); }
});

// ── Utilities ───────────────────────────────────────────────────────
function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    // textContent -> innerHTML escapes &<> but NOT quotes (they're inert inside
    // a text node, so the browser has no reason to encode them there). Every
    // caller of esc() interpolates into a "-quoted HTML attribute, so an
    // unescaped " lets the payload close the attribute early and add new ones
    // (e.g. onerror=...) — this is exactly how the profile-photo XSS worked.
    return d.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Turn plain URLs in already-escaped text into clickable links + collect them.
const URL_RE = /(https?:\/\/[^\s<]+[^\s<.,!?;:'")\]])/gi;
function linkify(escapedText) {
    return escapedText.replace(URL_RE, (m) => {
        // m is already HTML-escaped (came from esc()); safe to embed
        return `<a href="${m}" class="msg-link" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${m}</a>`;
    });
}
// Extract the first URL from a raw (unescaped) string
function firstUrl(text) {
    if (!text) return null;
    const m = text.match(/https?:\/\/[^\s<]+[^\s<.,!?;:'")\]]/i);
    return m ? m[0] : null;
}
// Build a compact link-preview card (no external fetch — safe under CSP/DNS tunnel).
// The icon is generated locally (host initial on a color derived from the host),
// so nothing is requested off-device — no domain leak, works during a shutdown.
function linkPreviewHtml(url) {
    if (!url) return '';
    let host = '', path = '';
    try { const u = new URL(url); host = u.hostname.replace(/^www\./, ''); path = (u.pathname + u.search).slice(0, 60); }
    catch (e) { return ''; }
    const iconColors = avatarColor(host);
    const iconLetter = host ? host[0].toUpperCase() : '#';
    return `
        <a class="link-preview" href="${esc(url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">
            <div class="link-preview-icon" style="display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600;color:#fff;background:linear-gradient(135deg,${iconColors[0]},${iconColors[1]})">${esc(iconLetter)}</div>
            <div class="link-preview-body">
                <div class="link-preview-host">${esc(host)}</div>
                <div class="link-preview-path">${esc(path || url)}</div>
            </div>
        </a>`;
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
        // Update header if still viewing this chat. Patches the dot/text in
        // place (scoped to pane A's own header) rather than replacing
        // .chat-subtitle's innerHTML wholesale, which used to silently wipe
        // out the .typing-text span living alongside it.
        if (state.currentChat?.id === username) {
            const sub = $chatHeader.querySelector('.chat-subtitle');
            if (sub) {
                const dot = sub.querySelector('.online-dot');
                const subtitleText = sub.querySelector('.subtitle-text');
                if (dot) dot.style.background = res.online ? 'var(--green)' : 'var(--text-muted)';
                if (subtitleText) subtitleText.textContent = formatLastSeen(res);
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
                    // Меняем фото прямо из открытого drawer — сам он
                    // перерисовывается только в openDrawer(), а drawer в этот
                    // момент уже открыт и повторно не откроется, так что без
                    // явного обновления аватарка тут молча оставалась старой.
                    const $da = $('#drawer-avatar');
                    if ($da) $da.innerHTML = `<img src="${esc(resized)}" class="avatar-img" alt="">`;
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
// ── PWA: service worker + install prompt ────────────────────────────
function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js')
        .then(() => { if (isPushEnabled()) syncPushSubscription(); })
        .catch((e) => console.warn('SW register failed', e));
}

// ─── Web Push (VAPID) ───────────────────────────────────────────────────
// Уведомления от сервера, доходящие при полностью закрытой вкладке.
// Отличие от showDesktopNotification: там страница жива и рисует сама.

const PUSH_FLAG_KEY = () => `dns_push_${state.username || 'anon'}`;

function isPushSupported() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}
function isPushEnabled() {
    return localStorage.getItem(PUSH_FLAG_KEY()) === '1';
}

async function syncPushSubscription() {
    // Подписка живёт в браузере, а сервер мог потерять её (перезапуск,
    // очистка файла) — поэтому отправляем на сервер при каждом старте.
    // Бросаем, а не возвращаем null: молчаливый выход раньше выдавался
    // вызывающему за успех, и флаг включался без единого запроса к серверу.
    if (!isPushSupported()) throw new Error(t('push_unsupported'));

    // navigator.serviceWorker.ready никогда не отвергается: если регистрация
    // не удалась (например, самоподписанный сертификат), он висит вечно.
    const reg = await Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, rej) => setTimeout(() => rej(new Error(t('push_no_sw'))), 8000)),
    ]);

    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
        const keyRes = await fetch('/api/push/key').then((r) => r.json());
        if (!keyRes.ok) throw new Error('no vapid key');
        sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: keyRes.key,
        });
    }
    const res = await fetch('/api/push/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription: sub.toJSON() }),
    }).then((r) => r.json());
    // Сервер отвечает 200 и на отказ — проверяем тело, иначе «подписались»
    // при истёкшей сессии выглядело бы успехом.
    if (!res.ok) throw new Error(res.error || 'subscribe rejected');
    return sub;
}

async function hasLivePushSubscription() {
    if (!isPushSupported() || Notification.permission !== 'granted') return false;
    try {
        const reg = await navigator.serviceWorker.getRegistration();
        return !!(reg && await reg.pushManager.getSubscription());
    } catch (e) {
        return false;
    }
}

async function enablePush() {
    if (!isPushSupported()) {
        toast(t('push_unsupported'), 'error');
        return false;
    }
    // Если разрешение уже отклонено, requestPermission молча вернёт 'denied'
    // без диалога — подсказываем, что чинить это надо в настройках сайта.
    const wasDenied = Notification.permission === 'denied';
    const perm = await Notification.requestPermission();
    if (perm !== 'granted') {
        toast(wasDenied ? t('push_blocked') : t('push_denied'), 'error');
        return false;
    }
    try {
        await syncPushSubscription();
        localStorage.setItem(PUSH_FLAG_KEY(), '1');
        toast(t('push_enabled'), 'success');
        return true;
    } catch (e) {
        console.warn('push subscribe failed', e);
        toast(`${t('push_failed')}: ${e.message}`, 'error');
        return false;
    }
}

async function disablePush() {
    localStorage.removeItem(PUSH_FLAG_KEY());
    try {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
            await fetch('/api/push/unsubscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ endpoint: sub.endpoint }),
            });
            await sub.unsubscribe();
        }
    } catch (e) { /* уже отписаны */ }
    toast(t('push_disabled'), 'info');
}

async function sendTestPush() {
    const res = await fetch('/api/push/test', { method: 'POST' }).then((r) => r.json()).catch(() => null);
    if (res && res.ok) { toast(t('push_test_sent'), 'success'); return; }
    // Показываем настоящую причину: раньше любой отказ — включая «нет сессии» —
    // выдавался за «сначала включите push», что уводило от реальной проблемы.
    const reason = res && (res.error || (res.errors && res.errors[0]));
    toast(reason ? `${t('push_test_failed')}: ${reason}` : t('push_test_failed'), 'error');
}

let deferredInstallPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
});
async function promptInstall() {
    if (!deferredInstallPrompt) {
        toast(t('install_unavailable') || 'Установка недоступна (уже установлено или не поддерживается)', 'info');
        return;
    }
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    if (outcome === 'accepted') toast(t('installed') || 'Приложение установлено', 'success');
    deferredInstallPrompt = null;
}

// One-time cleanup: merge mixed-case group chats into their lowercase id
// (fixes duplicates created before group ids were canonicalized server-side).
function dedupeGroupChats() {
    let changed = false;
    for (const id of Object.keys(state.chats)) {
        const chat = state.chats[id];
        if (chat.type !== 'group') continue;
        const lc = id.toLowerCase();
        if (lc === id) continue;
        const target = state.chats[lc];
        if (target) {
            // Merge messages (dedupe by id), keep the newer lastTs
            const seen = new Set(target.messages.map(m => m.id));
            for (const msg of chat.messages) {
                if (!seen.has(msg.id)) { target.messages.push(msg); seen.add(msg.id); }
            }
            target.messages.sort((a, b) => a.ts - b.ts);
            target.lastTs = Math.max(target.lastTs || 0, chat.lastTs || 0);
            target.pinnedId = target.pinnedId || chat.pinnedId || null;
            target.chatPinned = target.chatPinned || chat.chatPinned;
        } else {
            // Rename the chat to its lowercase id
            state.chats[lc] = { ...chat };
        }
        delete state.chats[id];
        changed = true;
    }
    if (changed) saveState();
}

async function init() {
    await unlockStorage();
    await loadState();
    dedupeGroupChats();
    initTabs();
    registerServiceWorker();

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
    celebrateIfFirstLogin();
}

// ── Confetti on first login ──────────────────────────────────────────
// login.html sets this sessionStorage flag right before redirecting here,
// only for a fresh registration or anonymous-mode signup (not a plain
// returning login) - see doLogin() there. canvas-confetti is ~11KB, so it's
// fetched on demand instead of on every page load.
function celebrateIfFirstLogin() {
    if (sessionStorage.getItem('dns_celebrate') !== '1') return;
    sessionStorage.removeItem('dns_celebrate');
    if (document.documentElement.classList.contains('no-anim')) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const script = document.createElement('script');
    script.src = '/static/vendor/confetti.min.js';
    script.onload = () => {
        if (typeof window.confetti !== 'function') return;
        window.confetti({ particleCount: 120, spread: 90, origin: { y: 0.6 } });
    };
    document.body.appendChild(script);
}

init();
