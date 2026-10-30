"""
SIGAP v6.2 — Centralized Logger
================================
Sanitized logging — tidak ada PII yang bisa leak ke log file.
"""
import logging
import re
import sys
from pathlib import Path
from config import LOG_PATH

# ─── PII Sanitizer (UU PDP) ───────────────────────────────
PII_PATTERNS = [
    (re.compile(r'\b\d{16}\b'), '[NIK_REDACTED]'),           # NIK 16 digit
    (re.compile(r'\b08\d{8,11}\b'), '[HP_REDACTED]'),         # No. HP
    (re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b'), '[NIK_REDACTED]'),  # NIK with spaces
    (re.compile(r'(?i)pasien[_\s]\w+'), '[PASIEN_REDACTED]'), # Nama pasien
]

def sanitize_pii(text: str) -> str:
    """Hapus PII dari string sebelum di-log."""
    if not isinstance(text, str):
        text = str(text)
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text

# ─── Custom Formatter ─────────────────────────────────────
class SanitizedFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        return sanitize_pii(msg)

# ─── Logger Factory ───────────────────────────────────────
def get_logger(name: str = "sigap") -> logging.Logger:
    logger = logging.getLogger(name)
    
    if logger.handlers:  # Sudah di-configure
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(SanitizedFormatter(
        '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
        datefmt='%H:%M:%S'
    ))
    logger.addHandler(console)
    
    # File handler
    try:
        Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_PATH, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(SanitizedFormatter(
            '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"File logging disabled: {e}")
    
    return logger

# Singleton
log = get_logger("sigap")