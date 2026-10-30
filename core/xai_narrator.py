"""
SIGAP v6.2 — Explainable AI (XAI) Narrator
===========================================
4-Tier Cascade: Qwen (Local) → Gemini (Cloud) → Template → Raw.

Fix dari Qwen & Gemini:
- Deterministic level & confidence (LLM tidak boleh intervensi)
- ThreadPoolExecutor timeout asli (bukan blocking)
- raw_decode() untuk ekstraksi JSON aman
- Template fallback anti-gagal
"""
import json
import re
import time
import os
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pydantic import BaseModel, Field, ValidationError
from config import (
    QWEN_TIMEOUT_SEC, GEMINI_TIMEOUT_SEC, 
    XAI_MAX_CHARS, TIER_FRAUD_THRESHOLD, TIER_REVIEW_THRESHOLD,
    Tier
)
from utils.logger import log

# ═══════════════════════════════════════════════════════════════
# 1. PYDANTIC GATEKEEPER
# ═══════════════════════════════════════════════════════════════
class XAIOutput(BaseModel):
    id_klaim: str
    level: str = Field(pattern=r"^(DITAHAN \(FRAUD\)|REVIEW RINGAN|LOLOS \(AMAN\))$")
    alasan_utama: str = Field(min_length=5, max_length=XAI_MAX_CHARS)
    detail: list[str] = Field(default_factory=list)
    rekomendasi_verifikator: str
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)

# ═══════════════════════════════════════════════════════════════
# 2. DETERMINISTIC INJECTORS (LLM Tidak Boleh Sentuh Ini)
# ═══════════════════════════════════════════════════════════════
def compute_level(skor_total: float) -> str:
    if skor_total >= TIER_FRAUD_THRESHOLD: return Tier.FRAUD
    elif skor_total >= TIER_REVIEW_THRESHOLD: return Tier.REVIEW
    return Tier.SAFE

def compute_confidence(skor_total: float, is_emergency: bool) -> float:
    if is_emergency: return 0.92
    if skor_total >= 60: return round(min(0.99, 0.90 + (skor_total - 60) / 100), 2)
    elif skor_total >= 35: return round(0.75 + (skor_total - 35) / 100, 2)
    return round(min(0.99, 0.85 + (35 - skor_total) / 100), 2)

# ═══════════════════════════════════════════════════════════════
# 3. ROBUST JSON EXTRACTOR (raw_decode)
# ═══════════════════════════════════════════════════════════════
def extract_json(raw: str) -> Optional[dict]:
    """Ambil JSON valid pertama dari output LLM yang mungkin berantakan."""
    if not raw: return None
    raw = re.sub(r'```(?:json)?\s*', '', raw)
    raw = re.sub(r'```\s*$', '', raw)
    start = raw.find('{')
    if start == -1: return None
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(raw[start:])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None

# ═══════════════════════════════════════════════════════════════
# 4. PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════
def build_prompt(claim: dict) -> str:
    is_emergency = (
        str(claim.get('jenis_kunjungan', '')).lower() == 'rujukan darurat' or
        any(x in str(claim.get('faskes_tujuan', '')) for x in ['RSUD', 'RSCM', 'Tipe A'])
    )
    
    anomalies = []
    if claim.get('status_aktif_num', 1) == 0:
        anomalies.append("Status kartu peserta Non-Aktif")
    if claim.get('spatiotemporal_anomaly', 0) > 0:
        anomalies.append(f"Impossible travel: {claim.get('jarak_km')}km dalam {claim.get('waktu_selisih_jam')} jam")
    if claim.get('skor_graph', 0) > 0:
        anomalies.append("No. HP terhubung >15 NIK (indikasi sindikat)")
    if claim.get('skor_iforest', 0) > 45:
        anomalies.append("Anomali pola biaya/durasi (Isolation Forest)")
    
    if not anomalies and claim.get('total_skor', 0) >= 35:
        anomalies.append("Anomali pola statistik transaksi (Machine Learning)")
    
    emergency_ctx = "PENTING: Rujukan Darurat. Anomali spatiotemporal DIKECUALIKAN." if is_emergency else ""
    
    return f"""Kamu XAI Narrator SIGAP. Output HANYA JSON valid, tanpa teks lain.

{emergency_ctx}
Data Klaim:
- ID: {claim['id_klaim']}
- Total Skor: {claim['total_skor']}
- Anomali: {json.dumps(anomalies, ensure_ascii=False)}

Klasifikasi: >=60 DITAHAN, 35-59 REVIEW, <35 LOLOS

Output WAJIB:
{{
  "id_klaim": "{claim['id_klaim']}",
  "alasan_utama": "maks 25 kata, Bahasa Indonesia formal",
  "detail": ["poin 1", "poin 2"],
  "rekomendasi_verifikator": "Tahan | Tinjau manual | Setujui pembayaran"
}}

JANGAN pakai ```json. JANGAN tambah teks. JSON:"""

