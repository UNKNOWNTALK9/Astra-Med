import subprocess
import sys

rc = subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
rc |= subprocess.call([sys.executable, "tests/smoke_gui.py"])
sys.exit(rc)
