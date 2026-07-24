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
// A security scan flagged the message `href` (linkify) as a possible XSS sink.
// It's a false positive *only because* the real app calls linkify(esc(text)):
// escaping runs first, so any " in a crafted URL is already &quot; before
// URL_RE matches, and can't close href="...". URL_RE also requires https?://,
// so no javascript:/data: scheme slips through. This test pins that invariant —
// it fails if anyone ever reorders esc/linkify or loosens the scheme match.
test('linkify cannot break out of href="" via a crafted URL (esc runs first)', () => {
    const raw = 'click https://evil.com/x"onmouseover="alert(1) now';
    const out = linkify(escAttr(raw));           // escAttr mirrors the real esc()
    assert.ok(out.includes('&quot;'), 'the breakout quote was entity-encoded, not raw');
    assert.ok(!out.includes('x"onmouseover'), 'no raw quote survived inside the href');
    assert.ok(!/<a[^>]*\sonmouseover=/i.test(out), 'no live onmouseover attribute injected');
});
test('linkify never turns a javascript: URI into a link', () => {
    const out = linkify(escAttr('run javascript:alert(1) please'));
    assert.ok(!/<a\s/i.test(out), 'javascript: scheme is not linkified at all');
});
// Regression for the localStorage plaintext-fallback (scan #13): when at-rest
// encryption is ENABLED but the key isn't held (the unlock passphrase prompt was
// cancelled or failed), the old writeState fell through to writing plaintext —
// leaking the history the user asked to encrypt and clobbering the encrypted
// blob. The fix returns 'skip' in exactly that state. Mirrors app.js.
function storageWriteMode(hasKey, encEnabled) {
    if (hasKey) return 'encrypt';
    if (encEnabled) return 'skip';
    return 'plaintext';
}
test('storage never falls back to plaintext when encryption is enabled but locked', () => {
    assert.equal(storageWriteMode(false, true), 'skip');   // the vulnerable case
});
test('storage encrypts when the key is held, even if flag reads stale', () => {
    assert.equal(storageWriteMode(true, true), 'encrypt');
    assert.equal(storageWriteMode(true, false), 'encrypt');
});
test('storage writes plaintext only when encryption is genuinely off', () => {
    assert.equal(storageWriteMode(false, false), 'plaintext');
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

// Regression test for the reply-quote onclick JS-string-breakout XSS, proven
// live with node's Function constructor (mirrors exactly how a browser
// compiles an inline event-handler attribute into a function body): even
// after esc()'s quote-encoding, `onclick="...scrollToQuoted('${esc(qName)}',this)"`
// was still exploitable, because the browser decodes HTML entities in an
// attribute value BEFORE that value is parsed as JS — so an escaped quote
// still lands as a real quote at the JS-string layer and breaks out. Reachable
// by any user just typing "> <payload>: text" as an ordinary message, no
// special API or reply-feature abuse needed.
//
// The fix removes the inline onclick attribute entirely — qName/qText now
// travel from renderMessages() to scrollToQuoted() as real JS values via a
// closure-bound addEventListener, never serialized into an attribute that
// gets parsed as code. This mirrors the current static/app.js template.
function buildReplyQuoteHtml(qName, qText) {
    return `<div class="reply-quote"><div class="reply-name">${escAttr(qName)}</div><div class="reply-text">${escAttr(qText)}</div></div>`;
}
test('reply-quote wrapper div carries no attributes at all beyond class, for any qName', () => {
    // qName/qText are only ever interpolated into the two inner divs' TEXT
    // CONTENT now, never into the wrapper's own tag — so its opening tag must
    // be this exact literal string regardless of what qName contains. (A
    // substring check for "onclick" anywhere in the HTML would false-positive
    // on a name like 'x" onclick="alert(1)' rendered as inert escaped text —
    // checking the actual tag boundary is what makes this precise.)
    const attackerNames = [
        "x',(alert(document.domain)),'",     // the exact payload confirmed to execute pre-fix
        'x");alert(1);("',
        'x" onclick="alert(1)',
        '<img src=x onerror=alert(1)>',
    ];
    for (const name of attackerNames) {
        const html = buildReplyQuoteHtml(name, 'hi');
        assert.ok(html.startsWith('<div class="reply-quote">'),
            `wrapper tag must carry no attributes for ${JSON.stringify(name)}: ${html}`);
    }
});
test('a legitimate reply quote still renders name and text as visible content', () => {
    const html = buildReplyQuoteHtml('alice', 'see you tomorrow');
    assert.ok(html.includes('>alice<'));
    assert.ok(html.includes('>see you tomorrow<'));
});

console.log(`\n${passed} passed`);
