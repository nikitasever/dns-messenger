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
function linkify(escapedText) {
    return escapedText.replace(URL_RE, (m) =>
        `<a href="${m}" class="msg-link" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${m}</a>`);
}
function firstUrl(text) {
    if (!text) return null;
    const m = text.match(/https?:\/\/[^\s<]+[^\s<.,!?;:'")\]]/i);
    return m ? m[0] : null;
}
function bodyOf(msg) {
    let b = msg.text || (msg.voice ? '🎤 Голосовое' : '') || (msg.videoMsg ? '🎥 Видео' : '') || (msg.file ? '📎 ' + msg.file : '');
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

console.log(`\n${passed} passed`);
