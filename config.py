"""
SIGAP v6.2 — Central Configuration
===================================
Fondasi setting. Semua magic number & path di sini.
Zero hardcode di file lain.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env (jika ada)
load_dotenv()

# ═══════════════════════════════════════════════════════════════
# 1. PATHS
# ═══════════════════════════════════════════════════════════════
ROOT_DIR = Path(__file__).parent.resolve()
DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
LOGS_DIR = ROOT_DIR / "logs"

# Pastikan folder otomatis dibuat jika belum ada
DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

DB_PATH = Path(os.getenv("SIGAP_DB_PATH", DATA_DIR / "sigap_v6.db"))
LOG_PATH = Path(os.getenv("SIGAP_LOG_PATH", LOGS_DIR / "sigap.log"))

# ═══════════════════════════════════════════════════════════════
# 2. SECURITY (UU PDP)
# ═══════════════════════════════════════════════════════════════
SIGAP_SALT = os.getenv("SIGAP_SALT", "BPJS_SIGAP_2026_SALT_FALLBACK_INSECURE")
HASH_LENGTH = 16  # Panjang hash output (dipotong dari 64 hex SHA-256)

# ═══════════════════════════════════════════════════════════════
# 3. DATABASE
# ═══════════════════════════════════════════════════════════════
SQLITE_BUSY_TIMEOUT_MS = 5000   # 5 detik timeout untuk Windows
SQLITE_WAL_MODE = True          # Write-Ahead Logging (anti-lock)
SQLITE_MAX_RETRY = 3            # Retry untuk HITL writes
SQLITE_RETRY_BACKOFF_MS = 100   # Jeda antar retry

# ═══════════════════════════════════════════════════════════════
# 4. STATUS STATE MACHINE
# ═══════════════════════════════════════════════════════════════
class Status:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"

STATUS_ZOMBIE_TIMEOUT_MIN = 5   # Timeout untuk status PROCESSING yang macet

# ═══════════════════════════════════════════════════════════════
# 5. 3-TIER CLASSIFICATION (PPT Hal 4)
# ═══════════════════════════════════════════════════════════════
TIER_FRAUD_THRESHOLD = 60.0       # >= 60: DITAHAN (FRAUD)
TIER_REVIEW_THRESHOLD = 35.0      # >= 35: REVIEW RINGAN
TIER_SAFE_THRESHOLD = 0.0         # < 35: LOLOS (AMAN)

class Tier:
    FRAUD = "DITAHAN (FRAUD)"
    REVIEW = "REVIEW RINGAN"
    SAFE = "LOLOS (AMAN)"

# ═══════════════════════════════════════════════════════════════
# 6. ALGORITHM PARAMETERS (PPT Hal 5)
# ═══════════════════════════════════════════════════════════════
# Layer 1: Rule-Based
SCORE_NON_AKTIF = 50.0            # Sesuai PPT: +50

# Layer 2: Spatiotemporal
IMPOSSIBLE_TRAVEL_KM = 300.0
IMPOSSIBLE_TRAVEL_HOURS = 3.0
SCORE_IMPOSSIBLE_TRAVEL = 60.0
EMERGENCY_KEYWORDS = ["RSUD", "RSCM", "Tipe A"]
EMERGENCY_VISIT_TYPE = "rujukan darurat"

# Layer 3: Graph Network
GRAPH_SYNDICATE_THRESHOLD = 15    # PPT Hal 5: >15 NIK
SCORE_GRAPH_SYNDICATE = 60.0

# ═══════════════════════════════════════════════════════════════
# 7. ENSEMBLE FORMULA
# ═══════════════════════════════════════════════════════════════
WEIGHT_XGBOOST = 0.7
WEIGHT_IFOREST = 0.3
ML_MAX_SCORE = 70.0               # Konversi probabilitas ke skor max

# XGBoost (CPU only, aman untuk RAM 12GB)
XGB_PARAMS = {
    "n_estimators": 50,
    "max_depth": 4,
    "learning_rate": 0.08,
    "tree_method": "hist",
    "device": "cpu",
    "n_jobs": -1,
    "random_state": 42
}

# Isolation Forest
IFOREST_PARAMS = {
    "contamination": 0.01,
    "n_jobs": -1,
    "random_state": 42
}

ML_FEATURES = [
    "status_aktif_num",
    "jarak_km",
    "waktu_selisih_jam",
    "biaya_juta"
]

# ═══════════════════════════════════════════════════════════════
# 8. XAI CASCADE (4-tier)
# ═══════════════════════════════════════════════════════════════
QWEN_TIMEOUT_SEC = 3.0
GEMINI_TIMEOUT_SEC = 5.0
XAI_MAX_WORDS = 25
XAI_MAX_CHARS = 200

# ═══════════════════════════════════════════════════════════════
# 9. DEMO MODE
# ═══════════════════════════════════════════════════════════════
DEMO_MODE = os.getenv("SIGAP_DEMO_MODE", "true").lower() == "true"
DEMO_CLAIMS_PER_BATCH = 50
DEMO_SYNDICATE_HP = "081199998888"

# ═══════════════════════════════════════════════════════════════
# 10. VALIDATION (Fail-fast)
# ═══════════════════════════════════════════════════════════════
def validate_config():
    """Fail-fast kalau ada yang salah config."""
    errors = []
    
    if len(SIGAP_SALT) < 16:
        errors.append("SIGAP_SALT minimal 16 karakter (UU PDP)")
    
    if "CHANGE_ME" in SIGAP_SALT and not DEMO_MODE:
        errors.append("SIGAP_SALT masih default, ganti sebelum production")
    
    if WEIGHT_XGBOOST + WEIGHT_IFOREST > 1.01:
        errors.append(f"Bobot ensemble {WEIGHT_XGBOOST}+{WEIGHT_IFOREST} > 1.0")
    
    if TIER_FRAUD_THRESHOLD <= TIER_REVIEW_THRESHOLD:
        errors.append("TIER_FRAUD_THRESHOLD harus > TIER_REVIEW_THRESHOLD")
    
    if errors:
        raise ValueError("❌ Config Error:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True

# Auto-validate saat import
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as e:
        print(f"[!] Warning: {e}")
        print("[!] Mode demo tetap lanjut, tapi jangan pakai di production.")