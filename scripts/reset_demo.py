"""
SIGAP v6.2 — Reset Demo
========================
Wipe database & model untuk demo fresh.
"""
import sys
from pathlib import Path

# ⚠️ WAJIB DI PALING ATAS: Tambahkan root folder ke sys.path
root_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(root_dir))

from config import DB_PATH, MODELS_DIR
from utils.logger import log

def reset_all():
    """Hapus semua state: DB + model .pkl + log."""
    print("=" * 60)
    print("  🗑️  SIGAP RESET DEMO")
    print("=" * 60)
    
    # 1. Hapus SQLite + WAL files
    db_files = [
        DB_PATH,
        Path(str(DB_PATH) + "-wal"),
        Path(str(DB_PATH) + "-shm"),
    ]
    for f in db_files:
        if f.exists():
            f.unlink()
            print(f"  ✓ Hapus: {f.name}")
    
    # 2. Hapus model .pkl
    if MODELS_DIR.exists():
        for pkl in MODELS_DIR.glob("*.pkl"):
            pkl.unlink()
            print(f"  ✓ Hapus: models/{pkl.name}")
    
    print("=" * 60)
    print("  ✅ Reset selesai. Database siap untuk demo baru.")
    print("=" * 60)
    print("\nLangkah berikutnya:")
    print("  1. python -m pipelines.ingest     (generate 50 klaim)")
    print("  2. python -m pipelines.analyze    (analisis ML+XAI)")
    print("  3. streamlit run dashboard/app.py (buka dashboard)")

if __name__ == "__main__":
    # Konfirmasi kecuali ada flag -y
    if "-y" not in sys.argv:
        print("⚠️  WARNING: Semua data akan DIHAPUS (DB + models).")
        answer = input("Lanjutkan? (y/N): ").strip().lower()
        if answer != "y":
            print("Dibatalkan.")
            sys.exit(0)
    
    reset_all()