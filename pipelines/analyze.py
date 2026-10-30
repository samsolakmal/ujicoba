"""
SIGAP v6.2 — Analyze Pipeline (Orchestrator)
=============================================
Mengambil data PENDING, memprosesnya lewat 3 Layer ML + XAI,
lalu menyimpannya ke tbl_hasil_risiko.
"""
import pandas as pd
import traceback
import json
from config import Status
from core.database import transaction, get_pending_claims, update_status
from core.rule_engine import apply_rule_engine
from core.graph_engine import apply_graph_engine
from core.ml_engine import apply_ml_engine
from core.ensemble import apply_ensemble
from core.xai_narrator import generate_xai
from utils.logger import log

def run_analysis() -> tuple[int, str]:
    """Fungsi utama untuk memproses klaim yang PENDING. Return (total_processed, error_msg)"""
    
    # 1. Ambil data dari antrean
    pending_claims = get_pending_claims()
    if not pending_claims:
        log.info("Analyze Pipeline: Tidak ada klaim PENDING/FAILED. Sistem idle.")
        return 0, "Tidak ada data PENDING"

    log.info(f"Analyze Pipeline: Memproses {len(pending_claims)} klaim...")
    df_delta = pd.DataFrame(pending_claims)

    # 2. Tandai sebagai PROCESSING (State Machine)
    for id_klaim in df_delta['id_klaim']:
        update_status(id_klaim, Status.PROCESSING)

    try:
        # 3. Ambil semua data historis untuk Graph Engine & ML Training
        with transaction(retry=False) as conn:
            # WAJIB SELECT * AGAR SEMUA FITUR ML TERSEDIA
            df_all = pd.read_sql("SELECT * FROM tbl_klaim_mentah", conn)

        # 4. Jalankan Mesin Berurutan
        log.info("  -> Layer 1: Rule-Based Engine")
        df_delta = apply_rule_engine(df_delta)

        log.info("  -> Layer 2: Graph Network Engine")
        df_delta = apply_graph_engine(df_delta, df_all=df_all)

        log.info("  -> Layer 3: ML Ensemble (XGBoost + IForest)")
        df_delta = apply_ml_engine(df_delta, df_all=df_all)

        log.info("  -> Menggabungkan Skor (Ensemble)")
        df_delta = apply_ensemble(df_delta)

        # 5. Generate XAI & Simpan ke Database
        log.info("  -> Generate XAI Narasi...")
        
        with transaction() as conn:
            for _, row in df_delta.iterrows():
                # Siapkan payload untuk XAI
                claim_payload = row.to_dict()
                claim_payload = {k: (v if pd.notna(v) else 0) for k, v in claim_payload.items()}
                
                # Panggil XAI (4-Tier Cascade)
                xai_result = generate_xai(claim_payload)
                
                # Simpan ke tbl_hasil_risiko
                conn.execute("""
                    INSERT OR REPLACE INTO tbl_hasil_risiko
                    (id_klaim, nik_hash, skor_ml, skor_iforest, skor_graph, 
                     skor_rules, total_skor, keputusan, evidence_xai, evidence_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['id_klaim'],
                    row['nik_hash'],
                    round(float(row['skor_ml']), 2),
                    round(float(row['skor_iforest']), 2),
                    round(float(row['skor_graph']), 2),
                    round(float(row['skor_rules']), 2),
                    round(float(row['total_skor']), 2),
                    row['keputusan'],
                    xai_result['alasan_utama'],
                    json.dumps(xai_result, ensure_ascii=False)
                ))
                
                # Ubah status jadi PROCESSED
                conn.execute("""
                    UPDATE tbl_klaim_mentah 
                    SET status_analisis = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id_klaim = ?
                """, (Status.PROCESSED, row['id_klaim']))

        log.info(f"Analyze Pipeline: {len(df_delta)} klaim berhasil diproses (PROCESSED).")
        return len(df_delta), ""

    except Exception as e:
        # JIKA CRASH: Rollback status PROCESSING -> FAILED
        log.error(f"Analyze Pipeline GAGAL: {e}")
        traceback.print_exc()
        for id_klaim in df_delta['id_klaim']:
            update_status(id_klaim, Status.FAILED, error_msg=str(e)[:200])
        return 0, str(e)

# ═══════════════════════════════════════════════════════════════
# SELF-TEST (jalankan: python -m pipelines.analyze)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from core.database import get_stats
    
    print("=" * 60)
    print("  ⚙️  ANALYZE PIPELINE SELF-TEST")
    print("=" * 60)
    
    print("\n[1] State Sebelum Analisis:")
    stats_before = get_stats()
    print(f"    Status      : {stats_before['by_status']}")

    print("\n[2] Menjalankan Analisis...")
    total, err = run_analysis()

    print("\n[3] State Setelah Analisis:")
    stats_after = get_stats()
    print(f"    Status      : {stats_after['by_status']}")
    print(f"    Keputusan   : {stats_after['by_decision']}")
    
    if err:
        print(f"\n[!] Error: {err}")
    else:
        print(f"\n[✓] Berhasil memproses {total} klaim.")
        
    print("=" * 60)