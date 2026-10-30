"""
SIGAP v6.2 — Ensemble & Classification
=======================================
Menggabungkan skor dari 3 layer:
total_skor = max(skor_rules, skor_graph, ml_weighted)

Lalu melakukan klasifikasi 3-Tier:
- >= 60 : DITAHAN (FRAUD)
- >= 35 : REVIEW RINGAN
- < 35  : LOLOS (AMAN)
"""
import pandas as pd
import numpy as np
from config import (
    TIER_FRAUD_THRESHOLD, 
    TIER_REVIEW_THRESHOLD, 
    Tier
)
from utils.logger import log

def klasifikasi_3tier(skor: float) -> str:
    """Menentukan keputusan berdasarkan skor 0-100."""
    if skor >= TIER_FRAUD_THRESHOLD:
        return Tier.FRAUD
    elif skor >= TIER_REVIEW_THRESHOLD:
        return Tier.REVIEW
    else:
        return Tier.SAFE

def apply_ensemble(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gabungkan skor Rules, Graph, dan ML Weighted.
    Tambahkan kolom 'total_skor' dan 'keputusan'.
    """
    if len(df) == 0:
        return df

    df = df.copy()

    # ─── 1. Pastikan semua kolom skor ada ─────────────────────
    for col in ['skor_rules', 'skor_graph', 'ml_weighted']:
        if col not in df.columns:
            df[col] = 0.0
            
    # Ganti NaN dengan 0.0 (antisipasi data kosong)
    df[['skor_rules', 'skor_graph', 'ml_weighted']] = (
        df[['skor_rules', 'skor_graph', 'ml_weighted']].fillna(0.0)
    )

    # ─── 2. Formula Ensemble: Ambil Nilai MAX ─────────────────
    # Jika Rules 50, Graph 60, ML 40 -> Ambil 60.
    # Kita pakai np.maximum.reduce untuk efisiensi maksimal.
    df['total_skor'] = np.maximum.reduce([
        df['skor_rules'].values,
        df['skor_graph'].values,
        df['ml_weighted'].values
    ])
    
    # Bulatkan 2 desimal agar rapi di database
    df['total_skor'] = df['total_skor'].round(2)

    # ─── 3. Klasifikasi 3-Tier ────────────────────────────────
    df['keputusan'] = df['total_skor'].apply(klasifikasi_3tier)

    # ─── 4. Logging ───────────────────────────────────────────
    merah = (df['keputusan'] == Tier.FRAUD).sum()
    kuning = (df['keputusan'] == Tier.REVIEW).sum()
    hijau = (df['keputusan'] == Tier.SAFE).sum()
    
    log.info(f"Ensemble: {len(df)} klaim diproses -> "
             f"🔴 {merah} Merah | 🟡 {kuning} Kuning | 🟢 {hijau} Hijau")

    return df


# ═══════════════════════════════════════════════════════════════
# SELF-TEST (jalankan: python -m core.ensemble)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  ⚖️  ENSEMBLE & CLASSIFICATION SELF-TEST")
    print("=" * 60)

    # Dummy data untuk menguji formula max dan 3-tier
    dummy_data = [
        # 1. Rules menang (50), sisanya 0 -> Harus Kuning (50)
        {"id_klaim": "K-1", "skor_rules": 50.0, "skor_graph": 0.0, "ml_weighted": 10.0},
        # 2. Graph menang (60), ML tinggi (55) -> Harus Merah (60)
        {"id_klaim": "K-2", "skor_rules": 0.0, "skor_graph": 60.0, "ml_weighted": 55.0},
        # 3. ML menang (68), sisanya 0 -> Harus Merah (68)
        {"id_klaim": "K-3", "skor_rules": 0.0, "skor_graph": 0.0, "ml_weighted": 68.0},
        # 4. Semua rendah -> Harus Hijau (20)
        {"id_klaim": "K-4", "skor_rules": 0.0, "skor_graph": 0.0, "ml_weighted": 20.0},
        # 5. Edge case: Rules 35 (pas di batas kuning) -> Harus Kuning
        {"id_klaim": "K-5", "skor_rules": 35.0, "skor_graph": 0.0, "ml_weighted": 0.0},
    ]
    
    df_test = pd.DataFrame(dummy_data)
    df_result = apply_ensemble(df_test)

    print("\nHasil Pengujian:")
    print("-" * 60)
    print(f"{'ID':<5} | {'Rules':<6} | {'Graph':<6} | {'ML':<6} | {'Total':<6} | {'Keputusan'}")
    print("-" * 60)
    for _, row in df_result.iterrows():
        print(f"{row['id_klaim']:<5} | {row['skor_rules']:<6.1f} | {row['skor_graph']:<6.1f} | "
              f"{row['ml_weighted']:<6.1f} | {row['total_skor']:<6.1f} | {row['keputusan']}")
    
    print("-" * 60)
    # Verifikasi Ekspektasi
    assert df_result.loc[0, 'keputusan'] == Tier.REVIEW, "K-1 harus REVIEW"
    assert df_result.loc[1, 'keputusan'] == Tier.FRAUD, "K-2 harus FRAUD"
    assert df_result.loc[2, 'total_skor'] == 68.0, "K-3 total harus 68.0"
    assert df_result.loc[3, 'keputusan'] == Tier.SAFE, "K-4 harus SAFE"
    assert df_result.loc[4, 'keputusan'] == Tier.REVIEW, "K-5 harus REVIEW (batas bawah)"

    print("\n[✓] Ensemble Layer LULUS SEMUA TES!")
    print("=" * 60)