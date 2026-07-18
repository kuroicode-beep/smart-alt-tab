# run.py
"""개발 실행 스크립트: py -3.13 run.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from smart_alt_tab.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
