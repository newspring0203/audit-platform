"""Deployment entrypoint: one ASGI process, platform port, no local token files."""
from pathlib import Path
import os, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    from backend.app.config import AppConfig
    AppConfig.from_env()  # Fail fast on invalid deployment configuration.
    port = int(os.environ.get('PORT', '8000'))
    if not 1 <= port <= 65535:
        raise SystemExit('PORT must be between 1 and 65535')
    os.chdir(ROOT)
    os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'backend.app.main:create_app',
        '--factory', '--host', '0.0.0.0', '--port', str(port), '--workers', '1',
        '--no-access-log', '--no-proxy-headers'])
if __name__ == '__main__': main()
