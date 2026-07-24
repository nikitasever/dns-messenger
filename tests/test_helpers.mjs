/* Lightweight unit tests for pure helpers in static/app.js.
   Run with:  node tests/test_helpers.mjs
   No test framework required — exits non-zero on first failure. */

import assert from 'node:assert/strict';

// ── Re-implementations kept in sync with static/app.js ──
// (app.js is browser-coupled; these mirror the pure logic under test.)

const URL_RE = /(https?:\/\/[^\s<]+[^\s<.,!?;:'")\]])/gi;
function escHtml(s) {
    return String(s || '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
// Mirrors static/app.js's real esc(): a browser's textContent->innerHTML
// round-trip auto-escapes &<> but not quotes, so esc() now explicitly encodes
// them too — this is the fix for the profile-photo stored-XSS proven live
// (a crafted `data:image/png,x" onerror="..."` fired in a real browser tab
// before this landed). Kept as a separate mirror because the real esc() needs
// a DOM (document.createElement), unavailable in plain Node.
function escAttr(s) {
    return escHtml(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function linkify(escapedText) {
    return escapedText.replace(URL_RE, (m) =>
        `<a href="${m}" class="msg-link" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${m}</a>`);
}
function firstUrl(text) {
    if (!text) return null;
    const m = text.match(/https?:\/\/[^\s<]+[^\s<.,!?;:'")\]]/i);
    return m ? m[0] : null;
}
const t = (k) => ({ label_voice: 'Голосовое', label_video: 'Видео' })[k];
function bodyOf(msg) {
    let b = msg.text || (msg.voice ? '🎤 ' + t('label_voice') : '') || (msg.videoMsg ? '🎥 ' + t('label_video') : '') || (msg.file ? '📎 ' + msg.file : '');
    if (b.startsWith('> ')) { const nl = b.indexOf('\n'); if (nl > 0) b = b.slice(nl + 1); }
    return b;
}

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('  ✓ ' + name); }

console.log('helpers');

test('firstUrl finds a plain url', () => {
    assert.equal(firstUrl('see https://example.com/x now'), 'https://example.com/x');
});
test('firstUrl returns null when absent', () => {
    assert.equal(firstUrl('no links here'), null);
});
test('firstUrl trims trailing punctuation', () => {
    assert.equal(firstUrl('go to https://a.com/path.'), 'https://a.com/path');
});
test('linkify wraps a url in an anchor', () => {
    const out = linkify(escHtml('visit https://github.com/x'));
    assert.match(out, /<a href="https:\/\/github\.com\/x"/);
    assert.match(out, /class="msg-link"/);
});
test('linkify leaves plain text untouched', () => {
    assert.equal(linkify(escHtml('hello world')), 'hello world');
});
test('escHtml neutralizes tags before linkify (no injection)', () => {
    const out = linkify(escHtml('<script>alert(1)</script> https://x.com'));
    assert.ok(!out.includes('<script>'));
    assert.match(out, /&lt;script&gt;/);
});
test('bodyOf strips a leading reply quote', () => {
    assert.equal(bodyOf({ text: '> alice: hi there\nreal body' }), 'real body');
});
test('bodyOf labels voice/video/file', () => {
    assert.equal(bodyOf({ voice: true }), '🎤 Голосовое');
    assert.equal(bodyOf({ videoMsg: true }), '🎥 Видео');
    assert.equal(bodyOf({ file: 'a.pdf' }), '📎 a.pdf');
});
test('edit command format round-trips', () => {
    const id = 'abc', text = 'new: text with: colons';
    const wire = `__EDIT__:${id}:${text}`;
    const rest = wire.slice('__EDIT__:'.length);
    const sep = rest.indexOf(':');
    assert.equal(rest.slice(0, sep), id);
    assert.equal(rest.slice(sep + 1), text);
});

// Regression test for the profile-photo stored XSS, proven live in a real
// browser tab (document.title became "XSS-PWNED" via an <img onerror>) before
// this fix. esc() is used everywhere a value is interpolated into a "-quoted
// HTML attribute; escHtml() alone left the closing quote unescaped, letting
// the payload break out of src="..." and add a live onerror attribute.
test('esc (as escAttr) neutralizes the exact payload that fired live', () => {
    const payload = 'data:image/png,x" onerror="window.__xss_fired=1;document.title=\'XSS-PWNED\'"';
    const escaped = escAttr(payload);
    // The invariant that actually matters: a double-quoted HTML attribute can
    // only be terminated by a raw, unescaped ". If none survives, the browser
    // has no way to end src="..." early — no other check is needed, since
    // onerror can only become a live attribute by escaping that boundary.
    assert.ok(!escaped.includes('"'), 'no raw double-quote survives — cannot close the attribute');
    assert.ok(!escaped.includes("'"), 'no raw single-quote survives either (single-quoted attrs, JS strings)');
});
test('esc (as escAttr) still round-trips plain text untouched by quoting', () => {
    assert.equal(escAttr('alice'), 'alice');
    assert.equal(escAttr('<b>hi</b>'), '&lt;b&gt;hi&lt;/b&gt;');
});

console.log(`\n${passed} passed`);
