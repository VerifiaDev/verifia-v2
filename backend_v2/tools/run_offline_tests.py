"""Run unchanged load/contract tests with a high-capacity test profile.
Security tests override individual limits to exercise rejections.
"""
import os
from pathlib import Path
import subprocess
import sys

env = os.environ.copy()
for key in ("MAX_ACTIVE_VERIFICATIONS", "RATE_LIMIT_PER_MINUTE", "HOURLY_QUOTA", "DAILY_QUOTA", "GLOBAL_DAILY_QUOTA", "MAX_RSS_MB"):
    env[key] = "100000"
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-p", "tools.offline_guard", *sys.argv[1:]], cwd=Path(__file__).resolve().parents[1], env=env))
