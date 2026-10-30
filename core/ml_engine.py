"""
SIGAP v6.2 — Layer 3: Hybrid ML Ensemble
=========================================
XGBoost (Supervised) + Isolation Forest (Unsupervised).
100% CPU-only untuk menghemat RAM dan menghindari crash GPU.

Formula Ensemble:
ml_weighted = (0.7 * skor_ml) + (0.3 * skor_iforest)
"""
import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.ensemble import IsolationForest
import joblib
from config import (
    MODELS_DIR, XGB_PARAMS, IFOREST_PARAMS, ML_FEATURES,
    WEIGHT_XGBOOST, WEIGHT_IFOREST, ML_MAX_SCORE
)
from utils.logger import log

XGB_MODEL_PATH = MODELS_DIR / "model_xgb_v6.pkl"
IFOREST_MODEL_PATH = MODELS_DIR / "model_iforest_v6.pkl"

def train_initial_models(df_all: pd.DataFrame):
    """Melatih model awal dari data historis jika .pkl belum ada."""
    log.info("Memulai Initial Training (XGBoost + Isolation Forest)...")
    
    # Siapkan fitur
    df = df_all.copy()
    df['status_aktif_num'] = df['status_kartu'].apply(lambda x: 1 if str(x).lower() == 'aktif' else 0)
    
    # Buat Pseudo-Label (Belajar dari Rule-Based + sedikit noise)
    # Ini trik agar model tidak menghafal 100% rule, tapi belajar polanya
    np.random.seed(42)
    noise = np.random.choice([0, 1], size=len(df), p=[0.95, 0.05])
    rule_label = (
        (df['status_aktif_num'] == 0) | 
        ((df['jarak_km'] >= 300) & (df['waktu_selisih_jam'] <= 3))
    ).astype(int)
    y_train = np.logical_or(rule_label, noise).astype(int)
    
    X_train = df[ML_FEATURES].fillna(0)
    
    # 1. Train XGBoost (CPU Only)
    model_xgb = xgb.XGBClassifier(**XGB_PARAMS)
    model_xgb.fit(X_train, y_train)
    joblib.dump(model_xgb, XGB_MODEL_PATH)
    log.info(f"✓ XGBoost disimpan di {XGB_MODEL_PATH.name}")
    
    # 2. Train Isolation Forest (CPU Only)
    model_iforest = IsolationForest(**IFOREST_PARAMS)
    model_iforest.fit(X_train)
    joblib.dump(model_iforest, IFOREST_MODEL_PATH)
    log.info(f"✓ Isolation Forest disimpan di {IFOREST_MODEL_PATH.name}")
    
    return model_xgb, model_iforest

