"""
EPL Crypto Package - Python Backend
Encryption & cryptography: AES-256, RSA, signatures, key derivation, file encryption.
"""

import base64 as _b64
import hashlib as _hashlib
import os as _os

# ═══════════════════════════════════════════════════════════
#  AES-256 Symmetric Encryption (using cryptography lib if available, else fallback)
# ═══════════════════════════════════════════════════════════

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa, padding as _padding
    from cryptography.hazmat.primitives import hashes as _hashes, serialization as _ser

    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False


def aes_generate_key():
    key = _os.urandom(32)
    return _b64.b64encode(key).decode()


def aes_encrypt(plaintext, secret_key):
    key = _b64.b64decode(secret_key.encode())
    if _HAS_CRYPTOGRAPHY:
        aesgcm = _AESGCM(key)
        nonce = _os.urandom(12)
        ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return _b64.b64encode(nonce + ct).decode()
    else:
        # XOR-based fallback (NOT secure, but functional without cryptography lib)
        from itertools import cycle

        data = plaintext.encode()
        encrypted = bytes(a ^ b for a, b in zip(data, cycle(key)))
        return _b64.b64encode(encrypted).decode()


def aes_decrypt(ciphertext, secret_key):
    key = _b64.b64decode(secret_key.encode())
    raw = _b64.b64decode(ciphertext.encode())
    if _HAS_CRYPTOGRAPHY:
        aesgcm = _AESGCM(key)
        nonce = raw[:12]
        ct = raw[12:]
        return aesgcm.decrypt(nonce, ct, None).decode()
    else:
        from itertools import cycle

        decrypted = bytes(a ^ b for a, b in zip(raw, cycle(key)))
        return decrypted.decode()


# ═══════════════════════════════════════════════════════════
#  RSA Asymmetric Encryption
# ═══════════════════════════════════════════════════════════


def rsa_generate_keypair(key_size=2048):
    if not _HAS_CRYPTOGRAPHY:
        raise RuntimeError(
            "RSA requires the 'cryptography' package. Install with: pip install cryptography"
        )
    private_key = _rsa.generate_private_key(public_exponent=65537, key_size=int(key_size))
    priv_pem = private_key.private_bytes(
        encoding=_ser.Encoding.PEM,
        format=_ser.PrivateFormat.PKCS8,
        encryption_algorithm=_ser.NoEncryption(),
    ).decode()
    pub_pem = (
        private_key.public_key()
        .public_bytes(encoding=_ser.Encoding.PEM, format=_ser.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return {'private_key': priv_pem, 'public_key': pub_pem}


def rsa_encrypt(plaintext, public_key):
    if not _HAS_CRYPTOGRAPHY:
        raise RuntimeError("RSA requires the 'cryptography' package.")
    pub = _ser.load_pem_public_key(public_key.encode())
    ct = pub.encrypt(
        plaintext.encode(),
        _padding.OAEP(
            mgf=_padding.MGF1(algorithm=_hashes.SHA256()), algorithm=_hashes.SHA256(), label=None
        ),
    )
    return _b64.b64encode(ct).decode()


def rsa_decrypt(ciphertext, private_key):
    if not _HAS_CRYPTOGRAPHY:
        raise RuntimeError("RSA requires the 'cryptography' package.")
    priv = _ser.load_pem_private_key(private_key.encode(), password=None)
    raw = _b64.b64decode(ciphertext.encode())
    pt = priv.decrypt(
        raw,
        _padding.OAEP(
            mgf=_padding.MGF1(algorithm=_hashes.SHA256()), algorithm=_hashes.SHA256(), label=None
        ),
    )
    return pt.decode()


def rsa_get_public_key(keypair):
    return keypair['public_key']


def rsa_get_private_key(keypair):
    return keypair['private_key']


# ═══════════════════════════════════════════════════════════
#  Digital Signatures
# ═══════════════════════════════════════════════════════════


def sign(message, private_key):
    if not _HAS_CRYPTOGRAPHY:
        raise RuntimeError("Signing requires the 'cryptography' package.")
    from cryptography.hazmat.primitives.asymmetric import utils as _utils

    priv = _ser.load_pem_private_key(private_key.encode(), password=None)
    sig = priv.sign(
        message.encode(),
        _padding.PSS(mgf=_padding.MGF1(_hashes.SHA256()), salt_length=_padding.PSS.MAX_LENGTH),
        _hashes.SHA256(),
    )
    return _b64.b64encode(sig).decode()


def verify_signature(message, signature, public_key):
    if not _HAS_CRYPTOGRAPHY:
        raise RuntimeError("Verification requires the 'cryptography' package.")
    pub = _ser.load_pem_public_key(public_key.encode())
    try:
        pub.verify(
            _b64.b64decode(signature.encode()),
            message.encode(),
            _padding.PSS(mgf=_padding.MGF1(_hashes.SHA256()), salt_length=_padding.PSS.MAX_LENGTH),
            _hashes.SHA256(),
        )
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
#  Key Derivation
# ═══════════════════════════════════════════════════════════


def derive_key(password, salt, iterations=100000):
    dk = _hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations))
    return _b64.b64encode(dk).decode()


def generate_salt(length=16):
    return _b64.b64encode(_os.urandom(int(length))).decode()


# ═══════════════════════════════════════════════════════════
#  Password-based Encryption
# ═══════════════════════════════════════════════════════════


def password_encrypt(plaintext, password):
    salt = _os.urandom(16)
    dk = _hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    key = _b64.b64encode(dk).decode()
    ct = aes_encrypt(plaintext, key)
    return _b64.b64encode(salt).decode() + ':' + ct


def password_decrypt(ciphertext, password):
    parts = ciphertext.split(':', 1)
    salt = _b64.b64decode(parts[0].encode())
    ct = parts[1]
    dk = _hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    key = _b64.b64encode(dk).decode()
    return aes_decrypt(ct, key)


# ═══════════════════════════════════════════════════════════
#  File Encryption
# ═══════════════════════════════════════════════════════════


def encrypt_file(input_path, output_path, secret_key):
    with open(input_path, 'rb') as f:
        data = f.read()
    encrypted = aes_encrypt(data.decode('utf-8', errors='replace'), secret_key)
    with open(output_path, 'w') as f:
        f.write(encrypted)
    return True


def decrypt_file(input_path, output_path, secret_key):
    with open(input_path, 'r') as f:
        encrypted = f.read()
    decrypted = aes_decrypt(encrypted, secret_key)
    with open(output_path, 'w') as f:
        f.write(decrypted)
    return True


def hash_file(file_path, algorithm='sha256'):
    h = _hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ═══════════════════════════════════════════════════════════
#  Random & Encoding Utilities
# ═══════════════════════════════════════════════════════════


def random_bytes(num_bytes):
    return _b64.b64encode(_os.urandom(int(num_bytes))).decode()


def random_hex(length):
    return _os.urandom(int(length) // 2 + 1).hex()[: int(length)]


def to_base64(data):
    return _b64.b64encode(str(data).encode()).decode()


def from_base64(encoded_data):
    return _b64.b64decode(encoded_data.encode()).decode()


def to_hex(data):
    return str(data).encode().hex()


def from_hex(hex_data):
    return bytes.fromhex(hex_data).decode()
