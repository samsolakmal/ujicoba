# 🛡️ PANDUAN LENGKAP & DOKUMENTASI ARSITEKTUR SISTEM SIGAP v6.2
**Sistem Integritas & Gerak Cepat Anti-Fraud — BPJS Kesehatan (JKN)**  
*Healthkathon Finalist Edition*

---

## 📌 1. Ringkasan Eksekutif & Filosofi Proyek

Proyek ini bernama **SIGAP (Sistem Integritas & Gerak Cepat Anti-Fraud) versi 6.2**. Sistem ini dirancang khusus untuk memecahkan dilema fraud audit pada ekosistem JKN (Jaminan Kesehatan Nasional) BPJS Kesehatan:

1. **Zero Disruption to Faskes (Tanpa Mengganggu Pelayanan):**
   * Pemeriksaan klaim dilakukan secara **Silent Post-Audit Screening** (asinkron).
   * Faskes dan pasien tidak mengalami penundaan layanan di loket pendaftaran/pelayanan. Sistem bekerja di latar belakang setelah klaim diajukan.
2. **Kepatuhan Penuh Terhadap UU Perlindungan Data Pribadi (UU PDP):**
   * Data identitas sensitif (NIK mentah dan Nama) langsung dipisahkan ke dalam brankas tersendiri (`tbl_identitas_pemohon`).
   * Engine analisis, ML, graf, dan log audit **hanya** menggunakan NIK yang telah dienkripsi secara satu arah menggunakan **Salted SHA-256** (16 karakter heksadesimal).
   * Seluruh log aplikasi dilengkapi penyaring otomatis (*PII Sanitizer*) agar nomor HP dan NIK tidak pernah bocor ke file log teks biasa.
3. **Hybrid Multi-Layer Intelligence:**
   * Menggabungkan ketegasan **Rule Engine**, kepekaan spasial **Spatiotemporal**, kecerdasan jaringan **Graph Network**, kekuatan prediksi **Machine Learning Ensemble**, dan keterbukaan pertanggungjawaban **Explainable AI (XAI)**.

---

## 🗂️ 2. Struktur Direktori Lengkap Proyek

Berikut adalah peta struktur seluruh folder dan file di dalam proyek:

```text
healtkathon finalis/
├── .env                       <- Variabel lingkungan (Salt enkripsi NIK & flag Demo)
├── .gitignore                 <- Mengabaikan file temporary, .venv, log, dan cache
├── requirements.txt           <- Daftar dependensi Python resmi (pinned version)
├── run_demo.py                <- Script peluncur demo satu klik (buka browser & Streamlit)
├── config.py                  <- Pusat kendali konfigurasi (Zero Hardcoding)
│
├── core/                      <- Inti mesin komputasi, algoritma, dan database
│   ├── __init__.py            <- Marker modul Python
│   ├── database.py            <- Database Access Object (DAO) SQLite WAL, isolasi & retry
│   ├── hashing.py             <- Mesin anonimisasi NIK (Salted SHA-256 UU PDP)
│   ├── rule_engine.py         <- Layer 1: Deteksi status kartu & Impossible Travel
│   ├── graph_engine.py        <- Layer 2: Deteksi sindikat klaim via relasi NIK-HP
│   ├── ml_engine.py           <- Layer 3: Hybrid ML (XGBoost + Isolation Forest)
│   ├── ensemble.py            <- Agregasi skor akhir & klasifikasi 3-Tier (Fraud/Review/Safe)
│   └── xai_narrator.py        <- Explainable AI 4-Tier Cascade dengan Pydantic Guard
│
├── pipelines/                 <- Alur kerja data (ETL & Eksekusi Batch)
│   ├── __init__.py            <- Marker modul Python
│   ├── ingest.py              <- Simulator penerimaan klaim dari faskes (50 data sintetis)
│   └── analyze.py             <- Orkestrator analisis antrean PENDING -> PROCESSED
│
├── dashboard/                 <- Antarmuka pengguna (Frontend Streamlit)
│   ├── __init__.py            <- Marker modul Python
│   ├── app.py                 <- Web Dashboard utama verifikator BPJS
│   └── pages/                 <- Folder untuk multi-page Streamlit (tersedia untuk ekspansi)
│
├── models/                    <- Penyimpanan binary model ML yang sudah dilatih
│   ├── model_xgb_v6.pkl       <- Model XGBoost Classifier (Supervised)
│   └── model_iforest_v6.pkl   <- Model Isolation Forest (Unsupervised)
│
├── data/                      <- Penyimpanan basis data lokal
│   └── sigap_v6.db            <- Database SQLite tempat menyimpan seluruh tabel & riwayat klaim
│
├── scripts/                   <- Script utilitas dan pemeliharaan
│   └── reset_demo.py          <- Script untuk membersihkan database dan model saat demo baru
│
├── utils/                     <- Utilitas pendukung sistem
│   ├── __init__.py            <- Marker modul Python
│   └── logger.py              <- Logger terpusat dengan filter PII Sanitizer otomatis
│
├── logs/                      <- Log aktivitas operasional sistem
│   └── sigap.log              <- Catatan log eksekusi, peringatan, dan audit trail
│
├── docs/                      <- Dokumentasi resmi teknis proyek
│   └── PENJELASAN_PROJEK_SIGAP.md <- File dokumentasi ini
│
└── tests/                     <- Folder pengujian sistem / unit test
```

