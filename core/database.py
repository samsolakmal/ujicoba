"""
SIGAP v6.2 — Database Layer (SQLite + WAL)
==========================================
DAO pattern. Semua akses DB LEWAT sini.

Fix dari Gemini & Qwen:
- WAL mode (Gemini)
- busy_timeout=5000 (Gemini)
- status_analisis state machine (Gemini)
- Zombie recovery PROCESSING > 5 min (Gemini)
- Retry logic untuk HITL writes (Qwen)
- Query WHERE status IN ('PENDING', 'FAILED') (Qwen)
"""
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional
from config import (
    DB_PATH, SQLITE_BUSY_TIMEOUT_MS, SQLITE_WAL_MODE,
    SQLITE_MAX_RETRY, SQLITE_RETRY_BACKOFF_MS,
    Status, STATUS_ZOMBIE_TIMEOUT_MIN
)
from utils.logger import log

# ═══════════════════════════════════════════════════════════════
# 1. CONNECTION FACTORY
# ═══════════════════════════════════════════════════════════════
def get_connection() -> sqlite3.Connection:
    """Buat koneksi SQLite dengan PRAGMA yang sudah di-set."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0,
        isolation_level=None  # Autocommit OFF manual
    )
    conn.row_factory = sqlite3.Row
    
    # PRAGMA (Gemini fix)
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA foreign_keys = ON;")
    if SQLITE_WAL_MODE:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    
    return conn

# ═══════════════════════════════════════════════════════════════
# 2. CONTEXT MANAGER (auto-commit/rollback)
# ═══════════════════════════════════════════════════════════════
@contextmanager
def transaction(retry: bool = True):
    """Atomic transaction dengan auto-rollback & retry."""
    attempts = SQLITE_MAX_RETRY if retry else 1
    last_error = None
    
    for attempt in range(attempts):
        conn = get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            conn.rollback()
            last_error = e
            if "locked" in str(e).lower() and attempt < attempts - 1:
                wait = SQLITE_RETRY_BACKOFF_MS * (attempt + 1) / 1000.0
                log.warning(f"DB locked, retry {attempt+1}/{attempts} in {wait}s")
                time.sleep(wait)
                continue
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    raise last_error

# ═══════════════════════════════════════════════════════════════
# 3. SCHEMA INITIALIZATION (auto-migrate)
# ═══════════════════════════════════════════════════════════════
SCHEMA_SQL = """
-- Brankas identitas mentah (UU PDP)
CREATE TABLE IF NOT EXISTS tbl_identitas_pemohon (
    id_klaim TEXT PRIMARY KEY,
    nik_mentah TEXT NOT NULL,
    nama_pasien TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Klaim yang sudah di-hash (untuk analytics)
CREATE TABLE IF NOT EXISTS tbl_klaim_mentah (
    id_klaim TEXT PRIMARY KEY,
    nik_hash TEXT NOT NULL,
    no_hp TEXT,
    status_kartu TEXT,
    jarak_km REAL,
    waktu_selisih_jam REAL,
    biaya_juta REAL,
    lat_faskes REAL,
    lng_faskes REAL,
    jenis_kunjungan TEXT,
    faskes_tujuan TEXT,
    poli_tujuan TEXT,
    status_analisis TEXT DEFAULT 'PENDING',
    error_message TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Hasil analisis ML + XAI
CREATE TABLE IF NOT EXISTS tbl_hasil_risiko (
    id_klaim TEXT PRIMARY KEY,
    nik_hash TEXT,
    skor_ml REAL,
    skor_iforest REAL,
    skor_graph REAL,
    skor_rules REAL,
    total_skor REAL,
    keputusan TEXT,
    evidence_xai TEXT,
    evidence_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_klaim) REFERENCES tbl_klaim_mentah(id_klaim)
);

-- Feedback verifikator (untuk retraining)
CREATE TABLE IF NOT EXISTS tbl_feedback_verifikator (
    id_feedback INTEGER PRIMARY KEY AUTOINCREMENT,
    id_klaim TEXT NOT NULL,
    aksi TEXT NOT NULL,
    verifikator TEXT,
    catatan TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_klaim) REFERENCES tbl_klaim_mentah(id_klaim)
);

