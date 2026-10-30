"""
SIGAP v6.2 — PDF Generator untuk Laporan Audit
==============================================
Membuat laporan PDF dari hasil analisis AI untuk diunduh verifikator.
"""
from fpdf import FPDF
from io import BytesIO

class AuditReportPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(30, 58, 138) # Warna Biru BPJS
        self.cell(0, 10, 'SIGAP - Laporan Investigasi Klaim', 0, 1, 'C')
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'Sistem Identifikasi & Analitik Risiko Anti-Penyalahgunaan Peserta JKN', 0, 1, 'C')
        self.line(10, 30, 200, 30)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Halaman {self.page_no()} | Dokumen ini dihasilkan otomatis oleh SIGAP Engine v6.2', 0, 0, 'C')

def generate_audit_pdf(claim_data: dict) -> bytes:
    pdf = AuditReportPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)

    # 1. Informasi Klaim
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'A. Informasi Klaim', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    
    info = [
        ("ID Klaim", claim_data.get('id_klaim', '-')),
        ("NIK Hash (Anonim)", claim_data.get('nik_hash', '-')),
        ("No. HP", claim_data.get('no_hp', '-')),
        ("Status Kartu", claim_data.get('status_kartu', '-')),
        ("Faskes Tujuan", claim_data.get('faskes_tujuan', '-')),
        ("Jenis Kunjungan", claim_data.get('jenis_kunjungan', '-')),
        ("Jarak Tempuh", f"{claim_data.get('jarak_km', 0)} km dalam {claim_data.get('waktu_selisih_jam', 0)} jam")
    ]
    
    for label, value in info:
        pdf.cell(50, 8, label, 0, 0)
        pdf.cell(5, 8, ":", 0, 0)
        pdf.cell(0, 8, str(value), 0, 1)

    pdf.ln(5)

    # 2. Hasil Analisis AI
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'B. Hasil Analisis AI (Hybrid Intelligence)', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    
    skor_data = [
        ("Skor Rule-Based", claim_data.get('skor_rules', 0)),
        ("Skor Graph Network", claim_data.get('skor_graph', 0)),
        ("Skor Machine Learning", claim_data.get('skor_ml', 0)),
        ("Skor Isolation Forest", claim_data.get('skor_iforest', 0)),
        ("TOTAL SKOR RISIKO", claim_data.get('total_skor', 0)),
        ("KEPUTUSAN SISTEM", claim_data.get('keputusan', '-'))
    ]
    
    for label, value in skor_data:
        if label in ["TOTAL SKOR RISIKO", "KEPUTUSAN SISTEM"]:
            pdf.set_font('Helvetica', 'B', 11)
        else:
            pdf.set_font('Helvetica', '', 11)
        
        pdf.cell(60, 8, label, 0, 0)
        pdf.cell(5, 8, ":", 0, 0)
        pdf.cell(0, 8, str(value), 0, 1)

    pdf.ln(5)

    # 3. Penjelasan XAI (Explainable AI)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'C. Alasan Penahanan (Explainable AI)', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    
    evidence = str(claim_data.get('evidence_xai', 'Tidak ada narasi.'))
    pdf.multi_cell(0, 8, evidence)
    
    pdf.ln(10)
    
    # 4. Tanda Tangan Verifikator
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'D. Lembar Keputusan Verifikator', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, "Status: [ ] Disetujui (Lanjut Bayar)    [ ] Ditahan (Investigasi)    [ ] Ditolak (Fraud)", 0, 1)
    pdf.cell(0, 8, "Catatan Audit: .............................................................................................", 0, 1)
    pdf.ln(15)
    
    pdf.cell(100, 8, "Tanggal: .................................", 0, 1)
    pdf.cell(100, 8, "Nama Verifikator: .................................", 0, 1)
    pdf.cell(100, 8, "Tanda Tangan: .................................", 0, 1)

    return bytes(pdf.output())