"""웹 서버 진입점에서 공통 src 패키지 경로를 먼저 등록한다."""
from pathlib import Path
import sys

_SRC = str(Path(__file__).resolve().parents[2] / 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
