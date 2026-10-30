"""
SIGAP v6.2 — One-Click Demo Launcher
"""
import subprocess
import sys
import webbrowser
import time

if __name__ == "__main__":
    print("=" * 60)
    print("  🚀 MENYALAKAN SIGAP DASHBOARD...")
    print("  Jangan tutup terminal ini selama presentasi.")
    print("=" * 60)
    
    # Buka browser otomatis setelah 2 detik
    time.sleep(2)
    webbrowser.open("http://localhost:8501")
    
    # Jalankan Streamlit
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard/app.py"])