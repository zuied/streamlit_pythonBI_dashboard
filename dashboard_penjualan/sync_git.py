import subprocess
import os
from datetime import datetime

def git_commit_new_file(filepath):
    filename = os.path.basename(filepath)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"🔄 Update data file: {filename} at {timestamp}"

    try:
        subprocess.run(["git", "add", filepath], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"✅ File '{filename}' berhasil disinkron ke Git.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Gagal sinkronisasi Git: {e}")
