import base64


def _has_win32crypt():
    try:
        import win32crypt  # noqa: F401
        return True
    except ImportError:
        return False


def encrypt_key(plaintext: str) -> str:
    if not plaintext:
        return ""
    if plaintext.startswith("ollama") or plaintext.startswith("local"):
        return plaintext
    if not _has_win32crypt():
        return plaintext
    try:
        import win32crypt
        encrypted = win32crypt.CryptProtectData(
            plaintext.encode("utf-8"),
            "IndusFuzz API Key",
            None, None, None, 0,
        )
        return base64.b64encode(encrypted).decode("ascii")
    except Exception as e:
        print(f"[security] DPAPI 加密失败: {type(e).__name__}: {e}，明文存储作为降级（⚠️ 不安全）")
        return plaintext


def decrypt_key(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    if ciphertext.startswith("ollama") or ciphertext.startswith("local"):
        return ciphertext
    if not _has_win32crypt():
        return ciphertext
    try:
        import win32crypt
        encrypted = base64.b64decode(ciphertext)
        _, decrypted = win32crypt.CryptUnprotectData(
            encrypted, None, None, None, 0,
        )
        return decrypted.decode("utf-8")
    except Exception:
        return ciphertext


def is_encrypted(candidate: str) -> bool:
    if not candidate:
        return False
    if candidate.startswith("ollama") or candidate.startswith("local"):
        return False
    if not _has_win32crypt():
        return False
    try:
        import win32crypt
        win32crypt.CryptUnprotectData(base64.b64decode(candidate), None, None, None, 0)
        return True
    except Exception:
        return False


def mask_key(key: str) -> str:
    if not key:
        return "***"
    if key.startswith("ollama") or key.startswith("local"):
        return key
    if len(key) < 8:
        return "***"
    # 固定 4 个星号，不泄露密钥长度
    return key[:4] + "****" + key[-4:]


def store_api_key(cfg: dict, api_key: str) -> dict:
    cfg = dict(cfg)
    # 幂等保护：若已是密文则不再加密，避免二次加密自毁
    if is_encrypted(api_key):
        cfg["api_key"] = api_key
        cfg["api_key_encrypted"] = True
        return cfg
    cfg["api_key"] = encrypt_key(api_key)
    cfg["api_key_encrypted"] = is_encrypted(cfg.get("api_key", ""))
    return cfg


def get_api_key(cfg: dict) -> str:
    raw = cfg.get("api_key", "")
    if not raw:
        return ""
    if is_encrypted(raw):
        return decrypt_key(raw)
    return raw


def validate_cloud_url(url: str, provider: str) -> tuple:
    if provider in ("ollama", "none", "local"):
        return True, None
    if not url.startswith("https://"):
        return False, "云端 API 地址必须使用 HTTPS，否则 API Key 会在网络上明文传输"
    return True, None


def migrate_plaintext_config(cfg: dict) -> dict:
    """首次加载时检测明文 api_key，自动升级为加密存储"""
    raw = cfg.get("api_key", "")
    if not raw or raw.startswith("ollama") or raw.startswith("local"):
        return cfg
    # 无 win32crypt 时无法加密也无法判断密文，跳过迁移避免误报
    if not _has_win32crypt():
        return cfg
    if not is_encrypted(raw):
        print("[security] 检测到明文 API Key，自动升级为 DPAPI 加密存储")
        cfg["api_key"] = encrypt_key(raw)
        cfg["api_key_encrypted"] = True
    return cfg
