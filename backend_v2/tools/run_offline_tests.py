"""Run offline tests with the same security limits as CI; never raise quotas."""
import os
from pathlib import Path
import subprocess
import sys

env = os.environ.copy()
env.update(GROQ_API_KEY="", TAVILY_API_KEY="")
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-p", "tools.offline_guard", *sys.argv[1:]], cwd=Path(__file__).resolve().parents[1], env=env))
