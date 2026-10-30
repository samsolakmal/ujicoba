"""
SIGAP v6.2 — Hashing Layer (UU PDP Compliant)
==============================================
Salted SHA-256 untuk anonimisasi NIK.
Output: 16 char hex (dari 64 hex SHA-256).

Aturan:
- NIK mentah HANYA hidup di sini (transient di memory)
- Setelah di-hash, NIK mentah tidak boleh dipakai lagi
- SALT tidak boleh di-commit ke git (.env only)
"""
import hashlib
from typing import Optional
from config import SIGAP_SALT, HASH_LENGTH
from utils.logger import log

def hash_nik(nik_mentah: str) -> str:
    """
    Hash NIK dengan Salted SHA-256.
    
    Args:
        nik_mentah: NIK 16 digit (string)
    
    Returns:
        16-char hex hash
    
    Raises:
        ValueError: jika NIK invalid (None, empty, bukan digit)
    """
    if not nik_mentah:
        raise ValueError("NIK tidak boleh kosong")
    
    nik_str = str(nik_mentah).strip()
    
    if not nik_str.isdigit():
        raise ValueError(f"NIK harus angka (16 digit), dapat: {type(nik_mentah)}")
    
    if len(nik_str) != 16:
        log.warning(f"NIK bukan 16 digit ({len(nik_str)} digit), tetap di-hash")
    
    # Salted SHA-256 → hex → 16 char
    raw = f"{SIGAP_SALT}{nik_str}"
    full_hash = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return full_hash[:HASH_LENGTH]

def verify_hash(nik_mentah: str, expected_hash: str) -> bool:
    """Verifikasi NIK cocok dengan hash (untuk testing/recovery)."""
    try:
        return hash_nik(nik_mentah) == expected_hash
    except ValueError:
        return False

def hash_optional(nik_mentah: Optional[str]) -> Optional[str]:
    """Safe version — return None jika input None."""
    if nik_mentah is None:
        return None
    try:
        return hash_nik(nik_mentah)
    except ValueError as e:
        log.warning(f"Hash gagal: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
# SELF-TEST (jalankan: python -m core.hashing)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  🔐 HASHING LAYER SELF-TEST")
    print("=" * 60)
    
    test_nik = "3275082112345678"
    h1 = hash_nik(test_nik)
    h2 = hash_nik(test_nik)
    
    print(f"NIK input       : {test_nik}")
    print(f"Hash 1          : {h1}")
    print(f"Hash 2          : {h2}")
    print(f"Deterministik?  : {h1 == h2} (harus True)")
    print(f"Panjang hash    : {len(h1)} (harus {HASH_LENGTH})")
    print(f"NIK di hash?    : {test_nik in h1} (harus False)")
    print(f"Verify match?   : {verify_hash(test_nik, h1)} (harus True)")
    
    # Edge case
    print("\n[Edge Cases]")
    try:
        hash_nik("")
    except ValueError as e:
        print(f"  Empty NIK       : ✓ Reject ({e})")
    
    try:
        hash_nik("bukan-angka")
    except ValueError as e:
        print(f"  Non-digit NIK   : ✓ Reject ({e})")
    
    print(f"  None optional   : {hash_optional(None)} (harus None)")
    
    print("\n[✓] Hashing layer OK")
    print("=" * 60)