---

## 🔍 3. Bedah Rinci Setiap File & Folder

### ⚙️ Root Files (Akar Proyek)
1. **`config.py`**
   * **Kegunaan:** Menjadi *Single Source of Truth*. Seluruh angka penting (*magic numbers*), batasan ambang (*threshold*), bobot algoritma, parameter model ML, dan konfigurasi path diatur di sini. Tidak ada *hardcode* di file lain.
   * **Isi Penting:**
     * `TIER_FRAUD_THRESHOLD = 60.0` (Skor $\ge 60$ ditahan/fraud).
     * `TIER_REVIEW_THRESHOLD = 35.0` (Skor $35 - 59.9$ review ringan, $<35$ aman).
     * `IMPOSSIBLE_TRAVEL_KM = 300.0` dan `IMPOSSIBLE_TRAVEL_HOURS = 3.0`.
     * `GRAPH_SYNDICATE_THRESHOLD = 15` (1 no. HP terhubung ke $>15$ NIK).
     * `WEIGHT_XGBOOST = 0.7` dan `WEIGHT_IFOREST = 0.3`.
     * Fungsi `validate_config()` untuk memeriksa kesiapan setting saat aplikasi dinyalakan (*fail-fast*).
2. **`.env`**
   * **Kegunaan:** Menyimpan konfigurasi rahasia lingkungan yang tidak boleh di-*hardcode* ke publik.
   * **Isi:** Berisi `SIGAP_SALT` untuk garam enkripsi NIK dan `SIGAP_DEMO_MODE=true`.
3. **`requirements.txt`**
   * **Kegunaan:** Menjamin kompatibilitas dependensi. Berisi pustaka inti yang sudah dikunci versinya (*pinned*): `pandas==2.2.2`, `numpy==1.26.4`, `networkx==3.3`, `xgboost==2.1.1`, `scikit-learn==1.5.1`, `pydantic==2.8.2`, `joblib==1.4.2`, `python-dotenv==1.0.1`, `streamlit==1.38.0`.
4. **`run_demo.py`**
   * **Kegunaan:** *Launcher* presentasi satu kali klik. Script ini secara otomatis memberi jeda 2 detik, membuka peramban web (*browser*) ke alamat `http://localhost:8501`, dan mengeksekusi perintah Streamlit untuk menjalankan `dashboard/app.py`.

---

### 🧠 Folder `core/` (Mesin Algoritma & Logika Bisnis)
1. **`core/database.py`**
   * **Kegunaan:** Lapisan akses data (*Database Access Object*). Semua interaksi kueri baca/tulis SQLite diwajibkan melewati modul ini.
   * **Fitur Utama:**
     * **Mode WAL (Write-Ahead Logging):** Mencegah *database locked* saat aplikasi membaca dan menulis secara simultan.
     * **Atomic Transaction & Auto-Retry:** Membungkus transaksi dengan *context manager* (`with transaction():`). Jika database terkunci sesaat, sistem mencoba ulang otomatis hingga 3 kali.
     * **Zombie Processing Recovery:** Mendeteksi klaim yang menggantung di status `PROCESSING` lebih dari 5 menit akibat kendala sistem, lalu otomatis mengubahnya menjadi `FAILED` untuk diproses ulang.
     * **4 Tabel Utama:**
       1. `tbl_identitas_pemohon`: Menyimpan NIK asli dan nama (terisolasi).
       2. `tbl_klaim_mentah`: Menyimpan NIK hash, jarak tempuh, biaya, jenis poli, dan status antrean (`PENDING`, `PROCESSING`, `PROCESSED`, `FAILED`, `VERIFIED`).
       3. `tbl_hasil_risiko`: Menyimpan kalkulasi skor tiap layer, skor total, keputusan tier, dan teks XAI.
       4. `tbl_feedback_verifikator`: Menyimpan keputusan akhir verifikator (*Human-in-the-Loop*).