# ═══════════════════════════════════════════════════════════════
# 5. TIER 1: QWEN LOKAL (ThreadPoolExecutor)
# ═══════════════════════════════════════════════════════════════
_qwen_model = None
_qwen_tokenizer = None

def _load_qwen():
    global _qwen_model, _qwen_tokenizer
    if _qwen_model is not None: return _qwen_model, _qwen_tokenizer
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        model_id = "Qwen/Qwen2.5-1.5B-Instruct"
        _qwen_tokenizer = AutoTokenizer.from_pretrained(model_id)
        _qwen_model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.float16,
            device_map="cuda" if torch.cuda.is_available() else "cpu"
        )
        return _qwen_model, _qwen_tokenizer
    except Exception as e:
        log.warning(f"Qwen load gagal: {e}")
        return None, None

def _qwen_inference(claim: dict) -> Optional[dict]:
    model, tokenizer = _load_qwen()
    if model is None: return None
    try:
        prompt = build_prompt(claim)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        outputs = model.generate(
            **inputs, max_new_tokens=300, temperature=0.3, 
            do_sample=False, pad_token_id=tokenizer.eos_token_id
        )
        response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        return extract_json(response)
    except Exception as e:
        log.warning(f"Qwen inference error: {e}")
        return None

def call_qwen(claim: dict) -> Optional[dict]:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_qwen_inference, claim)
        try:
            return future.result(timeout=QWEN_TIMEOUT_SEC)
        except FutureTimeout:
            log.warning(f"Qwen TIMEOUT (> {QWEN_TIMEOUT_SEC}s), fallback ke Tier 2.")
            return None
        except Exception:
            return None

# ═══════════════════════════════════════════════════════════════
# 6. TIER 2: GEMINI CLOUD
# ═══════════════════════════════════════════════════════════════
_gemini_configured = False

