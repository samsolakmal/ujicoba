"""
SIGAP v6.2 — Layer 2: Graph Network Engine
===========================================
Deteksi sindikat berdasarkan relasi NIK-HP (PPT Hal 5):
- 1 No. HP terhubung ke >15 NIK (default) dianggap sindikat.
"""
import pandas as pd
import networkx as nx
from config import GRAPH_SYNDICATE_THRESHOLD, SCORE_GRAPH_SYNDICATE
from utils.logger import log

def apply_graph_engine(df_delta: pd.DataFrame, df_all: pd.DataFrame = None, conn=None) -> pd.DataFrame:
    """
    Terapkan Layer 2 (Graph Network) ke DataFrame delta.
    
    Args:
        df_delta: DataFrame klaim yang baru masuk (perlu dinilai)
        df_all: DataFrame seluruh klaim historis (untuk membangun graf)
        conn: Koneksi DB (jika df_all tidak diberikan)
        
    Returns:
        DataFrame delta dengan kolom baru 'skor_graph'
    """
    if len(df_delta) == 0:
        return df_delta

    df_delta = df_delta.copy()

    # Jika df_all tidak diberikan, ambil semua data dari database
    # (Graf harus dibangun dari SELURUH data, bukan cuma data delta)
    if df_all is None:
        if conn is None:
            from core.database import get_connection
            conn = get_connection()
        log.info("Graph engine: Mengambil data historis untuk membangun graf...")
        df_all = pd.read_sql("SELECT id_klaim, nik_hash, no_hp FROM tbl_klaim_mentah", conn)
        if conn:
            conn.close()

    # ─── 1. Bangun Graf ───────────────────────────────────────
    G = nx.Graph()
    for _, row in df_all.iterrows():
        if pd.notna(row.get('no_hp')) and pd.notna(row.get('nik_hash')):
            G.add_edge(str(row['nik_hash']), str(row['no_hp']))

    # ─── 2. Hitung Skor Graph ─────────────────────────────────
    def score_hp(hp):
        if pd.isna(hp) or str(hp).strip() == '':
            return 0.0
        hp_str = str(hp).strip()
        if G.has_node(hp_str):
            degree = G.degree(hp_str)
            # Jika derajat (jumlah NIK terhubung) melebihi batas
            if degree > GRAPH_SYNDICATE_THRESHOLD:
                return SCORE_GRAPH_SYNDICATE
        return 0.0

    df_delta['skor_graph'] = df_delta['no_hp'].apply(score_hp)
    
    # ─── 3. Logging ───────────────────────────────────────────
    syndicate_count = (df_delta['skor_graph'] > 0).sum()
    if syndicate_count > 0:
        log.warning(f"Graph engine: {syndicate_count} klaim terhubung sindikat HP (>{GRAPH_SYNDICATE_THRESHOLD} NIK).")
    else:
        log.info("Graph engine: Tidak ada sindikat terdeteksi pada batch ini.")
        
    return df_delta


# ═══════════════════════════════════════════════════════════════
# SELF-TEST (jalankan: python -m core.graph_engine)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  🕸️  GRAPH ENGINE LAYER SELF-TEST")
    print("=" * 60)

    # Skenario: 1 HP Sindikat dipakai oleh 16 NIK (melebihi batas 15)
    hp_sindikat = "081199998888"
    hp_normal = "081300001111"
    
    # Dummy data historis (df_all)
    data_all = []
    # 16 NIK pakai 1 HP sindikat
    for i in range(16):
        data_all.append({"id_klaim": f"H-{i}", "nik_hash": f"hash_sindikat_{i}", "no_hp": hp_sindikat})
    # 1 NIK pakai HP normal
    data_all.append({"id_klaim": "H-Normal", "nik_hash": "hash_normal", "no_hp": hp_normal})
    df_all = pd.DataFrame(data_all)

    # Dummy data delta (klaim yang mau dinilai)
    data_delta = [
        {"id_klaim": "D-1", "no_hp": hp_sindikat}, # Harusnya kena skor 60
        {"id_klaim": "D-2", "no_hp": hp_normal},   # Harusnya skor 0
        {"id_klaim": "D-3", "no_hp": "08999999"},  # HP baru, skor 0
    ]
    df_delta = pd.DataFrame(data_delta)

    # Jalankan engine
    df_result = apply_graph_engine(df_delta, df_all=df_all)

    print("\nHasil Pengujian:")
    print("-" * 60)
    for _, row in df_result.iterrows():
        status = "🚨 SINDikat" if row['skor_graph'] > 0 else "✅ Normal"
        print(f"[{row['id_klaim']}] HP: {row['no_hp']:<15} | Skor Graph: {row['skor_graph']:>4.1f} | {status}")
    
    print("-" * 60)
    # Verifikasi
    assert df_result.loc[0, 'skor_graph'] == 60.0, "D-1 harus 60 (Sindikat)"
    assert df_result.loc[1, 'skor_graph'] == 0.0, "D-2 harus 0 (Normal)"
    assert df_result.loc[2, 'skor_graph'] == 0.0, "D-3 harus 0 (Baru)"
    
    print("\n[✓] Graph Engine LULUS SEMUA TES!")
    print("=" * 60)