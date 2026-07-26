/* CSRF: attach the session's synchronizer token to same-origin mutating
   requests. The token is rendered into <meta name="csrf-token"> on every page
   (bound to the Flask session); the server rejects mutating requests whose
   X-CSRF-Token header doesn't match. Defense-in-depth on top of SameSite=Lax.

   Loaded BEFORE any other script so the wrapper is in place before the first
   fetch. Covers all fetch() call sites (app.js + inline template scripts)
   without touching each one. */
(function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    var TOKEN = meta ? meta.getAttribute('content') : '';
    var UNSAFE = { POST: 1, PUT: 1, PATCH: 1, DELETE: 1 };
    var origFetch = window.fetch;
    if (!origFetch) return;

    window.fetch = function (input, init) {
        init = init || {};
        var method = (init.method ||
            (input && typeof input !== 'string' && input.method) || 'GET').toUpperCase();
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        // Only same-origin requests. MUST be an exact origin match via URL
        // parsing, not a string-prefix check: indexOf(location.origin)===0
        // treats "https://example.com.evil.com" as same-origin too (it DOES
        // start with "https://example.com"), leaking the CSRF token — a
        // secret meant only for this origin — to an attacker-controlled host.
        var sameOrigin;
        try {
            sameOrigin = new URL(url, location.href).origin === location.origin;
        } catch (e) {
            sameOrigin = false;
        }
        if (TOKEN && sameOrigin && UNSAFE[method]) {
            var headers = new Headers(
                init.headers ||
                (input && typeof input !== 'string' && input.headers) || {});
            if (!headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', TOKEN);
            init = Object.assign({}, init, { headers: headers });
        }
        return origFetch.call(this, input, init);
    };
})();