-- Index untuk query cepat
CREATE INDEX IF NOT EXISTS idx_status_analisis ON tbl_klaim_mentah(status_analisis);
CREATE INDEX IF NOT EXISTS idx_no_hp ON tbl_klaim_mentah(no_hp);
CREATE INDEX IF NOT EXISTS idx_nik_hash ON tbl_klaim_mentah(nik_hash);
CREATE INDEX IF NOT EXISTS idx_total_skor ON tbl_hasil_risiko(total_skor);
"""

def init_schema() -> bool:
    """Buat tabel jika belum ada + auto-migrate kolom baru."""
    try:
        with transaction(retry=False) as conn:
            conn.executescript(SCHEMA_SQL)
            _migrate_columns(conn)
        log.info("✓ Database schema ready")
        return True
    except Exception as e:
        log.error(f"Schema init failed: {e}")
        return False

def _migrate_columns(conn):
    """Tambah kolom baru jika belum ada (idempotent)."""
    migrations = [
        ("tbl_klaim_mentah", "status_analisis", "TEXT DEFAULT 'PENDING'"),
        ("tbl_klaim_mentah", "error_message", "TEXT"),
        ("tbl_klaim_mentah", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("tbl_hasil_risiko", "evidence_json", "TEXT"),
    ]
    
    for table, column, col_type in migrations:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cursor.fetchall()]
        if column not in cols:
            log.info(f"Migration: ALTER {table} ADD {column}")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

# ═══════════════════════════════════════════════════════════════
# 4. ZOMBIE RECOVERY (Gemini fix)
# ═══════════════════════════════════════════════════════════════
def recover_zombie_processing() -> int:
    """Reset PROCESSING yang stuck > 5 menit menjadi FAILED."""
    try:
        cutoff = datetime.now() - timedelta(minutes=STATUS_ZOMBIE_TIMEOUT_MIN)
        with transaction() as conn:
            cursor = conn.execute("""
                UPDATE tbl_klaim_mentah
                SET status_analisis = ?, 
                    error_message = 'Zombie timeout recovered',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status_analisis = ?
                  AND updated_at < ?
            """, (Status.FAILED, Status.PROCESSING, cutoff.isoformat()))
            count = cursor.rowcount
        if count > 0:
            log.warning(f"Recovered {count} zombie PROCESSING → FAILED")
        return count
    except Exception as e:
        log.error(f"Zombie recovery failed: {e}")
        return 0

# ═══════════════════════════════════════════════════════════════
# 5. STATUS TRANSITIONS
# ═══════════════════════════════════════════════════════════════
def update_status(id_klaim: str, new_status: str, error_msg: Optional[str] = None):
    """Update status_analisis dengan validasi state machine."""
    valid = {Status.PENDING, Status.PROCESSING, Status.PROCESSED, Status.FAILED}
    if new_status not in valid:
        raise ValueError(f"Invalid status: {new_status}")
    
    with transaction() as conn:
        conn.execute("""
            UPDATE tbl_klaim_mentah
            SET status_analisis = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id_klaim = ?
        """, (new_status, error_msg, id_klaim))

def get_pending_claims() -> list:
    """Qwen fix: ambil PENDING + FAILED untuk auto-retry."""
    with transaction(retry=False) as conn:
        cursor = conn.execute("""
            SELECT * FROM tbl_klaim_mentah
            WHERE status_analisis IN (?, ?)
            ORDER BY created_at ASC
        """, (Status.PENDING, Status.FAILED))
        return [dict(row) for row in cursor.fetchall()]

# ═══════════════════════════════════════════════════════════════
# 6. HELPER DAO
# ═══════════════════════════════════════════════════════════════
def get_stats() -> dict:
    """Ringkasan statistik DB."""
    with transaction(retry=False) as conn:
        stats = {}
        stats['total_klaim'] = conn.execute(
            "SELECT COUNT(*) FROM tbl_klaim_mentah"
        ).fetchone()[0]
        stats['by_status'] = {
            row['status_analisis']: row['count']
            for row in conn.execute(
                "SELECT status_analisis, COUNT(*) as count FROM tbl_klaim_mentah GROUP BY status_analisis"
            ).fetchall()
        }
        stats['by_decision'] = {
            row['keputusan']: row['count']
            for row in conn.execute(
                "SELECT keputusan, COUNT(*) as count FROM tbl_hasil_risiko GROUP BY keputusan"
            ).fetchall()
        }
        return stats

def health_check() -> dict:
    """Cek kesehatan DB (untuk start.bat & debugging)."""
    try:
        with transaction(retry=False) as conn:
            conn.execute("PRAGMA integrity_check").fetchone()
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            
        return {
            "status": "healthy",
            "db_path": str(DB_PATH),
            "journal_mode": mode,
            "tables": tables,
            "size_kb": round(DB_PATH.stat().st_size / 1024, 2) if DB_PATH.exists() else 0
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ═══════════════════════════════════════════════════════════════
# 7. SELF-TEST (jalankan: python -m core.database)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  🗄️  DATABASE LAYER SELF-TEST")
    print("=" * 60)
    
    print("\n[1] Init schema...")
    assert init_schema(), "Schema init failed"
    
    print("\n[2] Health check...")
    health = health_check()
    print(f"  Status       : {health['status']}")
    print(f"  DB Path      : {health['db_path']}")
    print(f"  Journal mode : {health['journal_mode']} (harus WAL)")
    print(f"  Size         : {health['size_kb']} KB")
    print(f"  Tables       : {', '.join(health['tables'])}")
    
    print("\n[3] Test zombie recovery...")
    recovered = recover_zombie_processing()
    print(f"  Zombie recovered: {recovered}")
    
    print("\n[4] Test stats...")
    stats = get_stats()
    print(f"  Total klaim : {stats['total_klaim']}")
    print(f"  By status   : {stats['by_status']}")
    print(f"  By decision : {stats['by_decision']}")
    
    print("\n[✓] Database layer OK")
    print("=" * 60)