2. **`core/hashing.py`**
   * **Kegunaan:** Menjalankan amanat UU PDP. Mengubah NIK 16 digit menjadi heksadesimal 16 karakter yang deterministik dan tidak dapat dibalik (*irreversible*).
   * **Cara Kerja:** `hashlib.sha256(f"{SIGAP_SALT}{nik}".encode()).hexdigest()[:16]`.
3. **`core/rule_engine.py` (Layer 1)**
   * **Kegunaan:** Deteksi pelanggaran aturan deterministik:
     * **Pelanggaran Kartu:** Jika status kartu peserta "Non-Aktif", langsung diberi penalti skor **+50**.
     * **Impossible Travel (Spatiotemporal):** Jika jarak antar faskes $\ge 300\text{ km}$ dalam selisih waktu $\le 3\text{ jam}$, diberi penalti skor **+60**.
     * **Pengecualian Medis Darurat (*Zero False Alarm*):** Jika jenis kunjungan adalah "Rujukan Darurat" atau faskes tujuan berstatus RSUD / RSCM / RS Tipe A, maka indikasi *impossible travel* diabaikan (**skor 0**), karena pasien rujukan gawat darurat antar-provinsi via transportasi cepat merupakan kebutuhan medis nyata.
4. **`core/graph_engine.py` (Layer 2)**
   * **Kegunaan:** Deteksi sindikat percaloan / mafia klaim menggunakan analisis graf jejaring sosial (*Social Network Analysis*).
   * **Pustaka:** `networkx.Graph()`.
   * **Cara Kerja:** Membentuk hubungan antara simpul *NIK Hash* dengan simpul *Nomor HP*. Jika ada satu nomor HP yang dihubungkan oleh lebih dari 15 NIK yang berbeda (`degree > 15`), sistem mengidentifikasi nomor tersebut sebagai sindikat dan memberikan penalti skor **+60**.
5. **`core/ml_engine.py` (Layer 3)**
   * **Kegunaan:** Mesin pembelajaran mesin *hybrid* untuk mendeteksi anomali pola transaksi yang halus dan tidak tertangkap aturan kaku.
   * **Model yang Digunakan:**
     * **XGBoost Classifier (Supervised):** Mempelajari pola riwayat klaim historis berisiko.
     * **Isolation Forest (Unsupervised):** Mendeteksi pencilan (*outliers*) multivariat pada kombinasi biaya, jarak tempuh, dan waktu tanpa butuh label awal.
6. **`core/ensemble.py`**
   * **Kegunaan:** Mengombinasikan hasil ketiga lapisan menjadi skor tunggal $0 - 100$.
   * **Formula Utama:**
     $$\text{Total Skor} = \max(\text{Skor Rules}, \text{Skor Graph}, \text{Skor ML Weighted})$$
     *Di mana:*
     $$\text{Skor ML Weighted} = (0.7 \times \text{Skor XGBoost}) + (0.3 \times \text{Skor IForest})$$
   * **Klasifikasi 3-Tier:**
     * 🔴 **DITAHAN (FRAUD):** $\text{Skor} \ge 60$
     * 🟡 **REVIEW RINGAN:** $35 \le \text{Skor} < 60$
     * 🟢 **LOLOS (AMAN):** $\text{Skor} < 35$