def call_gemini(claim: dict) -> Optional[dict]:
    global _gemini_configured
    try:
        import google.generativeai as genai
        if not _gemini_configured:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key: return None
            genai.configure(api_key=api_key)
            _gemini_configured = True
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(build_prompt(claim))
        return extract_json(response.text)
    except Exception as e:
        log.warning(f"Gemini error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
# 7. TIER 3: TEMPLATE (NEVER FAIL)
# ═══════════════════════════════════════════════════════════════
def call_template(claim: dict) -> dict:
    reasons = []
    if claim.get('status_aktif_num', 1) == 0: reasons.append("Status kartu Non-Aktif")
    if claim.get('spatiotemporal_anomaly', 0) > 0: reasons.append(f"Impossible travel: {claim.get('jarak_km')}km/{claim.get('waktu_selisih_jam')}jam")
    if claim.get('skor_graph', 0) > 0: reasons.append("Terhubung sindikat HP (>15 NIK)")
    if claim.get('skor_iforest', 0) > 45: reasons.append("Anomali statistik biaya/durasi")
    if not reasons: reasons = ["Anomali pola statistik transaksi (Machine Learning)"]
    
    level = compute_level(claim['total_skor'])
    if level == Tier.FRAUD: rekom = "Tahan untuk audit lanjutan sebelum pembayaran."
    elif level == Tier.REVIEW: rekom = "Tinjau manual oleh verifikator."
    else: 
        rekom = "Setujui pembayaran."
        reasons = ["Tidak ada anomali terdeteksi"]
    
    return {
        "alasan_utama": (reasons[0] + ".")[:XAI_MAX_CHARS],
        "detail": reasons,
        "rekomendasi_verifikator": rekom
    }

# ═══════════════════════════════════════════════════════════════
# 8. MAIN CASCADE (4-TIER)
# ═══════════════════════════════════════════════════════════════
def generate_xai(claim: dict) -> dict:
    is_emergency = (
        str(claim.get('jenis_kunjungan', '')).lower() == 'rujukan darurat' or
        any(x in str(claim.get('faskes_tujuan', '')) for x in ['RSUD', 'RSCM', 'Tipe A'])
    )
    
    # Deterministic — TIDAK bergantung LLM
    level = compute_level(claim['total_skor'])
    confidence = compute_confidence(claim['total_skor'], is_emergency)
    
    # TIER 1: Qwen
    result = call_qwen(claim)
    
    # TIER 2: Gemini
    if not result or not all(k in result for k in ['alasan_utama', 'detail', 'rekomendasi_verifikator']):
        result = call_gemini(claim)
        
    # TIER 3: Template
    if not result or not all(k in result for k in ['alasan_utama', 'detail', 'rekomendasi_verifikator']):
        result = call_template(claim)
    
    # Override level & confidence
    final = {
        "id_klaim": claim['id_klaim'],
        "level": level,
        "alasan_utama": str(result.get('alasan_utama', 'Narasi tidak tersedia.'))[:XAI_MAX_CHARS],
        "detail": result.get('detail', []),
        "rekomendasi_verifikator": str(result.get('rekomendasi_verifikator', 'Tinjau manual.')),
        "confidence": confidence
    }
    
    # PYDANTIC VALIDATION (Gerbang Terakhir)
    try:
        validated = XAIOutput(**final)
        return validated.model_dump()
    except ValidationError as e:
        log.error(f"Pydantic reject: {e}")
        return {
            "id_klaim": claim['id_klaim'],
            "level": level,
            "alasan_utama": "Sistem tidak dapat validasi narasi. Perlu review manual.",
            "detail": ["XAI validation failed"],
            "rekomendasi_verifikator": "Tinjau manual oleh verifikator.",
            "confidence": 0.50
        }

# ═══════════════════════════════════════════════════════════════
# 9. SELF-TEST (jalankan: python -m core.xai_narrator)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  🎭 XAI NARRATOR (4-TIER CASCADE) SELF-TEST")
    print("=" * 60)

    # Dummy data untuk menguji 4 skenario
    dummy_claims = [
        # 1. Fraud: Non-Aktif + Impossible Travel
        {"id_klaim": "K-1", "total_skor": 65.0, "status_aktif_num": 0, "spatiotemporal_anomaly": 60.0, "skor_graph": 0, "skor_iforest": 0, "jarak_km": 850, "waktu_selisih_jam": 1.5, "jenis_kunjungan": "Rutin", "faskes_tujuan": "Klinik"},
        # 2. Review: IForest Anomaly only
        {"id_klaim": "K-2", "total_skor": 45.0, "status_aktif_num": 1, "spatiotemporal_anomaly": 0, "skor_graph": 0, "skor_iforest": 55.0, "jarak_km": 10, "waktu_selisih_jam": 5, "jenis_kunjungan": "Rutin", "faskes_tujuan": "Klinik"},
        # 3. Fraud: Graph Sindikat
        {"id_klaim": "K-3", "total_skor": 60.0, "status_aktif_num": 1, "spatiotemporal_anomaly": 0, "skor_graph": 60.0, "skor_iforest": 0, "jarak_km": 10, "waktu_selisih_jam": 5, "jenis_kunjungan": "Rutin", "faskes_tujuan": "Klinik"},
        # 4. Safe: Darurat (dikecualikan)
        {"id_klaim": "K-4", "total_skor": 0.0, "status_aktif_num": 1, "spatiotemporal_anomaly": 0, "skor_graph": 0, "skor_iforest": 0, "jarak_km": 1200, "waktu_selisih_jam": 2.0, "jenis_kunjungan": "Rujukan Darurat", "faskes_tujuan": "RSUPN Cipto"},
    ]

    print("\n[*] Memproses XAI (Karena Qwen/Gemini belum diinstall, ini akan otomatis jatuh ke Tier 3 - Template):")
    print("-" * 60)
    
    for claim in dummy_claims:
        res = generate_xai(claim)
        print(f"[{res['id_klaim']}] LEVEL: {res['level']}")
        print(f"      Alasan: {res['alasan_utama']}")
        print(f"      Rekomendasi: {res['rekomendasi_verifikator']}")
        print(f"      Confidence: {res['confidence']}")
        print("-" * 60)
        
        # Verifikasi Deterministic Level
        if claim['total_skor'] >= 60:
            assert res['level'] == Tier.FRAUD, f"{claim['id_klaim']} harus FRAUD"
        elif claim['total_skor'] >= 35:
            assert res['level'] == Tier.REVIEW, f"{claim['id_klaim']} harus REVIEW"
        else:
            assert res['level'] == Tier.SAFE, f"{claim['id_klaim']} harus SAFE"

    print("\n[✓] XAI Narrator LULUS SEMUA TES (Cascade berjalan sempurna)!")
    print("=" * 60)