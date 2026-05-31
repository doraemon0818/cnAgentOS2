import subprocess
import sys

try:
    result = subprocess.run(
        [r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
         "-u", "root", "-p912419", "-e", "SELECT 1"],
        capture_output=True,
        text=True,
        timeout=5
    )
    print("Return code:", result.returncode)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
except Exception as e:
    print(f"Error: {e}")
