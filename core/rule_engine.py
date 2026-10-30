"""
SIGAP v6.2 — Layer 1: Rule-Based Engine
========================================
Deteksi pelanggaran aturan eksplisit (PPT Hal 5):
1. Status Kartu Non-Aktif → +50
2. Impossible Travel (Jarak >300km & Waktu <3jam) → +60
   KECUALI: Rujukan Darurat / RSUD / RSCM / RS Tipe A
"""
import pandas as pd
import numpy as np
from config import (
    SCORE_NON_AKTIF,
    IMPOSSIBLE_TRAVEL_KM,
    IMPOSSIBLE_TRAVEL_HOURS,
    SCORE_IMPOSSIBLE_TRAVEL,
    EMERGENCY_KEYWORDS,
    EMERGENCY_VISIT_TYPE
)
from utils.logger import log

def apply_rule_engine(df: pd.DataFrame) -> pd.DataFrame:
    """
    Terapkan Layer 1 (Rule-Based) ke DataFrame.
    Return DataFrame dengan kolom baru:
    - status_aktif_num
    - spatiotemporal_anomaly
    - skor_rules
    """
    if len(df) == 0:
        return df

    df = df.copy()

    # ─── 1. Konversi Status Kartu ─────────────────────────────
    df['status_aktif_num'] = df['status_kartu'].apply(
        lambda x: 1 if str(x).strip().lower() == 'aktif' else 0
    )
    df['skor_rules'] = np.where(
        df['status_aktif_num'] == 0,
        SCORE_NON_AKTIF,
        0.0
    )

    # ─── 2. Cek Spatiotemporal (Impossible Travel) ────────────
    # Pastikan kolom tidak None (antisipasi data kotor)
    jarak = pd.to_numeric(df['jarak_km'], errors='coerce').fillna(0)
    waktu = pd.to_numeric(df['waktu_selisih_jam'], errors='coerce').fillna(0)
    
    # Deteksi Darurat / RSUD / RS Tipe A (Zero Disruption)
    # Pakai .fillna('') agar aman kalau kolom kosong
    jenis = df.get('jenis_kunjungan', pd.Series([''] * len(df))).fillna('').astype(str).str.lower()
    faskes = df.get('faskes_tujuan', pd.Series([''] * len(df))).fillna('').astype(str).str.upper()
    
    # Boolean mask: True jika masuk kategori darurat
    is_emergency = (
        jenis.str.contains(EMERGENCY_VISIT_TYPE, na=False) |
        faskes.apply(lambda x: any(kw.upper() in x for kw in EMERGENCY_KEYWORDS))
    )
    
    # Cek anomali mustahil
    anomaly_mask = (
        (jarak >= IMPOSSIBLE_TRAVEL_KM) & 
        (waktu <= IMPOSSIBLE_TRAVEL_HOURS) & 
        (~is_emergency)
    )
    
    df['spatiotemporal_anomaly'] = np.where(
        anomaly_mask,
        SCORE_IMPOSSIBLE_TRAVEL,
        0.0
    )

    # ─── 3. Gabungkan Skor (Ambil yang tertinggi) ─────────────
    # Jika Non-Aktif (50) DAN Impossible Travel (60), ambil 60.
    df['skor_rules'] = np.maximum(df['skor_rules'], df['spatiotemporal_anomaly'])

    log.info(f"Rule engine: {len(df)} klaim diproses, "
             f"{(df['skor_rules'] > 0).sum()} terindikasi anomali.")
    
    return df


# ═══════════════════════════════════════════════════════════════
# SELF-TEST (jalankan: python -m core.rule_engine)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  ⚖️  RULE ENGINE LAYER SELF-TEST")
    print("=" * 60)

    # Buat data dummy untuk menguji 4 skenario
    dummy_data = [
        # 1. Normal (harus skor 0)
        {"id_klaim": "K-1", "status_kartu": "Aktif", "jarak_km": 10, "waktu_selisih_jam": 5, "jenis_kunjungan": "Rutin", "faskes_tujuan": "Klinik"},
        # 2. Non-Aktif (harus skor 50)
        {"id_klaim": "K-2", "status_kartu": "Non-Aktif", "jarak_km": 10, "waktu_selisih_jam": 5, "jenis_kunjungan": "Rutin", "faskes_tujuan": "Klinik"},
        # 3. Impossible Travel (harus skor 60)
        {"id_klaim": "K-3", "status_kartu": "Aktif", "jarak_km": 850, "waktu_selisih_jam": 1.5, "jenis_kunjungan": "Rutin", "faskes_tujuan": "Klinik"},
        # 4. Impossible Travel TAPI Darurat (harus skor 0 - dikecualikan)
        {"id_klaim": "K-4", "status_kartu": "Aktif", "jarak_km": 1200, "waktu_selisih_jam": 2.0, "jenis_kunjungan": "Rujukan Darurat", "faskes_tujuan": "RSUPN Cipto"},
    ]
    
    df_test = pd.DataFrame(dummy_data)
    df_result = apply_rule_engine(df_test)

    print("\nHasil Pengujian:")
    print("-" * 60)
    for _, row in df_result.iterrows():
        print(f"[{row['id_klaim']}] Skor: {row['skor_rules']:>4.1f} | "
              f"Status: {row['status_kartu']:<10} | "
              f"Jarak: {row['jarak_km']:>4}km / {row['waktu_selisih_jam']}jam | "
              f"Darurat: {row['jenis_kunjungan']}")
    
    print("-" * 60)
    # Verifikasi ekspektasi
    assert df_result.loc[0, 'skor_rules'] == 0.0, "K-1 harus 0"
    assert df_result.loc[1, 'skor_rules'] == 50.0, "K-2 harus 50"
    assert df_result.loc[2, 'skor_rules'] == 60.0, "K-3 harus 60"
    assert df_result.loc[3, 'skor_rules'] == 0.0, "K-4 harus 0 (darurat)"
    
    print("\n[✓] Rule Engine LULUS SEMUA TES!")
    print("=" * 60)