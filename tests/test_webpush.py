"""
Tests for the hand-rolled Web Push implementation (RFC 8188/8291/8292).

The encryption is verified by decrypting our own output the way a browser
would, so a mistake in the HKDF chain or the record header cannot pass.

Run:  python tests/test_webpush.py
"""
import base64
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils  # noqa: E402
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: E402

import webpush  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def ua_decrypt(body, ua_private, auth_secret):
    """Decrypt an aes128gcm body the way a user agent does (RFC 8291 receiver)."""
    salt = body[:16]
    _rs, idlen = struct.unpack('!IB', body[16:21])
    as_public_raw = body[21:21 + idlen]
    ciphertext = body[21 + idlen:]

    as_public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), as_public_raw)
    shared = ua_private.exchange(ec.ECDH(), as_public)
    ua_public_raw = ua_private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)

    def hkdf(slt, ikm, info, length):
        return HKDF(algorithm=hashes.SHA256(), length=length,
                    salt=slt, info=info).derive(ikm)

    prk = hkdf(auth_secret, shared,
               b'WebPush: info\x00' + ua_public_raw + as_public_raw, 32)
    cek = hkdf(salt, prk, b'Content-Encoding: aes128gcm\x00', 16)
    nonce = hkdf(salt, prk, b'Content-Encoding: nonce\x00', 12)
    plain = AESGCM(cek).decrypt(nonce, ciphertext, None)
    return plain.rstrip(b'\x02')


def main():
    print("webpush")

    # base64url round-trip, including a length that needs padding
    for raw in (b'', b'a', b'ab', b'abc', os.urandom(65)):
        check(f'b64u round-trips {len(raw)} bytes',
              webpush.b64u_decode(webpush.b64u_encode(raw)) == raw)
    check('b64u output is unpadded url-safe',
          '=' not in webpush.b64u_encode(os.urandom(65)))

    # VAPID key material
    keys = webpush.generate_vapid()
    check('vapid private key is 32 bytes', len(webpush.b64u_decode(keys['private'])) == 32)
    pub = webpush.b64u_decode(keys['public'])
    check('vapid public key is a 65-byte uncompressed point',
          len(pub) == 65 and pub[0] == 0x04)

    # Encryption: decrypt our own body as the browser would
    ua_private = ec.generate_private_key(ec.SECP256R1())
    ua_public_raw = ua_private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth_secret = os.urandom(16)

    payload = json.dumps({'title': 'алиса', 'body': 'Новое сообщение'},
                         ensure_ascii=False).encode('utf-8')
    body = webpush.encrypt_payload(payload, ua_public_raw, auth_secret)

    check('body carries the 21-byte aes128gcm header plus sender key',
          len(body) > 21 + 65 and struct.unpack('!B', body[20:21])[0] == 65)
    check('record size field matches', struct.unpack('!I', body[16:20])[0] == webpush.RECORD_SIZE)
    check('round-trip decrypts to the original payload',
          ua_decrypt(body, ua_private, auth_secret) == payload)
    check('payload survives non-ascii',
          json.loads(ua_decrypt(body, ua_private, auth_secret))['title'] == 'алиса')

    # A fresh salt/ephemeral key per call means identical input differs on the wire
    body2 = webpush.encrypt_payload(payload, ua_public_raw, auth_secret)
    check('each call uses fresh salt and ephemeral key', body[:16] != body2[:16] and body != body2)

    # Wrong auth secret must not decrypt
    try:
        ua_decrypt(body, ua_private, os.urandom(16))
        check('wrong auth secret is rejected', False)
    except Exception:
        check('wrong auth secret is rejected', True)

    # VAPID JWT structure and signature
    endpoint = 'https://fcm.googleapis.com/fcm/send/abc123'
    header = webpush._vapid_auth_header(endpoint, keys, 'mailto:a@b.c')
    check('auth header uses the vapid scheme', header.startswith('vapid t='))
    token = header[len('vapid t='):].split(',')[0]
    h_b64, c_b64, s_b64 = token.split('.')
    jwt_header = json.loads(webpush.b64u_decode(h_b64))
    claims = json.loads(webpush.b64u_decode(c_b64))
    check('jwt alg is ES256', jwt_header['alg'] == 'ES256')
    check('aud is the endpoint origin, without the path',
          claims['aud'] == 'https://fcm.googleapis.com')
    check('sub is carried through', claims['sub'] == 'mailto:a@b.c')
    check('exp is in the future and within 24h',
          0 < claims['exp'] - int(__import__('time').time()) <= 86400)

    sig = webpush.b64u_decode(s_b64)
    check('jws signature is raw r||s, not DER', len(sig) == 64 and sig[0] != 0x30)
    der = asym_utils.encode_dss_signature(
        int.from_bytes(sig[:32], 'big'), int.from_bytes(sig[32:], 'big'))
    pubkey = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub)
    pubkey.verify(der, f'{h_b64}.{c_b64}'.encode('ascii'), ec.ECDSA(hashes.SHA256()))
    check('signature verifies against the advertised public key', True)

    check('header advertises the same key it signed with', f"k={keys['public']}" in header)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
