"""
SIGAP v6.2 — Dashboard Verifikator (Streamlit)
==============================================
UI untuk meninjau antrean, Human-in-the-Loop, visualisasi Graph, dan Export PDF.
"""
import sys
import time
from pathlib import Path
root_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(root_dir))

import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from config import Status, Tier, TIER_FRAUD_THRESHOLD, TIER_REVIEW_THRESHOLD
from core.database import transaction, get_stats, init_schema
from pipelines.ingest import run_ingestion
from pipelines.analyze import run_analysis
from utils.logger import log
from utils.pdf_generator import generate_audit_pdf

# ═══════════════════════════════════════════════════════════════
# 0. INISIALISASI DATABASE
# ═══════════════════════════════════════════════════════════════
init_schema()

# ═══════════════════════════════════════════════════════════════
# 1. PAGE CONFIG & CUSTOM CSS
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SIGAP - BPJS Kesehatan",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .hero {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem;
    }
    .hero h1 { color: white; margin: 0; font-weight: 800; }
    .hero p { color: #DBEAFE; margin-top: 0.5rem; font-size: 1.1rem; }
    .metric-card {
        background: white; padding: 1.5rem; border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 5px solid #3B82F6;
    }
    .metric-value { color: #1F2937; font-size: 2rem; font-weight: 800; margin: 0; }
    .metric-label { color: #4B5563; font-size: 0.9rem; margin: 0; font-weight: 600; }
    .border-red { border-left-color: #EF4444; }
    .border-yellow { border-left-color: #F59E0B; }
    .border-green { border-left-color: #10B981; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 2. SIDEBAR (KONTROL & SIMULASI)
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("# 🛡️ BPJS Kesehatan")
    st.markdown("### SIGAP Engine v6.2")
    st.markdown("Silent Post-Audit Screening untuk JKN")
    st.divider()
    
    st.markdown("**Mode Demo**")
    if st.button("🚀 Tarik 50 Klaim Baru (Faskes)", use_container_width=True):
        with st.spinner("Menarik data & menjalankan AI..."):
            inserted = run_ingestion()
            processed, err_msg = run_analysis()
            
            st.cache_data.clear()
            
            if processed > 0:
                st.success(f"✅ {inserted} Klaim ditarik, {processed} Klaim diproses!")
            else:
                st.error(f"❌ Gagal memproses klaim. Error: {err_msg}. Cek terminal VSCode!")
            
            time.sleep(1.5)
            st.rerun()
            
    if st.button("⚠️ Reset Database", type="secondary", use_container_width=True):
        import subprocess
        subprocess.run([sys.executable, str(root_dir / "scripts" / "reset_demo.py"), "-y"])
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    st.markdown("**Auditor Login:**")
    st.info("👤 Verifikator_BPJS_01\n\n🏢 Kantor Cabang Jakarta Pusat")

# ═══════════════════════════════════════════════════════════════
# 3. DATA FETCHING (CACHED)
# ═══════════════════════════════════════════════════════════════
@st.cache_data(ttl=5)
def fetch_dashboard_data():
    with transaction(retry=False) as conn:
        df = pd.read_sql("""
            SELECT h.*, k.status_kartu, k.jarak_km, k.waktu_selisih_jam, 
                   k.jenis_kunjungan, k.faskes_tujuan, k.no_hp, k.nik_hash
            FROM tbl_hasil_risiko h
            JOIN tbl_klaim_mentah k ON h.id_klaim = k.id_klaim
            ORDER BY h.total_skor DESC
        """, conn)
    return df

df = fetch_dashboard_data()

# ═══════════════════════════════════════════════════════════════
# 4. HERO BANNER & KPI METRICS
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
    <h1>SIGAP: Smarter Protection for Sustainable JKN</h1>
    <p>Hybrid Intelligence | Zero Disruption to Faskes | Explainable AI</p>
</div>
""", unsafe_allow_html=True)

if len(df) == 0:
    st.warning("⚠️ Belum ada data. Silakan klik **'Tarik 50 Klaim Baru'** di sidebar.")
    st.stop()

total = len(df)
merah = len(df[df['keputusan'] == Tier.FRAUD])
kuning = len(df[df['keputusan'] == Tier.REVIEW])
hijau = len(df[df['keputusan'] == Tier.SAFE])

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="metric-card"><p class="metric-value">{total}</p><p class="metric-label">Total Klaim Dipindai</p></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card border-red"><p class="metric-value">{merah}</p><p class="metric-label">🔴 Antrean Fraud (Ditahan)</p></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card border-yellow"><p class="metric-value">{kuning}</p><p class="metric-label">🟡 Review Ringan</p></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card border-green"><p class="metric-value">{hijau}</p><p class="metric-label">🟢 Lolos (Aman)</p></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 5. TABS UTAMA
# ═══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(["📋 Antrean Investigasi", "📜 Riwayat & Ekspor", "🧠 Cara Kerja AI (XAI)", "🕸️ Graph Sindikat"])

# ─── TAB 1: ANTREAN & HUMAN-IN-THE-LOOP ───────────────────────
with tab1:
    st.subheader("Antrean Prioritas Verifikator")
    st.caption("Hanya klaim berisiko (Merah & Kuning) yang ditampilkan di sini.")
    
    df_antrean = df[df['keputusan'].isin([Tier.FRAUD, Tier.REVIEW])]
    
    if len(df_antrean) == 0:
        st.success("🎉 Luar biasa! Tidak ada klaim berisiko saat ini.")
    else:
        for _, row in df_antrean.iterrows():
            icon = "🔴" if row['keputusan'] == Tier.FRAUD else "🟡"
            
            with st.expander(f"{icon} [{row['id_klaim']}] Skor Risiko: {row['total_skor']} | {row['keputusan']}"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"**Alasan AI (XAI):** {row['evidence_xai']}")
                    st.markdown(f"""
                    - **Status Kartu:** {row['status_kartu']}
                    - **Jarak Tempuh:** {row['jarak_km']} km dalam {row['waktu_selisih_jam']} jam
                    - **Faskes Tujuan:** {row['faskes_tujuan']} ({row['jenis_kunjungan']})
                    - **No. HP:** {row['no_hp']}
                    """)
                    st.progress(int(row['total_skor']), text=f"Skor Ensemble: {row['total_skor']}/100")
                    
                    # --- FITUR EXPORT PDF ---
                    pdf_bytes = generate_audit_pdf(row.to_dict())
                    st.download_button(
                        label="📄 Unduh Laporan Audit (PDF)",
                        data=pdf_bytes,
                        file_name=f"Laporan_Audit_{row['id_klaim']}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{row['id_klaim']}"
                    )
                    # ------------------------
                    
                with c2:
                    st.markdown("**Keputusan Verifikator:**")
                    with st.form(key=f"form_{row['id_klaim']}"):
                        aksi = st.radio("Tindakan:", ["Setujui (Lanjut Bayar)", "Tahan (Investigasi)", "Tolak (Fraud)"])
                        catatan = st.text_area("Catatan Audit:")
                        submit = st.form_submit_button("Simpan Keputusan")
                        
                        if submit:
                            with transaction() as conn:
                                conn.execute("""
                                    INSERT INTO tbl_feedback_verifikator (id_klaim, aksi, verifikator, catatan)
                                    VALUES (?, ?, ?, ?)
                                """, (row['id_klaim'], aksi, "Verifikator_BPJS_01", catatan))
                                conn.execute("UPDATE tbl_klaim_mentah SET status_analisis = 'VERIFIED' WHERE id_klaim = ?", (row['id_klaim'],))
                            st.success(f"Keputusan untuk {row['id_klaim']} disimpan!")
                            st.cache_data.clear()
                            st.rerun()

# ─── TAB 2: RIWAYAT & EXPORT CSV ──────────────────────────────
with tab2:
    st.subheader("Riwayat Lengkap Pemindaian Klaim")
    st.dataframe(
        df[['id_klaim', 'total_skor', 'keputusan', 'status_kartu', 'evidence_xai']],
        use_container_width=True,
        hide_index=True
    )
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Hasil Pemindaian (CSV)", data=csv, file_name='sigap_hasil_audit.csv', mime='text/csv')

# ─── TAB 3: CARA KERJA AI (XAI) ───────────────────────────────
with tab3:
    st.subheader("Transparansi Algoritma (Explainable AI)")
    st.markdown("""
    Sistem SIGAP menggunakan **3 Lapisan Deteksi** dan **Hybrid ML Ensemble**:
    1. **Rule Engine:** Pelanggaran eksplisit (Kartu Non-Aktif).
    2. **Spatiotemporal Anomaly:** *Impossible Travel* (Jarak >300km dalam <3 jam). **Kecuali** Rujukan Darurat.
    3. **Graph Network:** Sindikat (1 No. HP terhubung ke >15 NIK).
    4. **Machine Learning:** XGBoost + Isolation Forest.
    
    **Formula Ensemble:** `Total Skor = max(Rule, Graph, ML_Weighted)`
    """)
    st.markdown("**Visualisasi Anomali Spatiotemporal:**")
    fig, ax = plt.subplots(figsize=(10, 4))
    colors = df['keputusan'].map({Tier.FRAUD: '#EF4444', Tier.REVIEW: '#F59E0B', Tier.SAFE: '#10B981'})
    ax.scatter(df['jarak_km'], df['waktu_selisih_jam'], c=colors, alpha=0.6, edgecolors='white')
    ax.axvline(x=300, color='red', linestyle='--', alpha=0.5, label='Batas Jarak (300km)')
    ax.axhline(y=3, color='red', linestyle='--', alpha=0.5, label='Batas Waktu (3 jam)')
    ax.set_xlabel("Jarak (km)")
    ax.set_ylabel("Waktu Tempuh (jam)")
    ax.legend()
    st.pyplot(fig)

# ─── TAB 4: GRAPH NETWORK ─────────────────────────────────────
with tab4:
    st.subheader("Peta Jaringan Sindikat (NIK ↔ No. HP)")
    st.caption("Node merah adalah HP yang terhubung ke banyak NIK (Indikasi Sindikat).")
    
    G = nx.Graph()
    sample_df = df.head(30) 
    for _, row in sample_df.iterrows():
        G.add_edge(str(row['nik_hash'])[:6], str(row['no_hp']))
    
    if len(G) > 0:
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        pos = nx.spring_layout(G, k=0.5, seed=42)
        node_colors = ['#EF4444' if G.degree(n) > 1 else '#3B82F6' for n in G.nodes()]
        nx.draw(G, pos, ax=ax2, with_labels=True, node_color=node_colors, 
                node_size=500, font_size=8, font_color='white', edge_color='gray')
        st.pyplot(fig2)
    else:
        st.info("Belum ada cukup data untuk membangun graf.")