7. **`core/xai_narrator.py`**
   * **Kegunaan:** Menghasilkan narasi alasan dalam bahasa manusia mengapa suatu klaim dicurigai, memberikan transparansi penuh kepada verifikator BPJS.
   * **Desain 4-Tier Cascade:**
     * **Tier 1 (Lokal):** Model Qwen-2.5-1.5B-Instruct lokal via PyTorch/Transformers (jika GPU/RAM memadai).
     * **Tier 2 (Cloud):** Google Gemini 1.5 Flash via API Key.
     * **Tier 3 (Template Generator):** Generator deterministik berbasis aturan teks formal bahasa Indonesia (selalu aktif, 100% cepat, anti-gagal, dan tidak butuh internet).
     * **Tier 4 (Fallback):** Pydantic Gatekeeper validation untuk menjamin format output selalu valid.

---

### 🔄 Folder `pipelines/` (Orkestrasi Alur Data)
1. **`pipelines/ingest.py`**
   * **Kegunaan:** Mensimulasikan data klaim yang masuk dari faskes (50 klaim sintetis per tarikan batch).
   * **Skenario Fraud Bawaan Demo:**
     * *Klaim #10:* Disuntik kartu Non-Aktif (Uji Rule Engine).
     * *Klaim #20:* Disuntik Jarak 850 km dalam 1.5 jam (Uji Impossible Travel).
     * *Klaim #30-34:* Disuntik nomor HP sindikat `081199998888` (Uji Graph Engine).
     * *Klaim #40:* Disuntik Jarak 1200 km dalam 2 jam TAPI Rujukan Darurat RSCM (Uji Bypass Darurat).
     * *Klaim #45:* Disuntik Biaya ekstrem Rp 150.5 Juta (Uji Isolation Forest).
2. **`pipelines/analyze.py`**
   * **Kegunaan:** Orkestrator analisis *batch*. Mengambil semua data dengan status `PENDING` atau `FAILED`, mengunci status menjadi `PROCESSING`, mengeksekusi Layer 1, Layer 2, Layer 3, Ensemble, dan XAI secara berurutan, lalu menyimpan hasil lengkapnya ke tabel `tbl_hasil_risiko` serta mengupdate status menjadi `PROCESSED`.

---

### 🖥️ Folder `dashboard/` (Antarmuka Verifikator Streamlit)
1. **`dashboard/app.py`**
   * **Kegunaan:** Dashboard berbasis web modern untuk petugas verifikator BPJS.
   * **Komponen Antarmuka:**
     * **Hero Banner & 4 Kartu KPI:** Ringkasan jumlah klaim dipindai, jumlah antrean ditahan (merah), review ringan (kuning), dan lolos otomatis (hijau).
     * **Sidebar Kontrol:** Tombol simulasi *"Tarik 50 Klaim Baru"* dan tombol *"Reset Database"*.
     * **Tab 1: Antrean Investigasi & Human-in-the-Loop (HITL):** Menampilkan daftar klaim merah & kuning. Petugas dapat membaca narasi XAI, melihat riwayat klaim, dan mengirim keputusan (Setujui, Tahan, Tolak) lengkap dengan catatan audit.
     * **Tab 2: Riwayat & Ekspor CSV:** Menampilkan tabel riwayat audit seluruh klaim dan tombol unduh laporan `.csv`.
     * **Tab 3: Cara Kerja AI (XAI):** Visualisasi diagram sebar (*Scatter Plot*) interaktif membedah pola jarak vs waktu tempuh serta garis batas anomali spatiotemporal.
     * **Tab 4: Graph Network Sindikat:** Visualisasi simpul jaringan relasi nomor HP dan NIK menggunakan NetworkX & Matplotlib (node merah menunjukkan nomor sindikat).

---

### 🛠️ Folder Pendukung Lainnya
* **`scripts/reset_demo.py`:** Utilitas pembersih untuk demonstrasi. Menghapus file database SQLite (`sigap_v6.db`, `-wal`, `-shm`) dan file bobot model `.pkl` agar presentasi dapat dimulai dari kondisi nol yang bersih.
* **`utils/logger.py`:** Pustaka *logging* yang dilengkapi ekspresi reguler (*regex*) untuk menyensor otomatis NIK (16 digit) menjadi `[NIK_REDACTED]` dan nomor ponsel menjadi `[HP_REDACTED]`.
* **`models/`:** Direktori artefak model hasil *training* serialisasi `joblib` (`model_xgb_v6.pkl` berukuran ~57 KB dan `model_iforest_v6.pkl` berukuran ~1.1 MB).
* **`data/`:** Direktori basis data SQLite (`sigap_v6.db`).
* **`logs/`:** Direktori file rekaman aktivitas runtime (`sigap.log`).

