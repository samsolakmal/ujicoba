"""
SIGAP v6.2 — Ingestion Pipeline
================================
Simulasi penerimaan data dari Faskes (PPT Hal 4).
- Generate 50 klaim sintetis (100% Synthetic Data - PPT Hal 7)
- Inject 5 skenario fraud untuk demo
- Hashing NIK (UU PDP) sebelum masuk DB
- Simpan dengan status PENDING
"""
import random
import pandas as pd
from datetime import datetime
from config import (
    Status, DEMO_CLAIMS_PER_BATCH, DEMO_SYNDICATE_HP,
    SCORE_NON_AKTIF
)
from core.database import transaction
from core.hashing import hash_nik
from utils.logger import log

def generate_dummy_claims(n: int = DEMO_CLAIMS_PER_BATCH) -> list:
    """Generate klaim sintetis dengan 5 skenario fraud."""
    claims = []
    
    # Ambil ID terakhir dari DB untuk penomoran berlanjut
    with transaction(retry=False) as conn:
        res = conn.execute("SELECT COALESCE(MAX(CAST(SUBSTR(id_klaim, 7) AS INTEGER)), 10000) FROM tbl_klaim_mentah").fetchone()
        max_id = res[0] if res else 10000

    for i in range(1, n + 1):
        next_id = max_id + i
        id_klaim = f"KLAIM-{next_id}"
        
        # Default data (Normal)
        nik_mentah = f"32750821{random.randint(10000000, 99999999)}"
        nama_pasien = f"Pasien_Sintetis_{next_id}"
        no_hp = f"0813{random.randint(10000000, 99999999)}"
        status_kartu = "Aktif"
        jarak_km = round(random.uniform(1.0, 30.0), 2)
        waktu_selisih_jam = round(random.uniform(5.0, 48.0), 2)
        biaya_juta = round(random.uniform(0.5, 7.0), 2)
        lat_faskes = round(random.uniform(-6.3, -6.1), 6)
        lng_faskes = round(random.uniform(106.7, 106.9), 6)
        jenis_kunjungan = "Rutin"
        faskes_tujuan = "Klinik Pratama"
        poli_tujuan = "Poli Umum"

        # ─── INJEKSI SKENARIO FRAUD (Untuk Demo) ───
        if i == 10:
            status_kartu = "Non-Aktif" # Skenario 1: Rule Engine
        elif i == 20:
            jarak_km = 850.0 # Skenario 2: Impossible Travel
            waktu_selisih_jam = 1.5
        elif i in [30, 31, 32, 33, 34]:
            no_hp = DEMO_SYNDICATE_HP # Skenario 3: Graph Sindikat (5 NIK 1 HP)
        elif i == 40:
            jarak_km = 1200.0 # Skenario 4: Darurat Lintas Provinsi (Harus lolos)
            waktu_selisih_jam = 2.0
            jenis_kunjungan = "Rujukan Darurat"
            faskes_tujuan = "RSUPN Cipto Mangunkusumo"
        elif i == 45:
            biaya_juta = 150.5 # Skenario 5: Anomali Biaya Ekstrem (IForest)

        claims.append({
            'id_klaim': id_klaim,
            'nik_mentah': nik_mentah,
            'nama_pasien': nama_pasien,
            'no_hp': no_hp,
            'status_kartu': status_kartu,
            'jarak_km': jarak_km,
            'waktu_selisih_jam': waktu_selisih_jam,
            'biaya_juta': biaya_juta,
            'lat_faskes': lat_faskes,
            'lng_faskes': lng_faskes,
            'jenis_kunjungan': jenis_kunjungan,
            'faskes_tujuan': faskes_tujuan,
            'poli_tujuan': poli_tujuan,
        })
        
    return claims

def save_to_database(claims: list) -> int:
    """Simpan klaim ke DB dengan Atomic Transaction."""
    if not claims:
        return 0
        
    inserted = 0
    with transaction() as conn:
        for c in claims:
            # 1. Simpan ke Brankas (Identitas Mentah)
            conn.execute("""
                INSERT OR IGNORE INTO tbl_identitas_pemohon 
                (id_klaim, nik_mentah, nama_pasien) 
                VALUES (?, ?, ?)
            """, (c['id_klaim'], c['nik_mentah'], c['nama_pasien']))
            
            # 2. Hashing NIK (UU PDP)
            nik_hash = hash_nik(c['nik_mentah'])
            
            # 3. Simpan ke Klaim Mentah (Analytics) dengan Status PENDING
            conn.execute("""
                INSERT OR IGNORE INTO tbl_klaim_mentah 
                (id_klaim, nik_hash, no_hp, status_kartu, jarak_km, 
                 waktu_selisih_jam, biaya_juta, lat_faskes, lng_faskes, 
                 jenis_kunjungan, faskes_tujuan, poli_tujuan, status_analisis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c['id_klaim'], nik_hash, c['no_hp'], c['status_kartu'], 
                c['jarak_km'], c['waktu_selisih_jam'], c['biaya_juta'], 
                c['lat_faskes'], c['lng_faskes'], c['jenis_kunjungan'], 
                c['faskes_tujuan'], c['poli_tujuan'], Status.PENDING
            ))
            inserted += 1
            
    return inserted

def run_ingestion() -> int:
    """Fungsi utama untuk dipanggil oleh orchestrator."""
    log.info("Memulai proses Ingestion (Simulasi Faskes)...")
    claims = generate_dummy_claims()
    total = save_to_database(claims)
    log.info(f"Ingestion selesai. {total} klaim baru masuk ke antrean (PENDING).")
    return total

# ═══════════════════════════════════════════════════════════════
# SELF-TEST (jalankan: python -m pipelines.ingest)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from core.database import init_schema, get_stats
    
    print("=" * 60)
    print("  📥 INGESTION PIPELINE SELF-TEST")
    print("=" * 60)
    
    # Pastikan tabel siap
    init_schema()
    
    print(f"\n[1] State Awal:")
    stats_before = get_stats()
    print(f"    Total klaim di DB: {stats_before['total_klaim']}")
    
    print(f"\n[2] Menjalankan Ingestion (50 Klaim)...")
    total_inserted = run_ingestion()
    print(f"    Berhasil insert: {total_inserted} klaim.")
    
    print(f"\n[3] State Akhir:")
    stats_after = get_stats()
    print(f"    Total klaim di DB: {stats_after['total_klaim']}")
    print(f"    Status antrean  : {stats_after['by_status']}")
    
    # Verifikasi
    assert total_inserted == 50, "Harus insert 50 klaim"
    assert stats_after['by_status'].get('PENDING') == 50, "Semua harus PENDING"
    
    # Cek apakah NIK berhasil di-hash (tidak ada NIK asli di tbl_klaim_mentah)
    with transaction(retry=False) as conn:
        sample = conn.execute("SELECT nik_hash, no_hp FROM tbl_klaim_mentah LIMIT 1").fetchone()
        print(f"\n[4] Sample Data (Anonimisasi):")
        print(f"    NIK Hash : {sample['nik_hash']} (harus 16 char)")
        print(f"    No. HP   : {sample['no_hp']}")
        assert len(sample['nik_hash']) == 16, "Hash harus 16 char"
    
    print("\n[✓] Ingestion Pipeline LULUS SEMUA TES!")
    print("=" * 60)