# 🛡️ SIGAP v6.2 — Sistem Integritas & Gerak Cepat Anti-Fraud
> **Healthkathon Finalist Edition — BPJS Kesehatan (JKN)**  
> *Sistem Deteksi Fraud Klaim Kesehatan Berbasis Silent Post-Audit Screening & Hybrid Intelligence*

---

## 📌 Ringkasan Proyek

**SIGAP (Sistem Integritas & Gerak Cepat Anti-Fraud)** adalah sistem deteksi dan pencegahan fraud klaim layanan kesehatan BPJS yang dirancang dengan prinsip:
1. **Zero Disruption to Faskes**: Bekerja secara asinkron (*Silent Post-Audit Screening*) tanpa mengganggu antrean pelayanan pasien di faskes.
2. **Kepatuhan Penuh UU PDP**: Pemisahan identitas pemohon dan NIK dienkripsi secara satu arah menggunakan **Salted SHA-256**. Log otomatis disanitasi dari PII.
3. **Hybrid Multi-Layer Intelligence**: Mengintegrasikan:
   - **Layer 1: Rule Engine** (Validasi status kepesertaan & spatiotemporal *impossible travel*)
   - **Layer 2: Graph Network Engine** (Deteksi sindikat relasi NIK-HP abnormal)
   - **Layer 3: Machine Learning Ensemble** (XGBoost Supervised + Isolation Forest Unsupervised)
   - **Layer 4: Explainable AI (XAI)** (Penjelasan naratif otomatis 4-Tier dengan Pydantic Guard)

Dokumentasi arsitektur dan teknis lengkap dapat dilihat di [docs/PENJELASAN_PROJEK_SIGAP.md](docs/PENJELASAN_PROJEK_SIGAP.md).

---

## 🚀 Quick Start

### 1. Prasyarat & Instalasi
Pastikan Python 3.10+ telah terpasang.

```bash
# Clone repository
git clone https://github.com/samsolakmal/ujicoba.git
cd ujicoba

# Buat virtual environment (opsional namun disarankan)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# atau
.venv\Scripts\activate     # Windows

# Install dependensi
pip install -r requirements.txt
```

### 2. Konfigurasi Lingkungan
Salin file template `.env.example` menjadi `.env`:
```bash
cp .env.example .env
```

### 3. Menjalankan Demo / Dashboard
Jalankan script otomatis demo (akan otomatis membuka dashboard Streamlit):
```bash
python run_demo.py
```
Atau langsung jalankan Streamlit:
```bash
streamlit run dashboard/app.py
```

---

## 📂 Struktur Repositori

```text
├── core/             # Engine inti (database SQLite WAL, hashing, rule, graph, ML, ensemble, XAI)
├── dashboard/        # Antarmuka verifikator BPJS berbasis Streamlit
├── data/             # Database lokal (SQLite)
├── docs/             # Dokumentasi teknis & panduan lengkap arsitektur
├── models/           # Binary model ML (otomatis digenerate jika belum ada)
├── pipelines/        # Pipeline ingest data sintetis & analisis batch
├── scripts/          # Skrip pembantu (reset demo data, dsb.)
├── tests/            # Automated unit testing
├── utils/            # Helper utilitas & secure logger (PII Sanitizer)
├── config.py         # Konfigurasi terpusat
├── run_demo.py       # Script one-click launcher
└── requirements.txt  # Dependensi Python
```
