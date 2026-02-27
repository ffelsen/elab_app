"""auth.py — Encrypted local key store for the ElabFTW logger app.

Each user has one encrypted file:  keys/<short_name>.enc
File format (binary, concatenated):
    16 bytes  — random salt (for PBKDF2)
    N bytes   — Fernet-encrypted API key

The Fernet symmetric key is derived from the user's PIN via PBKDF2-HMAC-SHA256,
so the raw API key is never stored on disk in plaintext.
"""

import os
import re
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

import elabapi_python
from warnings import filterwarnings

filterwarnings("ignore")

# ── Constants ────────────────────────────────────────────────────────────────

KEYS_DIR = Path(__file__).parent / "keys"
ELAB_HOST = "https://elabftw-qa-2024.zit.ph.tum.de/api/v2"

# Short name must be lowercase letters, digits, or underscores, starting with a letter
_SHORT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

PBKDF2_ITERATIONS = 480_000  # OWASP 2023 recommendation for PBKDF2-HMAC-SHA256


# ── Validation ───────────────────────────────────────────────────────────────

def is_valid_short_name(name: str) -> bool:
    """Return True if *name* matches the short-name rules."""
    return bool(_SHORT_NAME_RE.match(name))


# ── Key-file helpers ─────────────────────────────────────────────────────────

def list_users() -> list[str]:
    """Return a sorted list of short names that have an encrypted key file."""
    KEYS_DIR.mkdir(exist_ok=True)
    return sorted(p.stem for p in KEYS_DIR.glob("*.enc"))


def _key_path(short_name: str) -> Path:
    return KEYS_DIR / f"{short_name}.enc"


def user_exists(short_name: str) -> bool:
    """Return True if an encrypted key file exists for *short_name*."""
    return _key_path(short_name).exists()


def _derive_fernet_key(pin: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet-compatible key from *pin* and *salt*."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    raw = kdf.derive(pin.encode())
    return base64.urlsafe_b64encode(raw)


# ── Public API ───────────────────────────────────────────────────────────────

def save_key(short_name: str, pin: str, api_key: str) -> None:
    """Encrypt *api_key* with *pin* and save to ``keys/<short_name>.enc``.

    Raises
    ------
    ValueError
        If *short_name* is not valid.
    """
    if not is_valid_short_name(short_name):
        raise ValueError(f"Invalid short name: {short_name!r}")
    KEYS_DIR.mkdir(exist_ok=True)
    salt = os.urandom(16)
    fernet_key = _derive_fernet_key(pin, salt)
    f = Fernet(fernet_key)
    encrypted = f.encrypt(api_key.strip().encode())
    with open(_key_path(short_name), "wb") as fh:
        fh.write(salt + encrypted)


def load_key(short_name: str, pin: str) -> str:
    """Decrypt and return the API key for *short_name* using *pin*.

    Raises
    ------
    FileNotFoundError
        If no key file exists for *short_name*.
    ValueError
        If the PIN is wrong or the file is corrupt.
    """
    path = _key_path(short_name)
    if not path.exists():
        raise FileNotFoundError(f"No key file found for user '{short_name}'.")
    with open(path, "rb") as fh:
        data = fh.read()
    salt, encrypted = data[:16], data[16:]
    fernet_key = _derive_fernet_key(pin, salt)
    try:
        api_key = Fernet(fernet_key).decrypt(encrypted).decode()
    except InvalidToken:
        raise ValueError("Incorrect PIN or corrupted key file.")
    return api_key


# ── elabFTW helpers ──────────────────────────────────────────────────────────

def _make_api_client(api_key: str) -> elabapi_python.ApiClient:
    """Build an elabapi_python ApiClient from a raw API key."""
    cfg = elabapi_python.Configuration()
    cfg.api_key["api_key"] = api_key
    cfg.api_key_prefix["api_key"] = "Authorization"
    cfg.host = ELAB_HOST
    cfg.debug = False
    cfg.verify_ssl = False
    client = elabapi_python.ApiClient(cfg)
    client.set_default_header(header_name="Authorization", header_value=api_key)
    return client


def fetch_user_info(api_key: str) -> dict:
    """Call ``GET /users/me`` and return a dict with user details.

    Returns
    -------
    dict with keys:
        fullname  : str   — display name (e.g. "Alice M.")
        firstname : str
        lastname  : str
        userid    : int
        teams     : list[dict]  — each has 'id' and 'name'

    Raises
    ------
    elabapi_python.rest.ApiException
        On authentication failure or network error.
    """
    client = _make_api_client(api_key)
    uapi = elabapi_python.UsersApi(client)
    me = uapi.read_user("me")
    teams = [{"id": t.id, "name": t.name} for t in (me.teams or [])]
    return {
        "fullname": me.fullname,
        "firstname": me.firstname,
        "lastname": me.lastname,
        "userid": me.userid,
        "teams": teams,
    }


def build_api_client_from_session(api_key: str) -> elabapi_python.ApiClient:
    """Convenience wrapper used by main.py after a successful login."""
    return _make_api_client(api_key)
