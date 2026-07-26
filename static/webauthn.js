/* Общие хелперы для WebAuthn (passkey) — второй фактор входа.
   base64url <-> ArrayBuffer конвертация (Credential Management API оперирует
   ArrayBuffer'ами, а сервер — base64url-строками из py_webauthn), плюс две
   функции верхнего уровня: регистрация нового passkey и подтверждение входа
   уже существующим. Ничего секретное сюда не попадает — приватный ключ
   passkey никогда не покидает устройство/аутентификатор. */

function b64urlToBuf(s) {
    s = s.replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    const bin = atob(s);
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    return buf.buffer;
}

function bufToB64url(buf) {
    const bytes = new Uint8Array(buf);
    let bin = '';
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function webauthnSupported() {
    return !!(window.PublicKeyCredential && navigator.credentials);
}

/* Регистрирует новый passkey для УЖЕ вошедшего пользователя. label — метка
   для UI ("MacBook Touch ID"), выбирает сам пользователь. */
async function registerPasskey(label) {
    if (!webauthnSupported()) throw new Error('Браузер не поддерживает passkeys');
    const optionsRes = await fetch('/api/webauthn/register/options', { method: 'POST' })
        .then(r => r.json());
    if (optionsRes.ok === false) throw new Error(optionsRes.error || 'Ошибка сервера');

    const publicKey = {
        ...optionsRes,
        challenge: b64urlToBuf(optionsRes.challenge),
        user: { ...optionsRes.user, id: b64urlToBuf(optionsRes.user.id) },
        excludeCredentials: (optionsRes.excludeCredentials || []).map(c => ({
            ...c, id: b64urlToBuf(c.id),
        })),
    };
    const cred = await navigator.credentials.create({ publicKey });
    if (!cred) throw new Error('Passkey не создан');

    const credentialJson = {
        id: cred.id,
        rawId: bufToB64url(cred.rawId),
        type: cred.type,
        response: {
            clientDataJSON: bufToB64url(cred.response.clientDataJSON),
            attestationObject: bufToB64url(cred.response.attestationObject),
        },
        clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
    };

    const verifyRes = await fetch('/api/webauthn/register/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: credentialJson, label: label || 'Passkey' }),
    }).then(r => r.json());
    if (!verifyRes.ok) throw new Error(verifyRes.error || 'Проверка не пройдена');
    return verifyRes; // .backup_codes присутствует только на самом первом passkey
}

/* Подтверждает вход уже существующим passkey — вызывается ПОСЛЕ того как
   /api/login ответил need_webauthn: true (пароль уже проверен, но сессия
   ещё не выдана). Бросает исключение на любую ошибку/отмену. */
async function verifyPasskeyLogin() {
    if (!webauthnSupported()) throw new Error('Браузер не поддерживает passkeys');
    const optionsRes = await fetch('/api/webauthn/login/options', { method: 'POST' })
        .then(r => r.json());
    if (optionsRes.ok === false) throw new Error(optionsRes.error || 'Ошибка сервера');

    const publicKey = {
        ...optionsRes,
        challenge: b64urlToBuf(optionsRes.challenge),
        allowCredentials: (optionsRes.allowCredentials || []).map(c => ({
            ...c, id: b64urlToBuf(c.id),
        })),
    };
    const assertion = await navigator.credentials.get({ publicKey });
    if (!assertion) throw new Error('Подтверждение отменено');

    const credentialJson = {
        id: assertion.id,
        rawId: bufToB64url(assertion.rawId),
        type: assertion.type,
        response: {
            clientDataJSON: bufToB64url(assertion.response.clientDataJSON),
            authenticatorData: bufToB64url(assertion.response.authenticatorData),
            signature: bufToB64url(assertion.response.signature),
            userHandle: assertion.response.userHandle ? bufToB64url(assertion.response.userHandle) : null,
        },
        clientExtensionResults: assertion.getClientExtensionResults ? assertion.getClientExtensionResults() : {},
    };

    const verifyRes = await fetch('/api/webauthn/login/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: credentialJson }),
    }).then(r => r.json());
    if (!verifyRes.ok) throw new Error(verifyRes.error || 'Проверка не пройдена');
    return true;
}