def apply_ml_engine(df_delta: pd.DataFrame, df_all: pd.DataFrame = None) -> pd.DataFrame:
    """
    Terapkan Layer 3 (ML Ensemble) ke DataFrame delta.
    """
    if len(df_delta) == 0:
        return df_delta

    df_delta = df_delta.copy()
    
    # ─── 1. Load atau Train Model ─────────────────────────────
    if XGB_MODEL_PATH.exists() and IFOREST_MODEL_PATH.exists():
        model_xgb = joblib.load(XGB_MODEL_PATH)
        model_iforest = joblib.load(IFOREST_MODEL_PATH)
    else:
        if df_all is None or len(df_all) == 0:
            log.warning("ML Engine: Data historis kosong, melatih model dengan data delta saja.")
            df_all = df_delta
            
        # Pastikan kolom status_aktif_num ada sebelum training
        if 'status_aktif_num' not in df_all.columns:
            df_all['status_aktif_num'] = df_all['status_kartu'].apply(lambda x: 1 if str(x).lower() == 'aktif' else 0)
            
        model_xgb, model_iforest = train_initial_models(df_all)

    # ─── 2. Siapkan Fitur ─────────────────────────────────────
    # Pastikan kolom status_aktif_num ada di data delta
    if 'status_aktif_num' not in df_delta.columns:
        df_delta['status_aktif_num'] = df_delta['status_kartu'].apply(lambda x: 1 if str(x).lower() == 'aktif' else 0)
        
    X_delta = df_delta[ML_FEATURES].fillna(0)

    # ─── 3. Prediksi XGBoost (0.0 - 70.0) ─────────────────────
    probs = model_xgb.predict_proba(X_delta)[:, 1]
    df_delta['skor_ml'] = probs * ML_MAX_SCORE

    # ─── 4. Prediksi Isolation Forest (0.0 - 70.0) ────────────
    # IForest mengembalikan nilai negatif untuk anomali, positif untuk normal.
    # Kita balik pakai Sigmoid agar anomali dapat skor tinggi.
    raw_scores = model_iforest.decision_function(X_delta)
    sigmoid_inverted = 1.0 / (1.0 + np.exp(raw_scores * 10.0))
    df_delta['skor_iforest'] = sigmoid_inverted * ML_MAX_SCORE

    # ─── 5. Ensemble Formula ──────────────────────────────────
    df_delta['ml_weighted'] = (
        (WEIGHT_XGBOOST * df_delta['skor_ml']) + 
        (WEIGHT_IFOREST * df_delta['skor_iforest'])
    )

    log.info(f"ML Engine: {len(df_delta)} klaim dievaluasi. "
             f"Rata-rata skor ML: {df_delta['skor_ml'].mean():.2f}")
    
    return df_delta


# ═══════════════════════════════════════════════════════════════
# SELF-TEST (jalankan: python -m core.ml_engine)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  🤖 ML ENGINE (XGBOOST + IFOREST) SELF-TEST")
    print("=" * 60)

    # Hapus model lama agar test benar-benar melakukan training baru
    if XGB_MODEL_PATH.exists(): XGB_MODEL_PATH.unlink()
    if IFOREST_MODEL_PATH.exists(): IFOREST_MODEL_PATH.unlink()

    # Buat data dummy 100 baris
    np.random.seed(42)
    dummy_data = []
    for i in range(100):
        is_fraud = (i % 10 == 0) # 10% fraud
        data = {
            "id_klaim": f"K-{i}",
            "status_kartu": "Non-Aktif" if is_fraud and i % 20 == 0 else "Aktif",
            "jarak_km": 850 if is_fraud and i % 30 == 0 else np.random.uniform(1, 50),
            "waktu_selisih_jam": 1.5 if is_fraud and i % 30 == 0 else np.random.uniform(5, 48),
            "biaya_juta": 150.5 if is_fraud and i % 40 == 0 else np.random.uniform(0.5, 7.0),
        }
        dummy_data.append(data)
    
    df_test = pd.DataFrame(dummy_data)
    
    print("\n[1] Melakukan Initial Training dari 100 data historis...")
    # df_all dan df_delta kita samakan untuk simulasi awal
    df_result = apply_ml_engine(df_test, df_all=df_test)
    
    print("\n[2] Hasil Prediksi (Top 5 Fraud):")
    print("-" * 60)
    top_fraud = df_result.sort_values('ml_weighted', ascending=False).head(5)
    for _, row in top_fraud.iterrows():
        print(f"[{row['id_klaim']}] Skor ML: {row['skor_ml']:.2f} | "
              f"IForest: {row['skor_iforest']:.2f} | "
              f"Total: {row['ml_weighted']:.2f} | "
              f"(Jarak: {row['jarak_km']:.0f}km, Biaya: {row['biaya_juta']:.0f}jt)")
    
    print("-" * 60)
    # Cek apakah model .pkl berhasil dibuat
    assert XGB_MODEL_PATH.exists(), "Model XGBoost gagal dibuat"
    assert IFOREST_MODEL_PATH.exists(), "Model IForest gagal dibuat"
    
    print("\n[✓] ML Engine LULUS SEMUA TES!")
    print("=" * 60)