---

## 🤖 4. Bedah Model Machine Learning & Algoritma AI yang Digunakan

| Komponen AI / Algoritma | Kategori Model | Library / Modul | Peran Spesifik |
| :--- | :--- | :--- | :--- |
| **XGBoost (Extreme Gradient Boosting)** | Supervised Learning (Tree Ensemble) | `xgboost.XGBClassifier` | Memprediksi probabilitas klaim berisiko berdasarkan kombinasi fitur terstruktur (`status_aktif_num`, `jarak_km`, `waktu_selisih_jam`, `biaya_juta`). Output dikalibrasi ke rentang $0 - 70$. |
| **Isolation Forest (iForest)** | Unsupervised Learning (Anomaly Detection) | `sklearn.ensemble.IsolationForest` | Memisahkan data anomali ekstrem (misal klaim biaya tak wajar atau durasi ganjil) tanpa memerlukan label data historis. Output fungsi keputusan diinversi menggunakan kurva *Sigmoid* ke rentang $0 - 70$. |
| **Network Graph Degree Centrality** | Graph Network Analytics | `networkx.Graph` | Mengidentifikasi topologi hubungan banyak-ke-satu (*many-to-one*) antara pemegang NIK dengan nomor kontak HP perantara/calo. |
| **Deterministic Rule & Spatiotemporal Filter** | Expert Knowledge Engine | Python `numpy` & `pandas` | Menerapkan regulasi eksplisit BPJS (Kartu Aktif) dan fisika perjalanan manusia antar faskes dengan pengecualian kasus gawat darurat. |
| **XAI Cascade (Template + LLM Ready)** | Natural Language Generation & Validation | `pydantic` + Template + LLM Interface | Menyusun penjelasan alasan medis dan administratif dalam format JSON valid dan narasi bahasa Indonesia formal maksimum 25 kata. |

### Mengapa Digunakan Formula `max(...)` Pada Ensemble?
Dalam audit fraud layanan kesehatan, **kecurangan tidak boleh dinetralkan oleh rata-rata**. 
* Jika sebuah klaim terbukti melakukan pelanggaran berat pada kartu non-aktif (skor 50) atau sindikat HP (skor 60), klaim tersebut **wajib ditahan** meskipun model ML memberikan skor rendah.
* Menggunakan `max(Rules, Graph, ML)` menjamin tidak adanya celah *false negative* di mana penipuan terstruktur lolos hanya karena nilai rata-ratanya tertarik turun oleh fitur-fitur normal lainnya.

---

## 🚀 5. Panduan Menjalankan Sistem untuk Demonstrasi

1. **Menjalankan Sistem:**
   Cukup jalankan satu perintah di terminal:
   ```powershell
   python run_demo.py
   ```
   *Peramban akan terbuka otomatis ke `http://localhost:8501`.*

2. **Skenario Alur Demonstrasi di Depan Penguji / Juri:**
   1. **Tunjukkan Dashboard Awal:** Jelaskan bahwa database sudah memproses ratusan klaim historis dan mendeteksi anomali secara *silent*.
   2. **Simulasikan Tarikan Data Baru:** Klik tombol **"🚀 Tarik 50 Klaim Baru (Faskes)"** di sidebar. Tunjukkan bahwa 50 klaim baru ditarik, di-hash seketika, dievaluasi melalui 3 layer AI, dan KPI metrics langsung terbarui otomatis.
   3. **Periksa Tab 1 (Antrean Prioritas):** Buka salah satu kartu berstatus 🔴 Merah atau 🟡 Kuning. Perlihatkan alasan XAI yang sangat mudah dibaca verifikator dan lakukan simulasi persetujuan verifikator (*Human-in-the-Loop*).
   4. **Periksa Tab 3 (Cara Kerja AI):** Tunjukkan diagram sebar *Scatter Plot* bagaimana sistem membedakan klaim *impossible travel* biasa vs rujukan darurat RSCM yang dibebaskan (*Zero False Alarm*).
   5. **Periksa Tab 4 (Graf Sindikat):** Tunjukkan simpul merah di mana 1 nomor HP menguasai puluhan NIK yang mengindikasikan percaloan klaim fiktif.

---
*Dokumentasi ini dibuat otomatis sebagai panduan arsitektur komprehensif proyek SIGAP v6.2.*
